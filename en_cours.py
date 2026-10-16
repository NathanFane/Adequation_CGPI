"""Produits en cours de référencement : suivis mais pas encore complets (VL ou indicateurs manquants)."""
import pandas as pd
import streamlit as st

from base import db
from collecte import _tout
from remplissage import NOMS_CONTRATS

st.title("Produits en cours de référencement")
st.caption("Produits suivis dont les VL ou les indicateurs ne sont pas encore disponibles. "
           "Ils rejoignent l'univers d'investissement dès que leurs données sont complètes.")


@st.cache_data(ttl=600)
def charger():
    incomplets = _tout(db.table("produits_incomplets")
                       .select("isin, nom, type_produit, statut, derniere_vl, raison").order("isin"))
    contrats = {}
    for s in _tout(db.table("supports_contrat_actuels").select("isin, contrat").order("isin")):
        contrats.setdefault(s["isin"], set()).add(NOMS_CONTRATS.get(s["contrat"], s["contrat"]))
    return incomplets, contrats


incomplets, contrats = charger()
df = pd.DataFrame([{
    "ISIN": p["isin"],
    "Nom": p["nom"],
    "Type": p["type_produit"],
    "Contrats": ", ".join(sorted(contrats.get(p["isin"], []))),
    "Raison": p["raison"],
    "VL jusqu'au": p["derniere_vl"],
} for p in incomplets], columns=["ISIN", "Nom", "Type", "Contrats", "Raison", "VL jusqu'au"])

if df.empty:
    st.info("Aucun produit en cours de référencement.")
else:
    # Nombre de produits par raison
    cols = st.columns(df["Raison"].nunique() + 1)
    cols[0].metric("Total", len(df))
    for c, (raison, n) in zip(cols[1:], df["Raison"].value_counts().items()):
        c.metric(raison, n)

    f1, f2 = st.columns(2)
    f_raison = f1.multiselect("Raison", sorted(df["Raison"].unique()))
    f_contrat = f2.multiselect("Contrat", sorted({c for v in df["Contrats"] for c in v.split(", ") if c}))
    vue = df
    if f_raison:
        vue = vue[vue["Raison"].isin(f_raison)]
    if f_contrat:
        vue = vue[vue["Contrats"].apply(lambda v: any(c in v.split(", ") for c in f_contrat))]
    st.dataframe(vue.sort_values(["Raison", "Nom"]), hide_index=True, width="stretch", height=600)

st.divider()
st.page_link("univers.py", label="Univers d'investissement : produits complets", icon="🗂️")
st.page_link("accueil.py", label="Retour à mes produits", icon="⬅️")
