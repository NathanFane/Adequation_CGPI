"""Filtres combinables (ET / OU) sur un tableau de produits.

Structure : des groupes de critères.
- Dans un critère : plusieurs valeurs d'un même indicateur (ex. Zone = France OU Monde).
- Dans un groupe : les critères sont reliés par ET ou par OU (au choix pour chaque groupe).
- Entre les groupes : ET ou OU (un seul choix, pour éviter toute ambiguïté de priorité).
"""
import numpy as np
import pandas as pd

# Indicateurs filtrables : nom de colonne -> type ("liste" ou "nombre") ; pourcent = saisie en %
LISTES = ["Classe d'actifs", "Zone", "Contrats", "Type", "SFDR", "Label ISR"]
NOMBRES = {  # colonne: (en pourcentage ?)
    "SRI": False, "Frais du fonds": True, "Rendement annuel": True, "Volatilité": True,
    "VaR 97,5 % 1 an": True, "Max Drawdown": True, "Sharpe": False, "Sortino": False,
    "Corrélation à l'indice": False,
}
EGAL, DIFFERENT = "égal à l'une des valeurs suivantes", "différent des valeurs suivantes"
DANS_UN, DANS_TOUS, ABSENT = ("présent dans l'un des contrats suivants", "présent dans tous les contrats suivants",
                              "absent des contrats suivants")
SUP, SUP_EG, INF, INF_EG, ENTRE, HORS = ("supérieur à", "supérieur ou égal à", "inférieur à", "inférieur ou égal à",
                                         "compris entre", "en dehors de")
OPERATEURS_LISTE = [EGAL, DIFFERENT]
OPERATEURS_LISTE_MULTIPLE = [DANS_UN, DANS_TOUS, ABSENT]   # Contrats
OPERATEURS_NOMBRE = [SUP, SUP_EG, INF, INF_EG, ENTRE, HORS]
SYMBOLES = {SUP: ">", SUP_EG: "≥", INF: "<", INF_EG: "≤"}
MULTIPLES = {"Contrats"}   # colonnes contenant plusieurs valeurs séparées par « , »


def valeurs_possibles(df: pd.DataFrame, colonne: str) -> list:
    if colonne in MULTIPLES:
        return sorted({v for x in df[colonne].dropna() for v in str(x).split(", ") if v})
    if colonne == "Label ISR":
        return ["Oui", "Non"]
    return sorted({str(v) for v in df[colonne].dropna()})


def _masque_critere(df: pd.DataFrame, c: dict) -> pd.Series:
    col, op, vals = c["indicateur"], c["operateur"], c["valeurs"]
    if col in NOMBRES:
        x = pd.to_numeric(df[col], errors="coerce")
        f = (lambda v: v / 100) if NOMBRES[col] else (lambda v: v)
        a = f(vals[0]) if vals and vals[0] is not None else None
        b = f(vals[1]) if len(vals) > 1 and vals[1] is not None else None
        if a is None:
            return pd.Series(True, index=df.index)
        b = a if b is None else b
        m = {SUP: x > a, SUP_EG: x >= a, INF: x < a, INF_EG: x <= a,
             ENTRE: x.between(min(a, b), max(a, b)), HORS: ~x.between(min(a, b), max(a, b))}[op]
        return m & x.notna()   # une valeur manquante ne satisfait jamais un critère chiffré
    if not vals:
        return pd.Series(True, index=df.index)
    if col == "Label ISR":
        x = df[col].map(lambda v: "Oui" if v is True else "Non")
    else:
        x = df[col].astype(str)
    if col in MULTIPLES:
        ens = x.map(lambda v: set(v.split(", ")))
        if op == DANS_TOUS:
            return ens.map(lambda s: set(vals) <= s)
        trouve = ens.map(lambda s: bool(s & set(vals)))
        return ~trouve if op == ABSENT else trouve
    dedans = x.isin(vals)
    return ~dedans if op == DIFFERENT else dedans


def appliquer(df: pd.DataFrame, groupes: list, lien_groupes: str = "ET") -> pd.DataFrame:
    """groupes = [{"lien": "ET"|"OU", "criteres": [{"indicateur", "operateur", "valeurs"}]}]."""
    masques = []
    for g in groupes:
        ms = [_masque_critere(df, c) for c in g["criteres"]]
        if ms:
            masques.append(np.logical_and.reduce(ms) if g["lien"] == "ET" else np.logical_or.reduce(ms))
    if not masques:
        return df
    total = np.logical_and.reduce(masques) if lien_groupes == "ET" else np.logical_or.reduce(masques)
    return df[total]


def decrire(groupes: list, lien_groupes: str = "ET") -> str:
    """Formule lisible, ex. (Zone = France ou Monde) ET (Volatilité > 2 % OU Max Drawdown entre 20 % et 30 %)."""
    def nombre(col, v):
        return f"{v:g} %" if NOMBRES[col] else f"{v:g}"

    def critere(c):
        col, op, vals = c["indicateur"], c["operateur"], c["valeurs"]
        if col in NOMBRES:
            if op in (ENTRE, HORS):
                return f"{col} {op} {nombre(col, vals[0])} et {nombre(col, vals[1])}"
            return f"{col} {SYMBOLES[op]} {nombre(col, vals[0])}"
        lien = " et " if op == DANS_TOUS else " ou "
        neg = "≠" if op in (DIFFERENT, ABSENT) else "="
        return f"{col} {neg} {lien.join(vals)}"

    morceaux = []
    for g in groupes:
        cs = [critere(c) for c in g["criteres"] if c["valeurs"] and c["valeurs"][0] is not None]
        if cs:
            morceaux.append("(" + f" {g['lien']} ".join(cs) + ")")
    return f" {lien_groupes} ".join(morceaux)
