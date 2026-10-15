"""Récupération des VL via EODHD et enregistrement dans la table historique.

Utilisé par le bouton « Récupérer les données » du site et par la tâche quotidienne.
"""
import datetime as dt

import requests

BASE = "https://eodhd.com/api"
PROFONDEUR_ANS = 5  # historique demandé au premier chargement (limité à 1 an en offre gratuite)


class LimiteAtteinte(Exception):
    """Quota de requêtes EODHD épuisé ou clé refusée."""


# Budget d'appels de la tâche en cours (None = illimité). Compté avant chaque appel.
QUOTA = None
APPELS = 0


def _get(chemin: str, cle: str, **params):
    global APPELS
    if QUOTA is not None and APPELS >= QUOTA:
        raise LimiteAtteinte(f"budget de {QUOTA} appels EODHD atteint pour aujourd'hui")
    APPELS += 1
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
    return chercher_ticker(isin, cle)


def chercher_ticker(isin: str, cle: str) -> str | None:
    """Recherche EODHD par ISIN (ETF, actions, fonds absents de EUFUND)."""
    resultats = _get(f"search/{isin}", cle) or []
    if not resultats:
        return None
    resultats.sort(key=lambda x: (x.get("Exchange") != "PA", x.get("Exchange") == "EUFUND"))
    x = resultats[0]
    return f"{x['Code']}.{x['Exchange']}"


def mettre_a_jour(db, cle: str, isins: list[str] | None = None, progression=None,
                  anciennete_max: int = 1) -> dict:
    """Met à jour l'historique des produits valides (tous, ou seulement `isins`).

    Ne télécharge que les VL postérieures à la dernière date connue, et seulement pour les
    produits dont la dernière VL date de plus de `anciennete_max` jours (les plus anciennes d'abord).
    Renvoie un compte rendu {"maj": [...], "sans_donnees": [...], "erreur": str | None}.
    """
    requete = (db.table("produits").select("isin, nom, type_produit, ticker_eodhd, derniere_vl")
               .eq("statut", "valide").is_("ticker_yahoo", "null")   # EODHD : secours de Yahoo
               .order("derniere_vl", desc=False, nullsfirst=True))
    if isins is not None:
        requete = requete.in_("isin", isins)
    produits = requete.execute().data

    rapport = {"maj": [], "sans_donnees": [], "erreur": None}
    aujourd_hui = dt.date.today()
    for n, p in enumerate(produits, 1):
        if progression:
            progression(n / max(len(produits), 1), p["nom"] or p["isin"])
        if p["derniere_vl"] and p["derniere_vl"] >= (aujourd_hui - dt.timedelta(days=anciennete_max)).isoformat():
            continue  # assez récent
        try:
            debut = (dt.date.fromisoformat(p["derniere_vl"]) + dt.timedelta(days=1) if p["derniere_vl"]
                     else aujourd_hui - dt.timedelta(days=365 * PROFONDEUR_ANS))
            ticker, vl = p["ticker_eodhd"], None
            if not ticker and p["type_produit"] in (None, "fonds", "autre"):
                # Fonds : on demande directement l'historique complet (1 appel au lieu de 2)
                vl = _get(f"eod/{p['isin']}.EUFUND", cle, **{"from": debut.isoformat()})
                ticker = f"{p['isin']}.EUFUND" if vl else None
            if not ticker:
                ticker = chercher_ticker(p["isin"], cle)
            if not ticker:
                rapport["sans_donnees"].append(p["isin"])
                continue
            if vl is None:
                vl = _get(f"eod/{ticker}", cle, **{"from": debut.isoformat()}) or []
        except LimiteAtteinte as e:
            rapport["erreur"] = str(e)
            break

        lignes = [{"isin": p["isin"], "date": v["date"], "vl": v["close"],
                   "vl_ajustee": v.get("adjusted_close", v["close"])}
                  for v in vl if v.get("close") is not None]
        for i in range(0, len(lignes), 500):
            db.table("historique").upsert(lignes[i:i + 500], on_conflict="isin,date").execute()

        maj = {"ticker_eodhd": ticker, "source_vl": "eodhd"}
        if lignes:
            maj["derniere_vl"] = max(l["date"] for l in lignes)
            rapport["maj"].append((p["isin"], len(lignes)))
        elif not p["derniere_vl"]:
            rapport["sans_donnees"].append(p["isin"])
        db.table("produits").update(maj).eq("isin", p["isin"]).execute()
    return rapport


def _tout(requete, taille=1000):
    """Lit toutes les lignes d'une requête Supabase (pagination par 1000)."""
    lignes, debut = [], 0
    while True:
        lot = requete.range(debut, debut + taille - 1).execute().data
        lignes += lot
        if len(lot) < taille:
            return lignes
        debut += taille


def actualiser(db, cle: str, isins: list[str] | None = None, progression=None, anciennete_eodhd: int = 1) -> dict:
    """Yahoo Finance d'abord (recherche du ticker si besoin), EODHD pour les produits absents de Yahoo."""
    import yahoo

    def requete(colonnes):
        q = db.table("produits").select(colonnes).eq("statut", "valide")
        return q.in_("isin", isins) if isins is not None else q

    # 1. Recherche des tickers Yahoo jamais cherchés
    a_chercher = _tout(requete("isin, nom").is_("ticker_yahoo", "null").eq("absent_yahoo", False))
    for n, p in enumerate(a_chercher, 1):
        if progression:
            progression(n / max(len(a_chercher), 1), f"Recherche Yahoo : {p['nom'] or p['isin']}")
        t = yahoo.chercher(p["isin"])
        db.table("produits").update({"ticker_yahoo": t} if t else {"absent_yahoo": True}).eq("isin", p["isin"]).execute()

    # 2. VL Yahoo
    produits = _tout(requete("isin, ticker_yahoo, derniere_vl, source_vl").not_.is_("ticker_yahoo", "null"))
    ry = yahoo.mettre_a_jour(db, produits, progression)
    if ry["sans_donnees"]:   # ticker trouvé mais sans cours : retour à EODHD
        db.table("produits").update({"ticker_yahoo": None, "absent_yahoo": True}).in_("isin", ry["sans_donnees"]).execute()

    # 3. EODHD pour les autres (dans la limite du quota)
    try:
        re_ = mettre_a_jour(db, cle, isins, progression, anciennete_max=anciennete_eodhd)
    except LimiteAtteinte as e:
        re_ = {"maj": [], "sans_donnees": [], "erreur": str(e)}
    return {"maj": ry["maj"] + re_["maj"], "sans_donnees": re_["sans_donnees"], "erreur": re_["erreur"],
            "recharges": ry["recharges"]}


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
