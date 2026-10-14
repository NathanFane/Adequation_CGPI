"""Calcul des métriques de risque et de performance à partir des VL ajustées.

Conventions :
- rendements quotidiens simples, 252 jours de bourse par an ;
- VaR Cornish-Fisher à 97,5 % sur 1 an, selon la formule PRIIPs (règlement délégué 2017/653),
  exprimée en perte positive (0,12 = perte de 12 %) ;
- taux sans risque : moyenne de l'€STR sur la période (BCE).
"""
import datetime as dt
import io
import math

import numpy as np
import pandas as pd
import requests

JOURS = 252
MIN_POINTS = 120  # environ 6 mois de VL quotidiennes
URL_ESTR = "https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT"


def taux_sans_risque(debut: dt.date) -> float | None:
    """Moyenne annuelle de l'€STR depuis `debut` (en décimal, ex. 0,025), ou None si indisponible."""
    try:
        r = requests.get(URL_ESTR, params={"startPeriod": debut.isoformat(), "format": "csvdata"}, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        return float(df["OBS_VALUE"].mean()) / 100
    except Exception:
        return None


def var_cornish_fisher(r: pd.Series, n: int = JOURS) -> float:
    """VaR 97,5 % à horizon n jours, méthode PRIIPs (catégorie 2)."""
    sigma = r.std(ddof=0)
    s = r.skew()          # asymétrie
    k = r.kurt()          # excès de kurtosis
    if sigma == 0 or np.isnan(s) or np.isnan(k):
        return 0.0
    z = -1.96 + 0.474 * s / math.sqrt(n) - 0.0687 * k / n + 0.146 * s ** 2 / n
    rendement = math.exp(sigma * math.sqrt(n) * z - 0.5 * sigma ** 2 * n) - 1
    return -rendement


def metriques(vl: pd.Series, rf: float | None) -> dict | None:
    """vl : VL ajustées indexées par date. Renvoie les métriques ou None si historique insuffisant."""
    vl = vl.dropna().sort_index()
    vl = vl[vl > 0]
    if len(vl) < MIN_POINTS:
        return None
    r = vl.pct_change().dropna()
    log_r = np.log(vl).diff().dropna()

    annees = len(r) / JOURS
    rendement = (vl.iloc[-1] / vl.iloc[0]) ** (1 / annees) - 1
    vol = r.std() * math.sqrt(JOURS)
    rf = rf or 0.0
    rf_jour = (1 + rf) ** (1 / JOURS) - 1
    baisse = np.minimum(r - rf_jour, 0)
    vol_baisse = math.sqrt((baisse ** 2).mean()) * math.sqrt(JOURS)

    return {
        "var_cf": round(float(var_cornish_fisher(log_r)), 6),
        "volatilite": round(float(vol), 6),
        "sharpe": round(float((rendement - rf) / vol), 4) if vol else None,
        "sortino": round(float((rendement - rf) / vol_baisse), 4) if vol_baisse else None,
    }


def lire_historique(db, isin: str, depuis: dt.date) -> pd.Series:
    """Lit les VL ajustées d'un produit (par pages de 1 000 lignes, limite de Supabase)."""
    lignes, debut = [], 0
    while True:
        page = (db.table("historique").select("date, vl, vl_ajustee").eq("isin", isin)
                .gte("date", depuis.isoformat()).order("date").range(debut, debut + 999).execute().data)
        lignes += page
        if len(page) < 1000:
            break
        debut += 1000
    if not lignes:
        return pd.Series(dtype=float)
    df = pd.DataFrame(lignes)
    valeurs = df["vl_ajustee"].fillna(df["vl"]).astype(float)
    return pd.Series(valeurs.values, index=pd.to_datetime(df["date"]))


def calculer_et_enregistrer(db, isins: list[str] | None = None, annees: int = 5) -> dict:
    """Calcule les métriques des produits valides et les enregistre (une ligne par produit et par jour)."""
    requete = db.table("produits").select("isin").eq("statut", "valide")
    if isins is not None:
        requete = requete.in_("isin", isins)
    produits = [p["isin"] for p in requete.execute().data]

    depuis = dt.date.today() - dt.timedelta(days=365 * annees)
    rf = taux_sans_risque(depuis)
    rapport = {"calcules": [], "insuffisants": [], "taux_sans_risque": rf}
    lignes = []
    for isin in produits:
        m = metriques(lire_historique(db, isin, depuis), rf)
        if m is None:
            rapport["insuffisants"].append(isin)
            continue
        lignes.append({"isin": isin, "date_calcul": dt.date.today().isoformat(), **m})
        rapport["calcules"].append(isin)
    if lignes:
        db.table("metriques").upsert(lignes, on_conflict="isin,date_calcul").execute()
    return rapport
