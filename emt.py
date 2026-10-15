"""Lecture des fichiers EMT (European MiFID Template, format FinDatEx).

Les colonnes sont repérées par leur code à 5 chiffres (ex. 07100), jamais par leur nom ni leur
position : le code est stable d'une société de gestion et d'une version à l'autre.
"""
import re

import pandas as pd

from isin import est_valide, normaliser

NIVEAUX_CONNAISSANCE = [("02010", "debutant"), ("02020", "informe"), ("02030", "avance")]
NIVEAUX_PERTE = [("03010", "aucune"), ("03020", "limitee"), ("03040", "capital"), ("03050", "au_dela")]
# Durée de détention exprimée en lettres dans certains fichiers (borne basse retenue)
DUREES_CODEES = {"VS": 0.5, "S": 1, "M": 3, "L": 5}
# Champ 00060 : type de produit
CATEGORIES = {"U": "opcvm", "UM": "opcvm_monetaire", "N": "fia", "NM": "fia_monetaire", "ETC": "etc"}


def lire_fichier(chemin: str) -> pd.DataFrame:
    """Lit l'onglet « Data » (ou le premier onglet) d'un Excel, ou un CSV. Colonnes renommées en codes."""
    if chemin.lower().endswith(".csv"):
        df = pd.read_csv(chemin, sep=None, engine="python", dtype=str)
    else:
        feuilles = pd.ExcelFile(chemin).sheet_names
        df = pd.read_excel(chemin, sheet_name="Data" if "Data" in feuilles else feuilles[0], dtype=str)
    codes = {}
    for col in df.columns:
        m = re.match(r"^\s*(\d{5})", str(col))
        if m and m.group(1) not in codes.values():
            codes[col] = m.group(1)
    return df[list(codes)].rename(columns=codes)


def _texte(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    v = str(v).strip()
    return v or None


def _drapeau(v):
    v = _texte(v)
    return v.upper() if v else None


def _nombre(v):
    v = _texte(v)
    if v is None:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def _oui(v):
    v = _drapeau(v)
    return True if v == "Y" else False if v == "N" else None


def convertir_ligne(l: pd.Series, anomalies: list) -> dict | None:
    """Transforme une ligne EMT en ligne de la table donnees_emt (None si la ligne est à ignorer)."""
    g = lambda code: l.get(code)
    isin = normaliser(g("00010"))
    if not est_valide(isin):
        return None
    if _drapeau(g("01010")) != "Y":           # parts non ouvertes aux particuliers
        return None

    def alerte(msg):
        anomalies.append(f"{isin} : {msg}")

    connaissance = next((niv for code, niv in NIVEAUX_CONNAISSANCE if _drapeau(g(code)) == "Y"), None)
    perte = next((niv for code, niv in NIVEAUX_PERTE if _drapeau(g(code)) == "Y"), None)

    sri = _nombre(g("04010"))
    if sri is not None and (sri != int(sri) or not 1 <= sri <= 7):
        alerte(f"SRI invalide ({g('04010')}), ignoré")
        sri = None

    brut = _texte(g("05080"))
    duree = _nombre(brut)
    if duree is None and brut:
        duree = DUREES_CODEES.get(brut.upper())
    if duree is not None and not 0 <= duree <= 40:
        alerte(f"durée de détention invalide ({brut}), ignorée")
        duree = None

    frais = {}
    for champ, code in [("frais_entree_max", "07020"), ("frais_sortie_max", "07050"),
                        ("frais_courants", "07100"), ("frais_gestion", "07110"), ("frais_transaction", "07130")]:
        v = _nombre(g(code))
        borne = 0.2 if champ in ("frais_courants", "frais_gestion", "frais_transaction") else 1
        if v is not None and not -0.05 <= v <= borne:   # frais de transaction parfois légèrement négatifs
            alerte(f"{champ} hors limites ({g(code)}), probablement exprimé en % au lieu de décimal : ignoré")
            v = None
        frais[champ] = v

    code_type = _drapeau(g("00060"))
    categorie = CATEGORIES.get(code_type) if code_type else None
    if code_type and categorie is None:
        alerte(f"type de produit non reconnu ({code_type}), classé « autre »")
        categorie = "autre"

    date_ref = _texte(g("00050"))
    return {
        "isin": isin,
        "nom": _texte(g("00030")),
        "devise": _texte(g("00040")),
        "societe_gestion": _texte(g("00070")),
        "date_reference": str(pd.to_datetime(date_ref).date()) if date_ref else None,
        "version_emt": _texte(g("00001")),
        "categorie_emt": categorie,
        "connaissance_min": connaissance,
        "perte_acceptable_min": perte,
        "perte_limitee_niveau": _nombre(g("03030")),
        "sri": int(sri) if sri is not None else None,
        "duree_detention_ans": duree,
        "objectif_preservation": _drapeau(g("05010")),
        "objectif_croissance": _drapeau(g("05020")),
        "objectif_revenus": _drapeau(g("05030")),
        "durabilite": _drapeau(g("05105")),
        **frais,
        "commission_performance": _oui(g("00045")),
        "distribution": _oui(g("00047")),
        "levier": _oui(g("00100")),
    }


def extraire(chemins: list[str]) -> tuple[list[dict], dict]:
    """Lit plusieurs fichiers. Pour un même ISIN, garde la donnée la plus récente."""
    retenues, anomalies, stats = {}, [], {"lignes": 0, "ignorees": 0}
    for chemin in chemins:
        df = lire_fichier(chemin)
        if "00010" not in df.columns:
            anomalies.append(f"{chemin} : colonne 00010 (ISIN) absente, fichier ignoré")
            continue
        for _, l in df.iterrows():
            stats["lignes"] += 1
            ligne = convertir_ligne(l, anomalies)
            if ligne is None:
                stats["ignorees"] += 1
                continue
            ligne["fichier_source"] = chemin.split("/")[-1]
            ancienne = retenues.get(ligne["isin"])
            if ancienne is None or (ligne["date_reference"] or "") >= (ancienne["date_reference"] or ""):
                retenues[ligne["isin"]] = ligne
    stats["anomalies"] = anomalies
    return list(retenues.values()), stats
