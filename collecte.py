"""Récupération des VL via EODHD et enregistrement dans la table historique.

Utilisé par le bouton « Récupérer les données » du site et par la tâche quotidienne.
"""
import datetime as dt

import requests

BASE = "https://eodhd.com/api"
PROFONDEUR_ANS = 5  # historique demandé au premier chargement (limité à 1 an en offre gratuite)


class LimiteAtteinte(Exception):
    """Quota de requêtes EODHD épuisé ou clé refusée."""


def _get(chemin: str, cle: str, **params):
    r = requests.get(f"{BASE}/{chemin}", params={"api_token": cle, "fmt": "json", **params}, timeout=30)
    if r.status_code in (401, 402, 403, 429):
        raise LimiteAtteinte(f"EODHD a refusé la requête ({r.status_code}) : {r.text[:120]}")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def trouver_ticker(isin: str, type_produit: str | None, cle: str) -> str | None:
    """Fonds : ISIN.EUFUND. ETF et actions : cotation à Paris en priorité."""
    if type_produit in (None, "fonds", "autre"):
        if _get(f"eod/{isin}.EUFUND", cle, **{"from": (dt.date.today() - dt.timedelta(days=10)).isoformat()}):
            return f"{isin}.EUFUND"
    resultats = _get(f"search/{isin}", cle) or []
    if not resultats:
        return None
    resultats.sort(key=lambda x: (x.get("Exchange") != "PA", x.get("Exchange") == "EUFUND"))
    x = resultats[0]
    return f"{x['Code']}.{x['Exchange']}"


def mettre_a_jour(db, cle: str, isins: list[str] | None = None, progression=None) -> dict:
    """Met à jour l'historique des produits valides (tous, ou seulement `isins`).

    Ne télécharge que les VL postérieures à la dernière date connue.
    Renvoie un compte rendu {"maj": [...], "sans_donnees": [...], "erreur": str | None}.
    """
    requete = db.table("produits").select("isin, nom, type_produit, ticker_eodhd, derniere_vl").eq("statut", "valide")
    if isins is not None:
        requete = requete.in_("isin", isins)
    produits = requete.execute().data

    rapport = {"maj": [], "sans_donnees": [], "erreur": None}
    aujourd_hui = dt.date.today()
    for n, p in enumerate(produits, 1):
        if progression:
            progression(n / max(len(produits), 1), p["nom"] or p["isin"])
        if p["derniere_vl"] and p["derniere_vl"] >= (aujourd_hui - dt.timedelta(days=1)).isoformat():
            continue  # déjà à jour
        try:
            ticker = p["ticker_eodhd"] or trouver_ticker(p["isin"], p["type_produit"], cle)
            if not ticker:
                rapport["sans_donnees"].append(p["isin"])
                continue
            debut = (dt.date.fromisoformat(p["derniere_vl"]) + dt.timedelta(days=1) if p["derniere_vl"]
                     else aujourd_hui - dt.timedelta(days=365 * PROFONDEUR_ANS))
            vl = _get(f"eod/{ticker}", cle, **{"from": debut.isoformat()}) or []
        except LimiteAtteinte as e:
            rapport["erreur"] = str(e)
            break

        lignes = [{"isin": p["isin"], "date": v["date"], "vl": v["close"],
                   "vl_ajustee": v.get("adjusted_close", v["close"])}
                  for v in vl if v.get("close") is not None]
        for i in range(0, len(lignes), 500):
            db.table("historique").upsert(lignes[i:i + 500], on_conflict="isin,date").execute()

        maj = {"ticker_eodhd": ticker}
        if lignes:
            maj["derniere_vl"] = max(l["date"] for l in lignes)
            rapport["maj"].append((p["isin"], len(lignes)))
        elif not p["derniere_vl"]:
            rapport["sans_donnees"].append(p["isin"])
        db.table("produits").update(maj).eq("isin", p["isin"]).execute()
    return rapport


def mettre_a_jour_indices(db) -> dict:
    """Télécharge les cours des ETF de référence (yfinance, dividendes réinvestis)."""
    import pandas as pd
    import yfinance as yf

    from indices import TICKERS

    # Téléchargement complet à chaque fois : les cours ajustés des dates passées changent
    # à chaque détachement de dividende, une mise à jour partielle créerait des ruptures.
    rapport = {"maj": 0, "echecs": []}
    lots = [(TICKERS, dt.date.today() - dt.timedelta(days=365 * PROFONDEUR_ANS))]

    for tickers, debut in lots:
        df = yf.download(tickers, start=debut.isoformat(), auto_adjust=True, progress=False,
                         group_by="ticker", threads=True)
        for t in tickers:
            try:
                serie = (df[t]["Close"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]).dropna()
            except KeyError:
                serie = pd.Series(dtype=float)
            if serie.empty:
                rapport["echecs"].append(t)
                continue
            lignes = [{"ticker": t, "date": d.date().isoformat(), "valeur": round(float(v), 6)}
                      for d, v in serie.items()]
            for i in range(0, len(lignes), 1000):
                db.table("indices_historique").upsert(lignes[i:i + 1000], on_conflict="ticker,date").execute()
            rapport["maj"] += len(lignes)
    return rapport
