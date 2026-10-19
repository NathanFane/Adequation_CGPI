"""Calcul des métriques de risque et de performance à partir des VL ajustées.

Conventions :
- rendements quotidiens simples, 252 jours de bourse par an ;
- VaR Cornish-Fisher à 97,5 % sur 1 an, selon la formule PRIIPs (règlement délégué 2017/653),
  exprimée en perte positive (0,12 = perte de 12 %) ;
- taux sans risque : moyenne de l'€STR sur la période (BCE) ;
- mesures relatives à l'indice (R², bêta, alpha, tracking error, ratio d'information) sur les
  rendements hebdomadaires, comme la corrélation.
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

    # CVaR historique quotidienne : perte moyenne des 2,5 % pires jours
    seuil = r.quantile(0.025)
    pires = r[r <= seuil]
    cvar = -float(pires.mean())

    # Max Drawdown et temps de recouvrement (du point bas au retour au plus haut précédent)
    plus_haut = vl.cummax()
    baisse_depuis_haut = vl / plus_haut - 1
    date_bas = baisse_depuis_haut.idxmin()
    max_dd = -float(baisse_depuis_haut.min())
    date_haut = vl.loc[:date_bas].idxmax()
    apres = vl.loc[date_bas:]
    retour = apres[apres >= vl.loc[date_haut]]
    date_retour = retour.index[0] if len(retour) else None
    recouvrement = (date_retour - date_bas).days if date_retour is not None and max_dd > 0 else None

    # Sortino : volatilité des seuls rendements inférieurs au taux sans risque
    rf_jour = (1 + rf) ** (1 / JOURS) - 1
    baisse = np.minimum(r - rf_jour, 0)
    vol_baisse = math.sqrt((baisse ** 2).mean()) * math.sqrt(JOURS)

    # Rendements mensuels (fin de mois ; le premier mois, incomplet, est écarté)
    fin_mois = vl.resample("ME").last()
    r_mois = fin_mois.pct_change().dropna()
    # Pire année : pire performance sur 12 mois glissants (fins de mois)
    r_12m = (fin_mois / fin_mois.shift(12) - 1).dropna()

    # Performances sur 3 mois, 6 mois et 1 an : de la VL à la même date n mois plus tôt
    # (ou à la dernière VL connue avant) ; vide si l'historique ne remonte pas assez loin
    def perf(mois):
        depart = vl.index[-1] - pd.DateOffset(months=mois)
        if vl.index[0] > depart:
            return None
        return float(vl.iloc[-1] / vl.loc[:depart].iloc[-1] - 1)

    return {
        "debut": vl.index[0].date(), "fin": vl.index[-1].date(), "nb_vl": len(vl), "nb_rendements": len(r),
        "vl_debut": float(vl.iloc[0]), "vl_fin": float(vl.iloc[-1]), "annees": annees,
        "rendement": float(rendement), "vol_jour": float(vol_jour), "volatilite": float(vol),
        "sigma_log": float(sigma), "skew": float(s), "kurt": float(k), "n": n, "z": float(z),
        "var_rendement": float(var_rendement), "var_cf": float(var_cf),
        "seuil_cvar": float(seuil), "nb_pires": len(pires), "cvar": cvar,
        "max_drawdown": max_dd, "date_haut": date_haut.date(), "date_bas": date_bas.date(),
        "vl_haut": float(vl.loc[date_haut]), "vl_bas": float(vl.loc[date_bas]),
        "date_retour": date_retour.date() if date_retour is not None else None,
        "recouvrement_jours": recouvrement,
        "rf": rf, "rf_jour": rf_jour, "nb_baisse": int((baisse < 0).sum()), "vol_baisse": float(vol_baisse),
        "sharpe": float((rendement - rf) / vol) if vol else None,
        "sortino": float((rendement - rf) / vol_baisse) if vol_baisse else None,
        "calmar": float(rendement / max_dd) if max_dd else None,
        "nb_mois": len(r_mois), "nb_mois_positifs": int((r_mois > 0).sum()),
        "pct_mois_positifs": float((r_mois > 0).mean()) if len(r_mois) else None,
        "pire_mois": float(r_mois.min()) if len(r_mois) else None,
        "date_pire_mois": r_mois.idxmin().date() if len(r_mois) else None,
        "pire_annee": float(r_12m.min()) if len(r_12m) else None,
        "fin_pire_annee": r_12m.idxmin().date() if len(r_12m) else None,
        "perf_3m": perf(3), "perf_6m": perf(6), "perf_1an": perf(12),
        "historique_annees": (vl.index[-1] - vl.index[0]).days / 365.25,
    }


def relatif(vl: pd.Series, indice: pd.Series, rf: float | None) -> dict | None:
    """Mesures par rapport à l'indice retenu, sur les rendements hebdomadaires communes
    (au moins 26 semaines). `indice` = rendements hebdomadaires de l'indice. None si insuffisant."""
    if vl.empty or indice is None or indice.empty:
        return None
    paire = pd.concat([rendements_hebdo(vl.dropna().sort_index()).rename("p"), indice.rename("i")],
                      axis=1, join="inner").dropna()
    n = len(paire)
    if n < MIN_SEMAINES:
        return None
    rf = rf or 0.0
    p, i = paire["p"], paire["i"]
    rho = p.corr(i)
    beta = p.cov(i) / i.var() if i.var() else None
    # Rendements annualisés sur les semaines communes (52 semaines par an)
    r_p = float((1 + p).prod() ** (52 / n) - 1)
    r_i = float((1 + i).prod() ** (52 / n) - 1)
    alpha = r_p - (rf + beta * (r_i - rf)) if beta is not None else None
    te = float((p - i).std() * math.sqrt(52))
    return {
        "nb_semaines": n, "debut": paire.index[0].date(), "fin": paire.index[-1].date(),
        "rendement_produit": r_p, "rendement_indice": r_i, "rf": rf,
        "correlation": float(rho), "r2": float(rho ** 2), "beta": float(beta) if beta is not None else None,
        "alpha": float(alpha) if alpha is not None else None, "tracking_error": te,
        "ratio_information": float((r_p - r_i) / te) if te else None,
    }


def metriques(vl: pd.Series, rf: float | None) -> dict | None:
    """Métriques à enregistrer en base (mêmes calculs que `detail`)."""
    d = detail(vl, rf)
    if d is None:
        return None
    return {
        "rendement_annuel": round(d["rendement"], 6),
        "cvar": round(d["cvar"], 6),
        "max_drawdown": round(d["max_drawdown"], 6),
        "recouvrement_jours": d["recouvrement_jours"],
        "var_cf": round(d["var_cf"], 6),
        "volatilite": round(d["volatilite"], 6),
        "sharpe": round(d["sharpe"], 4) if d["sharpe"] is not None else None,
        "sortino": round(d["sortino"], 4) if d["sortino"] is not None else None,
        "calmar": _arrondi(d["calmar"], 4),
        "pct_mois_positifs": _arrondi(d["pct_mois_positifs"], 4),
        "pire_mois": _arrondi(d["pire_mois"], 6),
        "pire_annee": _arrondi(d["pire_annee"], 6),
        "skewness": _arrondi(d["skew"], 4),
        "kurtosis": _arrondi(d["kurt"], 4),
        "perf_3m": _arrondi(d["perf_3m"], 6),
        "perf_6m": _arrondi(d["perf_6m"], 6),
        "perf_1an": _arrondi(d["perf_1an"], 6),
        "historique_annees": _arrondi(d["historique_annees"], 1),
    }


def _arrondi(x, d):
    return None if x is None or not math.isfinite(x) else round(x, d)


def lire_historique(db, isin: str, depuis: dt.date) -> pd.Series:
    """Lit les VL ajustées d'un produit (par pages de 1 000 lignes, limite de Supabase)."""
    lignes, debut = [], 0
    while True:
        from collecte import executer
        page = executer(db.table("historique").select("date, vl, vl_ajustee").eq("isin", isin)
                        .gte("date", depuis.isoformat()).order("date").range(debut, debut + 999)).data
        lignes += page
        if len(page) < 1000:
            break
        debut += 1000
    if not lignes:
        return pd.Series(dtype=float)
    df = pd.DataFrame(lignes)
    valeurs = df["vl_ajustee"].fillna(df["vl"]).astype(float)
    return pd.Series(valeurs.values, index=pd.to_datetime(df["date"]))


MIN_SEMAINES = 26


def lire_indices(db) -> pd.DataFrame:
    """Cours de tous les ETF de référence : une colonne par ticker."""
    lignes, debut = [], 0
    while True:
        page = (db.table("indices_historique").select("ticker, date, valeur")
                .order("ticker").order("date").range(debut, debut + 999).execute().data)
        lignes += page
        if len(page) < 1000:
            break
        debut += 1000
    if not lignes:
        return pd.DataFrame()
    df = pd.DataFrame(lignes)
    df["date"] = pd.to_datetime(df["date"])
    return df.pivot(index="date", columns="ticker", values="valeur").astype(float)


def rendements_hebdo(serie: pd.Series | pd.DataFrame):
    """Rendements hebdomadaires (cours du vendredi) : évite le décalage d'un jour entre
    la VL d'un fonds et la clôture d'un ETF."""
    return serie.resample("W-FRI").last().pct_change(fill_method=None).iloc[1:]


def rendements_references(cours: pd.DataFrame) -> pd.DataFrame:
    """Rendements hebdomadaires de chaque indice de référence (mixtes rééquilibrés chaque semaine)."""
    from indices import REFERENCES
    if cours.empty:
        return pd.DataFrame()
    hebdo = rendements_hebdo(cours)
    colonnes = {}
    for ref in REFERENCES:
        tickers = list(ref["composition"])
        if not all(t in hebdo.columns for t in tickers):
            continue
        poids = pd.Series(ref["composition"])
        colonnes[ref["code"]] = (hebdo[tickers] * poids[tickers]).sum(axis=1, min_count=len(tickers))
    return pd.DataFrame(colonnes)


def correlations(vl: pd.Series, refs: pd.DataFrame) -> pd.Series:
    """Corrélation des rendements hebdomadaires du produit avec chaque indice (au moins 26 semaines communes)."""
    if refs.empty or vl.empty:
        return pd.Series(dtype=float)
    r = rendements_hebdo(vl).rename("produit")
    jointure = refs.join(r, how="inner")
    res = {}
    for code in refs.columns:
        paire = jointure[[code, "produit"]].dropna()
        if len(paire) >= MIN_SEMAINES:
            res[code] = paire[code].corr(paire["produit"])
    return pd.Series(res).sort_values(ascending=False)


def calculer_et_enregistrer(db, isins: list[str] | None = None, annees: int = 5) -> dict:
    """Calcule les métriques des produits valides et les enregistre (une ligne par produit et par jour).

    L'indice de référence de chaque produit est celui qui lui est le plus corrélé, sauf s'il a été
    choisi à la main par un CGPI.
    """
    from collecte import _tout, executer
    from indices import SEUIL_ZONE, classe_indice, zone_indice

    requete = (db.table("produits").select("isin, indice_reference, indice_manuel, classe_actifs, classe_source, zone")
               .eq("statut", "valide"))
    if isins is not None:
        requete = requete.in_("isin", isins)
    produits = _tout(requete)

    depuis = dt.date.today() - dt.timedelta(days=365 * annees)
    rf = taux_sans_risque(depuis)
    refs = rendements_references(lire_indices(db))
    rapport = {"calcules": [], "insuffisants": [], "taux_sans_risque": rf}
    lignes = []
    for n, p in enumerate(produits, 1):
        if len(lignes) >= 200:   # enregistrement au fil de l'eau : une coupure ne perd pas tout le calcul
            executer(db.table("metriques").upsert(lignes, on_conflict="isin,date_calcul"))
            lignes = []
        try:
            vl = lire_historique(db, p["isin"], depuis)
        except Exception as e:   # un produit illisible ne doit pas arrêter le calcul des autres
            rapport.setdefault("erreurs", []).append(f"{p['isin']} : {e}")
            continue
        m = metriques(vl, rf)
        if m is None:
            rapport["insuffisants"].append(p["isin"])
            continue
        corr = correlations(vl, refs)
        indice = p["indice_reference"] if p["indice_manuel"] else (corr.index[0] if len(corr) else None)
        rho = float(corr[indice]) if indice in corr.index else None
        # Zone (et classe, si l'assureur ne la donne pas) déduites de l'indice : seulement si la
        # corrélation est assez forte, ou si l'indice a été choisi à la main par le CGPI
        fiable = p["indice_manuel"] or (rho is not None and rho >= SEUIL_ZONE)
        maj = {}
        if not p["indice_manuel"] and indice != p["indice_reference"]:
            maj["indice_reference"] = indice
        zone = zone_indice(indice) if fiable else "Indéterminée"
        if zone != p["zone"]:
            maj["zone"] = zone
        if p["classe_source"] != "assureur":
            classe = classe_indice(indice) if fiable else None
            if classe != p["classe_actifs"]:
                maj.update({"classe_actifs": classe, "classe_source": "indice" if classe else None})
        if maj:
            executer(db.table("produits").update(maj).eq("isin", p["isin"]))
        m["indice_reference"] = indice
        m["correlation_indice"] = round(rho, 4) if rho is not None else None
        rel = relatif(vl, refs[indice], rf) if indice in refs.columns else None
        for champ, d in (("r2", 4), ("beta", 4), ("alpha", 6), ("tracking_error", 6), ("ratio_information", 4)):
            m[champ] = _arrondi(rel[champ], d) if rel and rel[champ] is not None else None
        lignes.append({"isin": p["isin"], "date_calcul": dt.date.today().isoformat(), **m})
        rapport["calcules"].append(p["isin"])
    for i in range(0, len(lignes), 500):
        executer(db.table("metriques").upsert(lignes[i:i + 500], on_conflict="isin,date_calcul"))
    return rapport
