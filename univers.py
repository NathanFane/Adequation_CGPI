"""Univers d'investissement : tous les produits complets (VL et indicateurs disponibles)."""
import pandas as pd
import streamlit as st

from base import db
from collecte import _tout
from indices import PAR_CODE, ZONES
from remplissage import NOMS_CONTRATS

NOMS_CLASSES = {"monetaire": "Monétaire", "obligations": "Obligations", "actions": "Actions", "mixte": "Mixte",
                "immobilier": "Immobilier", "matieres_premieres": "Matières premières",
                "alternatif": "Alternatif", "structure": "Structuré / à formule"}

st.title("Univers d'investissement")
st.caption("Produits référencés dont les VL et tous les indicateurs sont disponibles. "
           "Un produit apparaît ici dès que ses données sont complètes.")


@st.cache_data(ttl=600)
def charger():
    complets = _tout(db.table("produits_complets").select("*").order("isin"))
    incomplets = _tout(db.table("produits_incomplets").select("isin, nom, type_produit, raison").order("isin"))
    return complets, incomplets


complets, incomplets = charger()
df = pd.DataFrame([{
    "ISIN": p["isin"],
    "Nom": p["nom"],
    "Type": p["type_produit"],
    "Classe d'actifs": NOMS_CLASSES.get(p["classe_actifs"]),
    "Zone": p["zone"],
    "Contrats": ", ".join(NOMS_CONTRATS.get(c, c) for c in (p["contrats"] or [])),
    "SRI": p["sri"],
    "SFDR": f"Article {p['sfdr']}" if p["sfdr"] else None,
    "Label ISR": p["label_isr"],
    "Frais du fonds": p["frais_actif"],
    "Rendement annuel": p["rendement_annuel"],
    "Volatilité": p["volatilite"],
    "VaR 97,5 % 1 an": p["var_cf"],
    "Max Drawdown": p["max_drawdown"],
    "Sharpe": p["sharpe"],
    "Sortino": p["sortino"],
    "Indice retenu": PAR_CODE.get(p["indice_reference"], {}).get("nom"),
    "Corrélation à l'indice": p["correlation_indice"],
    "VL jusqu'au": p["derniere_vl"],
} for p in complets])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Produits complets", len(complets))
c2.metric("En cours de référencement", len(incomplets))

if df.empty:
    st.info("Aucun produit complet pour l'instant.")
else:
    f1, f2, f3, f4 = st.columns(4)
    f_contrat = f1.multiselect("Contrat", sorted({c for v in df["Contrats"] for c in v.split(", ") if c}))
    f_classe = f2.multiselect("Classe d'actifs", list(NOMS_CLASSES.values()))
    f_zone = f3.multiselect("Zone", ZONES)
    f_sri = f4.slider("SRI", 1, 7, (1, 7))
    vue = df
    if f_contrat:
        vue = vue[vue["Contrats"].apply(lambda v: any(c in v.split(", ") for c in f_contrat))]
    if f_classe:
        vue = vue[vue["Classe d'actifs"].isin(f_classe)]
    if f_zone:
        vue = vue[vue["Zone"].isin(f_zone)]
    if f_sri != (1, 7):
        vue = vue[vue["SRI"].between(*f_sri)]
    c3.metric("Affichés", len(vue))

    st.dataframe(
        vue.sort_values(["Classe d'actifs", "Nom"], na_position="last"),
        hide_index=True, width="stretch", height=600,
        column_config={
            "Frais du fonds": st.column_config.NumberColumn(format="percent"),
            "Rendement annuel": st.column_config.NumberColumn(format="percent"),
            "Volatilité": st.column_config.NumberColumn(format="percent"),
            "VaR 97,5 % 1 an": st.column_config.NumberColumn(
                format="percent", help="Perte maximale sur 1 an dans 97,5 % des cas (Cornish-Fisher, méthode PRIIPs)"),
            "Max Drawdown": st.column_config.NumberColumn(format="percent"),
            "Sharpe": st.column_config.NumberColumn(format="%.2f"),
            "Sortino": st.column_config.NumberColumn(format="%.2f"),
            "Corrélation à l'indice": st.column_config.NumberColumn(format="%.2f"),
            "SRI": st.column_config.NumberColumn(help="Indicateur synthétique de risque (1 à 7) publié par l'assureur"),
        },
    )

with st.expander(f"Produits en cours de référencement ({len(incomplets)})"):
    if incomplets:
        st.dataframe(pd.DataFrame([{"ISIN": p["isin"], "Nom": p["nom"], "Type": p["type_produit"],
                                    "Raison": p["raison"]} for p in incomplets]),
                     hide_index=True, width="stretch")
    else:
        st.write("Aucun.")

st.divider()
st.page_link("accueil.py", label="Retour à mes produits", icon="⬅️")
st.page_link("methodologie.py", label="Méthodologie : détail du calcul des métriques", icon="📐")
