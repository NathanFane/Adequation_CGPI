"""Lecture des listes de supports publiées par les assureurs.

Un lecteur par assureur : le dossier donnees/contrats/<assureur>/ indique lequel utiliser.
Chaque lecteur renvoie des lignes au format de la table supports_contrat.
"""
import re
from datetime import date

import openpyxl
import pandas as pd

from isin import est_valide, normaliser


def _texte(v):
    if v is None or pd.isna(v):
        return None
    v = str(v).strip()
    return v or None


def _pourcent(v):
    """« 1.93 » ou « 1,93 » (en %) -> 0.0193. Vide ou non numérique -> None."""
    v = _texte(v)
    if v is None:
        return None
    try:
        return round(float(v.replace(",", ".").replace("%", "")) / 100, 6)
    except ValueError:
        return None


def _on(v):
    """« O » -> True, « N » -> False, autre -> None."""
    v = (_texte(v) or "").upper()
    return True if v == "O" else False if v == "N" else None


def _sfdr(v):
    v = (_texte(v) or "").lower().replace("article", "").strip()
    return int(v) if v in ("6", "8", "9") else None


def _lire_csv(chemin):
    """CSV « ; » en UTF-8 ou, à défaut, Latin-1 (export Windows)."""
    try:
        return pd.read_csv(chemin, sep=";", dtype=str, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(chemin, sep=";", dtype=str, encoding="latin-1")


# ---------------------------------------------------------------- Generali
def lire_generali(chemin: str):
    df = _lire_csv(chemin)
    df.columns = [c.strip() for c in df.columns]
    lignes, anomalies = [], []
    for _, r in df.iterrows():
        isin = normaliser(r.get("Code ISIN"))
        if not est_valide(isin):
            nom = _texte(r.get("Libelle de l'element financier"))
            anomalies.append(f"ISIN invalide : {r.get('Code ISIN')!r} ({nom})")
            continue
        if _on(r.get("Indicateur ETFs")):
            type_produit = "etf"
        elif _on(r.get("Indicateur Titres vifs /Actions")):
            type_produit = "action"
        elif (_texte(r.get("Nature juridique")) or "").upper() == "SCPI":
            type_produit = "scpi"
        else:
            type_produit = "fonds"
        lignes.append({
            "contrat": f"generali_{_texte(r.get('Code produit'))}",
            "assureur": "Generali",
            "isin": isin,
            "nom": _texte(r.get("Libelle de l'element financier")),
            "code_support": _texte(r.get("Code garantie elementaire")),
            "forme_juridique": _texte(r.get("Nature juridique")),
            "type_produit": type_produit,
            "societe_gestion": _texte(r.get("Societe de gestion")),
            "classification": _texte(r.get("Classification EUROPERF")),
            "sfdr": _sfdr(r.get("Classification SFDR")),
            "frais_actif": _pourcent(r.get("Frais de gestion de l'actif")),
            "retrocessions": _pourcent(r.get("Taux de retrocessions de commissionnement")),
            "frais_contrat": _pourcent(r.get("Frais de gestion du contrat")),
            "frais_totaux": _pourcent(r.get("Frais de gestion totaux")),
            "perf_brute_n1": _pourcent(r.get("Performance brute de l'actif N-1")),
            "perf_nette_n1": _pourcent(r.get("Performance nette de l'unite de compte N-1")),
            "perf_finale_n1": _pourcent(r.get("Performance finale")),
            "ouvert": (_texte(r.get("Etat de l'element financier")) or "").lower() == "ouvert",
            "avenant_requis": _on(r.get("Indicateur Fonds a avenant ?")),
            "cotation_quotidienne": _on(r.get("Cotation quotidienne")),
            "eligible_pea": _on(r.get("Eligibilite P.E.A.")),
            "complements": {
                "gestion_libre": _on(r.get("Gestion libre ?")),
                "gestion_pilotee": _on(r.get("Gestion pilotee ?")),
                "liste": _texte(r.get("Mandataire")),
            },
        })
    return lignes, anomalies


# ---------------------------------------------------------------- Vie Plus (Suravenir)
def _date(v):
    v = _texte(v)
    if v is None:
        return None
    try:
        return pd.Timestamp(v).date()
    except ValueError:
        return None


def _decimal(v):
    """Valeur déjà en décimal (0.2069 = 20,69 %)."""
    v = _texte(v)
    try:
        return float(v.replace(",", ".")) if v is not None else None
    except ValueError:
        return None


def _type_vieplus(nom, categorie):
    nom, categorie = (nom or "").upper(), (categorie or "").upper()
    if "ETF" in nom:
        return "etf"
    if categorie.startswith("IMMOBILIER") or re.search(r"\b(SCPI|SCI|OPCI)\b", nom):
        return "scpi"
    if "CAPITAL GARANTI" in categorie or "CAPITAL PROTEGE" in categorie:
        return "autre"   # fonds à formule / structurés
    return "fonds"


def lire_vieplus(chemin: str):
    titre = _texte(pd.read_excel(chemin, header=None, nrows=1, dtype=str).iat[0, 0]) or "Patrimoine Vie Plus"
    df = pd.read_excel(chemin, header=1, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    # Date de la liste : date de VL la plus fréquente (quelques dates du fichier sont aberrantes)
    dates = df["Date dernière VL 2025"].dropna()
    date_liste = _date(dates.mode().iat[0]) if not dates.empty else date.today()
    contrat = "vieplus_" + re.sub(r"[^a-z0-9]+", "_", titre.lower()).strip("_")
    lignes, anomalies = [], []
    for _, r in df.iterrows():
        isin = normaliser(r.get("Code Isin"))
        nom = _texte(r.get("Unité de compte"))
        if not est_valide(isin):
            anomalies.append(f"ISIN invalide : {r.get('Code Isin')!r} ({nom})")
            continue
        fermeture = [d for d in (_date(r.get("Date de fermeture commerciale")),
                                 _date(r.get("Date de fin des entrées"))) if d]
        sri = _texte(r.get("Indice de risque"))
        categorie = _texte(r.get("Catégorie MorningStar"))
        lignes.append({
            "contrat": contrat,
            "assureur": "Vie Plus (Suravenir)",
            "isin": isin,
            "date_liste": date_liste.isoformat(),
            "nom": nom,
            "type_produit": _type_vieplus(nom, categorie),
            "societe_gestion": _texte(r.get("Gestionnaire")),
            "classification": categorie,
            "sri": int(sri) if sri in list("1234567") else None,
            "sfdr": _sfdr(r.get("Classification SFDR")),
            "label_isr": _on(r.get("ISR")),
            "label_greenfin": _on(r.get("Greenfin")),
            "frais_actif": _pourcent(r.get("Frais de gestion")),
            "perf_brute_n1": None,
            "perf_nette_n1": _decimal(r.get("Performances annuelles 2024")),
            "ouvert": all(d > date.today() for d in fermeture),   # encore ouvert aujourd'hui
            "cotation_quotidienne": (_texte(r.get("Périodicité de cotation")) or "").startswith("Journalière"),
            "eligible_pea": _on(r.get("Eligibilité PEA")),
            "complements": {
                "note_morningstar": _texte(r.get("Notation MorningStar")),
                "volatilite_1an": _decimal(r.get("Volatilités 1 an")),
                "volatilite_3ans": _decimal(r.get("Volatilités 3 ans")),
                "volatilite_5ans": _decimal(r.get("Volatilités 5 ans")),
                "sharpe": _decimal(r.get("Ratio de Sharpe")),
                "perf_5ans_cumulee": _decimal(r.get("Performances glissantes 5 ans")),
                "perf_annuelles": {a: _decimal(r.get(f"Performances annuelles {a}")) for a in range(2018, 2025)},
                "devise": _texte(r.get("Devise d'origine du fonds")),
                "date_creation": str(_date(r.get("Date création du fonds")) or "") or None,
                "categorie_amf": _texte(r.get("Classification au sens AMF")),
                "finansol": _on(r.get("Finansol")),
                "part_taxonomie": _decimal(r.get("Taxonomie (part verte exprimée en %)")),
                "date_fermeture": str(min(fermeture)) if fermeture else None,
            },
        })
    return lignes, anomalies


# ---------------------------------------------------------------- Cardif
MOIS = {m: i for i, m in enumerate(["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
                                     "septembre", "octobre", "novembre", "decembre"], 1)}
# Colonnes (identiques dans les deux tableaux : fonds puis titres vifs)
C_CLASSE, C_ISIN, C_NOM, C_FORME, C_SDG, C_SRI = 0, 1, 2, 3, 4, 5
C_BRUT_N1, C_BRUT_5A, C_FRAIS_ACTIF, C_NET_N1, C_NET_5A = 6, 7, 8, 9, 10
C_FRAIS_CONTRAT, C_FRAIS_TOTAUX, C_FINAL_N1, C_FINAL_5A, C_SFDR, C_ISR, C_GREENFIN = 11, 12, 13, 14, 15, 16, 17


def _valeur_cardif(v):
    """Nombre décimal (0.01), texte en % (« 1% », « 0,46% ») ; NC, NA, - -> None."""
    if isinstance(v, (int, float)):
        return float(v)
    v = _texte(v)
    if v is None or v.upper() in ("NC", "NA", "-"):
        return None
    m = re.match(r"^(-?[\d.,]+)\s*%", v)
    if m:
        return round(float(m.group(1).replace(",", ".")) / 100, 6)
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def _frais_dont(v):
    """« 0,46% (dont 0,14%) » -> (0.0046, 0.0014)."""
    if isinstance(v, (int, float)):
        return float(v), None
    v = _texte(v) or ""
    m = re.match(r"^\s*([^()]*)\(\s*dont\s*([^)]*)\)", v)
    if m:
        return _valeur_cardif(m.group(1)), _valeur_cardif(m.group(2))
    return _valeur_cardif(v), None


def _type_cardif(classe, forme):
    classe, forme = (classe or "").lower(), (forme or "").upper()
    if classe.startswith("titre vif"):
        return "action" if "action" in classe else "obligation" if "oblig" in classe else "autre"
    if forme == "ETF":
        return "etf"
    if forme in ("SCPI", "OPCI", "SCI") or "immobilier" in classe:
        return "scpi"
    if forme == "CERTIFICAT":
        return "autre"
    return "fonds"


def lire_cardif(chemin: str):
    ws = openpyxl.load_workbook(chemin, data_only=True, read_only=True).worksheets[0]
    lignes_xl = [list(r) + [None] * 19 for r in ws.iter_rows(values_only=True)]
    # Date « en vigueur au 1er juillet 2025 » dans l'en-tête
    date_liste = date.today()
    for r in lignes_xl[:10]:
        t = (_texte(r[0]) or "").lower().replace("é", "e").replace("û", "u")
        m = re.search(r"au\s+(\d{1,2})(?:er)?\s+([a-z]+)\s+(\d{4})", t)
        if m and m.group(2) in MOIS:
            date_liste = date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
            break
    entetes = [i for i, r in enumerate(lignes_xl) if _texte(r[C_ISIN]) == "Code ISIN"]
    if not entetes:
        raise ValueError(f"{chemin} : aucune ligne d'en-tête « Code ISIN » trouvée")
    for i in entetes:   # contrôle : les colonnes n'ont pas bougé
        h = lignes_xl[i]
        if not ("SRI" in (h[C_SRI] or "") and "Frais de gestion de l" in (h[C_FRAIS_ACTIF] or "")
                and "Frais de gestion du contrat" in (h[C_FRAIS_CONTRAT] or "")):
            raise ValueError(f"{chemin} : colonnes inattendues ligne {i + 1}, le format a changé")
    lignes, anomalies = [], []
    for n, debut in enumerate(entetes):
        fin = entetes[n + 1] if n + 1 < len(entetes) else len(lignes_xl)
        titres_vifs = _texte(lignes_xl[debut][C_NOM]) != "Libellé"
        for r in lignes_xl[debut + 2:fin]:
            brut = _texte(r[C_ISIN])
            if brut is None or brut == "Code ISIN":
                continue
            isin = normaliser(brut)
            if not est_valide(isin):
                anomalies.append(f"ISIN invalide : {brut!r} ({_texte(r[C_NOM])})")
                continue
            frais_actif, retro = _frais_dont(r[C_FRAIS_ACTIF])
            frais_totaux, _ = _frais_dont(r[C_FRAIS_TOTAUX])
            sri = _texte(r[C_SRI])
            classe = _texte(r[C_CLASSE])
            ligne = {
                "contrat": "cardif_elite",
                "assureur": "Cardif",
                "isin": isin,
                "date_liste": date_liste.isoformat(),
                "nom": _texte(r[C_NOM]),
                "forme_juridique": "Action" if titres_vifs else _texte(r[C_FORME]),
                "type_produit": _type_cardif(classe, None if titres_vifs else _texte(r[C_FORME])),
                "societe_gestion": None if titres_vifs else _texte(r[C_SDG]),
                "classification": classe,
                "sri": int(sri) if sri in list("1234567") else None,
                "frais_actif": frais_actif,
                "retrocessions": retro,
                "frais_contrat": _valeur_cardif(r[C_FRAIS_CONTRAT]),
                "frais_totaux": frais_totaux,
                "perf_brute_n1": _valeur_cardif(r[C_BRUT_N1]),
                "perf_nette_n1": _valeur_cardif(r[C_NET_N1]),
                "perf_finale_n1": _valeur_cardif(r[C_FINAL_N1]),
                "ouvert": True,
                "complements": {
                    "perf_brute_5ans_annualisee": _valeur_cardif(r[C_BRUT_5A]),
                    "perf_nette_5ans_annualisee": _valeur_cardif(r[C_NET_5A]),
                    "perf_finale_5ans_annualisee": _valeur_cardif(r[C_FINAL_5A]),
                },
            }
            if titres_vifs:
                ligne["complements"].update({"indice": _texte(r[C_FORME]), "secteur": _texte(r[C_SDG])})
            else:
                ligne.update({"sfdr": _sfdr(r[C_SFDR]),
                              "label_isr": (_texte(r[C_ISR]) or "").upper() == "X",
                              "label_greenfin": (_texte(r[C_GREENFIN]) or "").upper() == "X"})
            lignes.append(ligne)
    return lignes, anomalies


LECTEURS = {"generali": lire_generali, "vieplus": lire_vieplus, "cardif": lire_cardif}


def extraire(dossier_assureur: str, fichiers: list[str]):
    """Lit les fichiers d'un dossier assureur. Une ligne par (contrat, ISIN) ; doublons signalés."""
    lecteur = LECTEURS[dossier_assureur]
    retenues, anomalies, nb = {}, [], 0
    for chemin in fichiers:
        lignes, anom = lecteur(chemin)
        nb += len(lignes)
        anomalies += anom
        for l in lignes:
            l["fichier_source"] = chemin.rsplit("/", 1)[-1]
            l.setdefault("date_liste", date.today().isoformat())
            cle = (l["contrat"], l["isin"])
            if cle in retenues:
                a = retenues[cle]
                if (a["frais_contrat"], a["frais_actif"]) != (l["frais_contrat"], l["frais_actif"]):
                    anomalies.append(f"{l['isin']} en double avec des frais différents "
                                     f"({a['code_support']} / {l['code_support']}) : première ligne gardée")
                continue
            retenues[cle] = l
    return list(retenues.values()), {"lignes": nb, "doublons": nb - len(retenues), "anomalies": anomalies}


# ---------------------------------------------------------------- Classe d'actifs
# Mots-clés recherchés dans la classification de l'assureur (Cardif, Generali EUROPERF,
# catégorie Morningstar chez Vie Plus), dans cet ordre.
_MOTS_CLASSES = [
    ("structure", ("capital garanti", "capital protég", "capital protege", "fonds garantis", "garantie plancher", "fonds à horizon",
                   "maturité définie", "obligations à échéance")),
    ("monetaire", ("monétaire", "money market")),
    ("immobilier", ("immobilier", "real estate")),
    ("matieres_premieres", ("matières premières", "commodit")),
    ("alternatif", ("spéculatif", "alternatif", "alt -", "macro", "multistrategy", "market neutral",
                    "trading", "fcpr", "private equity")),
    ("mixte", ("mixte", "diversifié", "allocation", "flexible", "gestion à horizons")),
    ("obligations", ("obligation", "bond", "taux", "convertible", "crédit", "credit")),
    ("actions", ("action", "equity", "actions")),
]


def classe_assureur(classification: str | None, type_produit: str | None = None) -> str | None:
    """Classe d'actifs déduite de la classification de l'assureur (None si inconnue)."""
    if type_produit == "action":
        return "actions"
    if type_produit == "scpi":
        return "immobilier"
    texte = (classification or "").lower()
    for classe, mots in _MOTS_CLASSES:
        if any(m in texte for m in mots):
            return classe
    return None
