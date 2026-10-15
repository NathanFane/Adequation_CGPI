"""Lecture des fichiers EPT (European PRIIPs Template, format FinDatEx).

Même principe que l'EMT : colonnes repérées par leur code à 5 chiffres.
"""
import pandas as pd

from emt import _drapeau, _nombre, _oui, _texte, lire_fichier
from isin import est_valide, normaliser

NUMERIQUES = {
    "vev": "01020", "duree_detention_ans": "01120",
    "priips_moyenne": "02140", "priips_sigma": "02150", "priips_skewness": "02160",
    "priips_kurtosis": "02170", "volatilite_stress": "02180",
    "scenario_defavorable_1an": "02010", "scenario_defavorable_rhp": "02030",
    "scenario_intermediaire_1an": "02040", "scenario_intermediaire_rhp": "02060",
    "scenario_favorable_1an": "02070", "scenario_favorable_rhp": "02090",
    "scenario_tension_1an": "02100", "scenario_tension_rhp": "02120",
    "frais_entree": "03010", "frais_sortie_rhp": "03020",
    "frais_gestion_courants": "03060", "frais_transaction": "03080",
}
ENTIERS = {"sri": "01090", "mrm": "01100", "crm": "01110",
           "categorie_priips": "00080", "priips_nb_rendements": "02130"}
BORNES = {"sri": (1, 7), "mrm": (1, 7), "crm": (1, 6), "categorie_priips": (1, 4),
          "frais_entree": (0, 1), "frais_sortie_rhp": (0, 1),
          "frais_gestion_courants": (0, 0.2), "frais_transaction": (-0.05, 0.2),
          "duree_detention_ans": (0, 40), "vev": (0, 5)}


def convertir_ligne(l: pd.Series, anomalies: list) -> dict | None:
    g = lambda code: l.get(code)
    isin = normaliser(g("00030"))
    if not est_valide(isin):
        return None

    ligne = {"isin": isin}
    for champ, code in {**NUMERIQUES, **ENTIERS}.items():
        v = _nombre(g(code))
        if v is not None and champ in BORNES:
            bas, haut = BORNES[champ]
            if not bas <= v <= haut:
                anomalies.append(f"{isin} : {champ} hors limites ({g(code)}), ignoré")
                v = None
        if v is not None and champ in ENTIERS:
            v = int(v) if v == int(v) else None
        ligne[champ] = v

    date_dic = _texte(g("00070"))
    ligne.update({
        "nom": _texte(g("00050")),
        "devise": _texte(g("00060")),
        "societe_gestion": _texte(g("00010")),
        "date_dic": str(pd.to_datetime(date_dic).date()) if date_dic else None,
        "version_ept": _texte(g("00001")),
        "risque_liquidite": _drapeau(g("01140")),
        "garantie_capital": _oui(g("04080")),
        "alerte_comprehension": _oui(g("04020")),
    })
    return ligne


def extraire(chemins: list[str]) -> tuple[list[dict], dict]:
    """Lit plusieurs fichiers EPT. Pour un même ISIN, garde le DIC le plus récent."""
    retenues, anomalies, stats = {}, [], {"lignes": 0, "ignorees": 0}
    for chemin in chemins:
        df = lire_fichier(chemin)
        if "00030" not in df.columns:
            anomalies.append(f"{chemin} : colonne 00030 (ISIN) absente, fichier ignoré")
            continue
        for _, l in df.iterrows():
            stats["lignes"] += 1
            ligne = convertir_ligne(l, anomalies)
            if ligne is None:
                stats["ignorees"] += 1
                continue
            ligne["fichier_source"] = chemin.split("/")[-1]
            ancienne = retenues.get(ligne["isin"])
            if ancienne is None or (ligne["date_dic"] or "") >= (ancienne["date_dic"] or ""):
                retenues[ligne["isin"]] = ligne
    stats["anomalies"] = anomalies
    return list(retenues.values()), stats
