"""Indices de référence : liste, composition, indicateurs et évolution sur 5 ans."""
import datetime as dt

import pandas as pd
import streamlit as st

from navigation import retour_en_haut

from base import db
from calculs import lire_indices, metriques, taux_sans_risque
from collecte import _tout
from indices import REFERENCES, classe_indice, zone_indice

NOMS_CLASSES = {"monetaire": "Monétaire", "obligations": "Obligations", "actions": "Actions", "mixte": "Mixte",
                "immobilier": "Immobilier", "matieres_premieres": "Matières premières"}

retour_en_haut()
st.title("Indices de référence")
st.caption(f"Les {len(REFERENCES)} indices auxquels chaque fonds est comparé (corrélation des rendements "
           "hebdomadaires). Chaque indice est représenté par un ou plusieurs ETF (source Yahoo Finance, "
           "dividendes réinvestis) ; les indices mixtes sont rééquilibrés chaque jour.")


def serie_indice(cours: pd.DataFrame, composition: dict) -> pd.Series:
    """Valeur de l'indice, base 100 : un ETF, ou un panier d'ETF rééquilibré chaque jour."""
    tickers = [t for t in composition if t in cours.columns]
    if len(tickers) < len(composition):
        return pd.Series(dtype=float)
    rendements = cours[tickers].pct_change(fill_method=None)
    poids = pd.Series(composition)[tickers]
    r = (rendements * poids).sum(axis=1, min_count=len(tickers)).dropna()
    return 100 * (1 + r).cumprod()


@st.cache_data(ttl=3600)
def charger():
    cours = lire_indices(db)
    rf = taux_sans_risque(dt.date.today() - dt.timedelta(days=365 * 5))
    utilisation = pd.Series([p["indice_reference"] for p in _tout(
        db.table("produits_complets").select("indice_reference").order("isin"))]).value_counts()
    lignes, series = [], {}
    for r in REFERENCES:
        s = serie_indice(cours, r["composition"])
        series[r["nom"]] = s
        m = metriques(s, rf) if len(s) else None
        lignes.append({
            "Indice": r["nom"],
            "Catégorie": r["categorie"],
            "Classe d'actifs": NOMS_CLASSES.get(classe_indice(r["code"])),
            "Zone": zone_indice(r["code"]),
            "ETF utilisé(s)": " + ".join(f"{round(p * 100)} % {t}" if p < 1 else t
                                         for t, p in r["composition"].items()),
            "Fonds rattachés": int(utilisation.get(r["code"], 0)),
            "Rendement annuel": m["rendement_annuel"] if m else None,
            "Volatilité": m["volatilite"] if m else None,
            "Max Drawdown": m["max_drawdown"] if m else None,
            "Sharpe": m["sharpe"] if m else None,
            "Cours jusqu'au": s.index.max().date().isoformat() if len(s) else None,
        })
    return pd.DataFrame(lignes), series


tableau, series = charger()
f1, f2 = st.columns(2)
f_cat = f1.multiselect("Catégorie", sorted(tableau["Catégorie"].unique()))
f_zone = f2.multiselect("Zone", sorted(tableau["Zone"].dropna().unique()))
vue = tableau
if f_cat:
    vue = vue[vue["Catégorie"].isin(f_cat)]
if f_zone:
    vue = vue[vue["Zone"].isin(f_zone)]

st.dataframe(vue, hide_index=True, width="stretch", height=min(40 + 35 * len(vue), 700), column_config={
    "Rendement annuel": st.column_config.NumberColumn(format="percent", help="Annualisé sur 5 ans"),
    "Volatilité": st.column_config.NumberColumn(format="percent", help="Annualisée sur 5 ans"),
    "Max Drawdown": st.column_config.NumberColumn(format="percent", help="Pire baisse depuis un plus haut, sur 5 ans"),
    "Sharpe": st.column_config.NumberColumn(format="%.2f"),
    "Fonds rattachés": st.column_config.NumberColumn(help="Fonds de l'univers dont c'est l'indice le plus corrélé"),
})

st.subheader("Évolution sur 5 ans (base 100)")
choix = st.multiselect("Indices à afficher", list(vue["Indice"]), default=list(vue["Indice"])[:3],
                       max_selections=8)
if choix:
    st.line_chart(pd.DataFrame({n: series[n] for n in choix if len(series[n])}))
