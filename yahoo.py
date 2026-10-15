"""VL via Yahoo Finance (yfinance) : source principale, gratuite et sans quota journalier fixe.

Limites : API non officielle (peut casser sans préavis), VL des fonds issues de Morningstar
avec parfois quelques jours de retard, usage personnel / académique uniquement.
"""
import datetime as dt

import pandas as pd
import yfinance as yf

PROFONDEUR_ANS = 5
CHEVAUCHEMENT_JOURS = 10   # VL déjà connues retéléchargées pour vérifier la continuité
ECART_MAX = 0.005          # au-delà de 0,5 % d'écart sur les VL ajustées : rechargement complet
LOT = 100                  # tickers par téléchargement groupé


def chercher(isin: str) -> str | None:
    """Ticker Yahoo correspondant à un ISIN (cotation à Paris en priorité)."""
    try:
        quotes = [q for q in yf.Search(isin, max_results=5).quotes if q.get("symbol")]
    except Exception:
        return None
    if not quotes:
        return None
    quotes.sort(key=lambda q: not q["symbol"].endswith(".PA"))
    return quotes[0]["symbol"]


def _telecharger(tickers: list[str], debut: dt.date) -> dict[str, pd.DataFrame]:
    """{ticker: DataFrame(Close, Adj Close)} pour un lot de tickers."""
    df = yf.download(tickers, start=debut.isoformat(), auto_adjust=False, actions=False,
                     group_by="ticker", threads=True, progress=False)
    resultat = {}
    for t in tickers:
        try:
            d = df[t] if isinstance(df.columns, pd.MultiIndex) else df
            d = d[["Close", "Adj Close"]].dropna(subset=["Close"])
        except KeyError:
            continue
        if not d.empty:
            resultat[t] = d
    return resultat


def _lignes(isin, d: pd.DataFrame, depuis: dt.date):
    d = d[d.index.date >= depuis]
    return [{"isin": isin, "date": i.date().isoformat(), "vl": round(float(r["Close"]), 6),
             "vl_ajustee": round(float(r["Adj Close"]), 6) if pd.notna(r["Adj Close"]) else None}
            for i, r in d.iterrows()]


def _enregistrer(db, lignes):
    for i in range(0, len(lignes), 1000):
        db.table("historique").upsert(lignes[i:i + 1000], on_conflict="isin,date").execute()


def mettre_a_jour(db, produits: list[dict], progression=None) -> dict:
    """Met à jour les VL des produits ayant un ticker Yahoo.

    `produits` : lignes de la table produits (isin, ticker_yahoo, derniere_vl, source_vl).
    Téléchargement incrémental avec contrôle de continuité ; rechargement complet si la série
    ajustée a changé (dividende détaché) ou si le produit venait d'une autre source.
    """
    rapport = {"maj": [], "sans_donnees": [], "recharges": []}
    aujourd_hui = dt.date.today()
    origine = aujourd_hui - dt.timedelta(days=365 * PROFONDEUR_ANS)
    produits = [p for p in produits if p.get("ticker_yahoo")]

    for n in range(0, len(produits), LOT):
        lot = produits[n:n + LOT]
        if progression:
            progression(n / max(len(produits), 1), f"Yahoo Finance : produits {n + 1} à {n + len(lot)}")
        complets = [p for p in lot if not p["derniere_vl"] or p.get("source_vl") != "yahoo"]
        increm = [p for p in lot if p not in complets]
        a_faire = []   # (produit, données, rechargement complet ?)
        if complets:
            d = _telecharger([p["ticker_yahoo"] for p in complets], origine)
            a_faire += [(p, d.get(p["ticker_yahoo"]), True) for p in complets]
        if increm:
            debut = min(dt.date.fromisoformat(p["derniere_vl"]) for p in increm) - dt.timedelta(days=CHEVAUCHEMENT_JOURS)
            d = _telecharger([p["ticker_yahoo"] for p in increm], debut)
            a_faire += [(p, d.get(p["ticker_yahoo"]), False) for p in increm]

        for p, d, complet in a_faire:
            if d is None:
                if complet:
                    rapport["sans_donnees"].append(p["isin"])
                continue
            if not complet:
                # Continuité : les VL ajustées déjà en base doivent correspondre aux nouvelles
                derniere = dt.date.fromisoformat(p["derniere_vl"])
                anciennes = (db.table("historique").select("date, vl_ajustee").eq("isin", p["isin"])
                             .gte("date", (derniere - dt.timedelta(days=CHEVAUCHEMENT_JOURS)).isoformat())
                             .execute().data)
                nouvelles = {i.date().isoformat(): v for i, v in d["Adj Close"].items()}
                ecarts = [abs(nouvelles[a["date"]] / float(a["vl_ajustee"]) - 1) for a in anciennes
                          if a["vl_ajustee"] and a["date"] in nouvelles and pd.notna(nouvelles[a["date"]])]
                if ecarts and max(ecarts) > ECART_MAX:
                    d2 = _telecharger([p["ticker_yahoo"]], origine).get(p["ticker_yahoo"])
                    if d2 is None:
                        continue
                    d, complet = d2, True
                    rapport["recharges"].append(p["isin"])
            if complet:
                # Nouvelle série : on efface l'ancienne pour ne pas mélanger deux sources
                db.table("historique").delete().eq("isin", p["isin"]).execute()
                lignes = _lignes(p["isin"], d, origine)
            else:
                lignes = _lignes(p["isin"], d, dt.date.fromisoformat(p["derniere_vl"]) + dt.timedelta(days=1))
            _enregistrer(db, lignes)
            maj = {"source_vl": "yahoo"}
            if lignes:
                maj["derniere_vl"] = max(l["date"] for l in lignes)
                rapport["maj"].append((p["isin"], len(lignes)))
            db.table("produits").update(maj).eq("isin", p["isin"]).execute()
    return rapport
