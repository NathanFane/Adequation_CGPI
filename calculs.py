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


def detail(vl: pd.Series, rf: float | None) -> dict | None:
    """Toutes les étapes du calcul, pour l'affichage pas à pas. None si historique insuffisant."""
    vl = vl.dropna().sort_index()
    vl = vl[vl > 0]
    if len(vl) < MIN_POINTS:
        return None
    r = vl.pct_change().dropna()
    log_r = np.log(vl).diff().dropna()
    rf = rf or 0.0

    # Rendement et volatilité
    annees = len(r) / JOURS
    rendement = (vl.iloc[-1] / vl.iloc[0]) ** (1 / annees) - 1
    vol_jour = r.std()
    vol = vol_jour * math.sqrt(JOURS)

    # VaR Cornish-Fisher (PRIIPs), sur les rendements logarithmiques
    n = JOURS
    sigma = log_r.std(ddof=0)
    s = log_r.skew()
    k = log_r.kurt()
    z = -1.96 + 0.474 * s / math.sqrt(n) - 0.0687 * k / n + 0.146 * s ** 2 / n
    var_rendement = sigma * math.sqrt(n) * z - 0.5 * sigma ** 2 * n
    var_cf = -(math.exp(var_rendement) - 1) if sigma else 0.0

    # Sortino : volatilité des seuls rendements inférieurs au taux sans risque
    rf_jour = (1 + rf) ** (1 / JOURS) - 1
    baisse = np.minimum(r - rf_jour, 0)
    vol_baisse = math.sqrt((baisse ** 2).mean()) * math.sqrt(JOURS)

    return {
        "debut": vl.index[0].date(), "fin": vl.index[-1].date(), "nb_vl": len(vl), "nb_rendements": len(r),
        "vl_debut": float(vl.iloc[0]), "vl_fin": float(vl.iloc[-1]), "annees": annees,
        "rendement": float(rendement), "vol_jour": float(vol_jour), "volatilite": float(vol),
        "sigma_log": float(sigma), "skew": float(s), "kurt": float(k), "n": n, "z": float(z),
        "var_rendement": float(var_rendement), "var_cf": float(var_cf),
        "rf": rf, "rf_jour": rf_jour, "nb_baisse": int((baisse < 0).sum()), "vol_baisse": float(vol_baisse),
        "sharpe": float((rendement - rf) / vol) if vol else None,
        "sortino": float((rendement - rf) / vol_baisse) if vol_baisse else None,
    }


def metriques(vl: pd.Series, rf: float | None) -> dict | None:
    """Métriques à enregistrer en base (mêmes calculs que `detail`)."""
    d = detail(vl, rf)
    if d is None:
        return None
    return {
        "var_cf": round(d["var_cf"], 6),
        "volatilite": round(d["volatilite"], 6),
        "sharpe": round(d["sharpe"], 4) if d["sharpe"] is not None else None,
        "sortino": round(d["sortino"], 4) if d["sortino"] is not None else None,
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
