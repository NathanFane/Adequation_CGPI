"""Remplissage progressif du tableau à partir des listes de supports des assureurs.

Chaque jour, de nouveaux supports sont ajoutés (Yahoo Finance, EODHD en secours), en commençant
par ceux dont les données assureur sont les plus complètes. Un support n'est rattaché aux contrats
de l'utilisateur que si ses VL ont été trouvées.
"""
from collections import Counter

from collecte import _tout, actualiser
from listes_assureurs import classe_assureur

NOMS_CONTRATS = {
    "cardif_elite": "Cardif Elite",
    "generali_8301": "Generali 8301",
    "vieplus_patrimoine_vie_plus_multiprojet": "Patrimoine Vie Plus Multiprojet",
    "generali_espace_lux": "Generali Espace Lux",
    "cardif_panthea_vie_2": "Cardif Panthéa Vie 2",
}
# Types sans VL quotidienne sur EODHD (SCPI, fonds à formule) : en dernier
ORDRE_TYPES = {"fonds": 0, "etf": 1, "action": 2, "obligation": 3, "scpi": 4, "autre": 5}



def _completude(s):
    return sum(s.get(c) is not None for c in ("sri", "frais_actif", "sfdr", "retrocessions", "frais_contrat"))


def _contrats(db, user_id, supports):
    """Crée au besoin les contrats de l'utilisateur ; renvoie {code contrat: id}."""
    existants = {c["nom"]: c["id"] for c in
                 db.table("contrats").select("id, nom").eq("user_id", user_id).execute().data}
    ids = {}
    for code in sorted({s["contrat"] for s in supports}):
        nom = NOMS_CONTRATS.get(code, code)
        if nom not in existants:
            lignes = [s for s in supports if s["contrat"] == code]
            frais = Counter(s.get("frais_contrat") for s in lignes if s.get("frais_contrat") is not None)
            r = db.table("contrats").insert({
                "user_id": user_id, "nom": nom, "assureur": lignes[0]["assureur"],
                "frais_gestion_uc": frais.most_common(1)[0][0] if frais else None,
            }).execute()
            existants[nom] = r.data[0]["id"]
        ids[code] = existants[nom]
    return ids


def rattacher(db, user_id, supports, isins):
    """Ajoute `isins` aux contrats qui les proposent (frais spécifiques si différents du contrat)."""
    ids = _contrats(db, user_id, supports)
    frais_contrat = {c["id"]: c["frais_gestion_uc"] for c in
                     db.table("contrats").select("id, frais_gestion_uc").eq("user_id", user_id).execute().data}
    lignes = []
    for s in supports:
        if s["isin"] in isins:
            cid = ids[s["contrat"]]
            specifique = s.get("frais_contrat") if s.get("frais_contrat") != frais_contrat.get(cid) else None
            lignes.append({"contrat_id": cid, "isin": s["isin"], "frais_specifiques": specifique})
    for i in range(0, len(lignes), 500):
        db.table("contrat_produits").upsert(lignes[i:i + 500], on_conflict="contrat_id,isin",
                                            ignore_duplicates=True).execute()
    return len(lignes)


def classer(db, supports):
    """Classe d'actifs des produits suivis d'après les assureurs (prioritaire sur celle déduite de l'indice)."""
    votes = {}
    for s in supports:
        c = classe_assureur(s.get("classification"), s.get("type_produit"))
        if c:
            votes.setdefault(s["isin"], Counter())[c] += 1
    produits = _tout(db.table("produits").select("isin, classe_actifs, classe_source"))
    par_classe = {}
    for p in produits:
        if p["isin"] in votes:
            c = votes[p["isin"]].most_common(1)[0][0]
            if (p["classe_actifs"], p["classe_source"]) != (c, "assureur"):
                par_classe.setdefault(c, []).append(p["isin"])
    for c, isins in par_classe.items():
        for i in range(0, len(isins), 200):
            db.table("produits").update({"classe_actifs": c, "classe_source": "assureur"}) \
                .in_("isin", isins[i:i + 200]).execute()


def _repartir(candidats, nb_contrats):
    """Ordre d'import équilibré : tour à tour chaque (contrat, classe d'actifs, fonds/action),
    et dans chaque groupe les supports aux données les plus complètes d'abord."""
    groupes = {}
    for s in candidats:
        cle = (s["contrat"], classe_assureur(s.get("classification"), s["type_produit"]) or "inconnue",
               s["type_produit"] == "action")
        groupes.setdefault(cle, []).append(s)
    for g in groupes.values():
        g.sort(key=lambda s: (-_completude(s), ORDRE_TYPES.get(s["type_produit"], 9), -nb_contrats[s["isin"]]))
    ordre, rang = [], 0
    while len(ordre) < len(candidats):
        for cle in sorted(groupes):
            if rang < len(groupes[cle]):
                ordre.append(groupes[cle][rang])
        rang += 1
    return ordre


def ajouter_nouveaux(db, cle, user_id, nombre=500, max_produits=2800, journal=print) -> dict:
    """Ajoute jusqu'à `nombre` nouveaux supports (Yahoo, puis EODHD dans la limite du quota).

    `max_produits` plafonne le nombre de produits suivis (stockage de la base gratuite Supabase).
    """
    supports = _tout(db.table("supports_contrat_actuels").select(
        "contrat, assureur, isin, nom, type_produit, classification, sri, sfdr, frais_actif, retrocessions, "
        "frais_contrat, ouvert, avenant_requis"))
    produits = {p["isin"]: p for p in _tout(db.table("produits").select("isin, statut, derniere_vl"))}
    suivis = sum(p["statut"] == "valide" for p in produits.values())
    try:   # fonds supprimés volontairement (migration 015) : jamais réimportés
        exclus = {e["isin"] for e in _tout(db.table("fonds_exclus").select("isin").order("isin"))}
    except Exception:
        exclus = set()

    # Candidats : supports ouverts, sans avenant, jamais essayés, avec des VL de marché
    # (ni SCPI ni fonds à formule) ; un ISIN = sa ligne la plus complète
    par_isin = {}
    for s in supports:
        if (s.get("ouvert") is False or s.get("avenant_requis") or s["isin"] in produits or s["isin"] in exclus
                or s["type_produit"] != "fonds"   # fonds uniquement (ni actions, ni ETF, ni SCPI)
                or classe_assureur(s.get("classification"), s["type_produit"]) == "structure"):
            continue
        if s["isin"] not in par_isin or _completude(s) > _completude(par_isin[s["isin"]]):
            par_isin[s["isin"]] = s
    candidats = _repartir(list(par_isin.values()), Counter(s["isin"] for s in supports))
    lot = candidats[:max(0, min(nombre, max_produits - suivis))]

    rapport = {"ajoutes": [], "en_attente": [], "restants": len(candidats) - len(lot), "erreur": None,
               "plafond_atteint": suivis + len(lot) >= max_produits}
    if lot:
        db.table("produits").upsert([{"isin": s["isin"], "nom": s["nom"], "type_produit": s["type_produit"],
                                      "statut": "valide"} for s in lot], on_conflict="isin").execute()
        r = actualiser(db, cle, [s["isin"] for s in lot])
        rapport["erreur"] = r["erreur"]
        trouves = {i for i, _ in r["maj"]}
        rapport["ajoutes"] = sorted(trouves)
        # Sans VL : seront retentés via EODHD les jours suivants, ou marqués introuvables
        rapport["en_attente"] = [s["isin"] for s in lot if s["isin"] not in trouves]

    # Rattachement aux contrats de tous les produits suivis ayant des VL (aucun appel externe)
    avec_vl = {p["isin"] for p in _tout(db.table("produits").select("isin").eq("statut", "valide")
                                        .not_.is_("derniere_vl", "null"))}
    rattacher(db, user_id, supports, avec_vl & {s["isin"] for s in supports})
    classer(db, supports)
    journal(f"Nouveaux supports : {len(rapport['ajoutes'])} avec VL, {len(rapport['en_attente'])} en attente, "
            f"{rapport['restants']} restant(s) dans les listes"
            + (f" ; plafond de {max_produits} produits atteint" if rapport["plafond_atteint"] else ""))
    return rapport
