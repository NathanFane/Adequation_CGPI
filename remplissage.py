"""Remplissage progressif du tableau à partir des listes de supports des assureurs.

Chaque jour, de nouveaux supports sont ajoutés (Yahoo Finance, EODHD en secours), en commençant
par ceux dont les données assureur sont les plus complètes. Un support n'est rattaché aux contrats
de l'utilisateur que si ses VL ont été trouvées.
"""
from collections import Counter

from collecte import _tout, actualiser

NOMS_CONTRATS = {
    "cardif_elite": "Cardif Elite",
    "generali_8301": "Generali 8301",
    "vieplus_patrimoine_vie_plus_multiprojet": "Patrimoine Vie Plus Multiprojet",
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


def ajouter_nouveaux(db, cle, user_id, nombre=300, max_produits=1500, journal=print) -> dict:
    """Ajoute jusqu'à `nombre` nouveaux supports (Yahoo, puis EODHD dans la limite du quota).

    `max_produits` plafonne le nombre de produits suivis (stockage de la base gratuite Supabase).
    """
    supports = _tout(db.table("supports_contrat_actuels").select(
        "contrat, assureur, isin, nom, type_produit, sri, sfdr, frais_actif, retrocessions, frais_contrat, "
        "ouvert, avenant_requis"))
    produits = {p["isin"]: p for p in _tout(db.table("produits").select("isin, statut, derniere_vl"))}
    suivis = sum(p["statut"] == "valide" for p in produits.values())

    # Candidats : supports ouverts, sans avenant, jamais essayés ; un ISIN = meilleure ligne
    par_isin = {}
    for s in supports:
        if s.get("ouvert") is False or s.get("avenant_requis") or s["isin"] in produits:
            continue
        cle_tri = (-_completude(s), ORDRE_TYPES.get(s["type_produit"], 9))
        if s["isin"] not in par_isin or cle_tri < par_isin[s["isin"]][0]:
            par_isin[s["isin"]] = (cle_tri, s)
    nb_contrats = Counter(s["isin"] for s in supports)
    candidats = [s for _, s in sorted(par_isin.values(), key=lambda x: (x[0], -nb_contrats[x[1]["isin"]]))]
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
    journal(f"Nouveaux supports : {len(rapport['ajoutes'])} avec VL, {len(rapport['en_attente'])} en attente, "
            f"{rapport['restants']} restant(s) dans les listes"
            + (f" ; plafond de {max_produits} produits atteint" if rapport["plafond_atteint"] else ""))
    return rapport
