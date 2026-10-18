"""Univers d'investissement : tous les produits complets (VL et indicateurs disponibles)."""
import pandas as pd
import streamlit as st

from navigation import pied_de_page, retour_en_haut

from base import db
from collecte import _tout
from indices import PAR_CODE, ZONES
from remplissage import NOMS_CONTRATS
import filtres as F
from colonnes import CONFIG, METRIQUES

NOMS_CLASSES = {"monetaire": "Monétaire", "obligations": "Obligations", "actions": "Actions", "mixte": "Mixte",
                "immobilier": "Immobilier", "matieres_premieres": "Matières premières",
                "alternatif": "Alternatif", "structure": "Structuré / à formule"}

retour_en_haut()
st.title("Univers d'investissement")
st.caption("Produits référencés dont les VL et tous les indicateurs sont disponibles. "
           "Un produit apparaît ici dès que ses données sont complètes.")


def _nouvel_id():
    etat = st.session_state.filtres
    etat["suivant"] += 1
    return etat["suivant"]


def _ajouter_critere():
    st.session_state.filtres["criteres"].append(_nouvel_id())


def _retirer_critere(cid):
    st.session_state.filtres["criteres"].remove(cid)


def _reinitialiser():
    for k in [k for k in st.session_state if k.startswith("flt_")]:
        del st.session_state[k]
    st.session_state.filtres = {"criteres": [], "suivant": 0}


def section_filtres(df):
    """Section « Filtres » : critères reliés deux à deux par ET ou OU. Renvoie le tableau filtré."""
    if "criteres" not in st.session_state.get("filtres", {}):
        st.session_state.filtres = {"criteres": [], "suivant": 0}
    etat = st.session_state.filtres
    indicateurs = F.LISTES + list(F.NOMBRES)
    criteres = []
    with st.expander("Filtres", expanded=True):
        st.caption("Dans un critère, plusieurs valeurs = OU (ex. Zone = France ou Monde). "
                   "Entre deux critères, choisissez ET ou OU. Le ET est prioritaire : "
                   "« A ET B OU C » = « (A ET B) OU C ».")
        for n, cid in enumerate(list(etat["criteres"])):
            lien = "ET"
            if n:
                lien = st.radio("Lien avec le critère précédent", ["ET", "OU"], horizontal=True,
                                key=f"flt_lien_{cid}", label_visibility="collapsed")
            c1, c2, c3, c4 = st.columns([3, 3, 4, 1])
            ind = c1.selectbox("Indicateur", indicateurs, key=f"flt_ind_{cid}", label_visibility="collapsed")
            if ind in F.NOMBRES:
                op = c2.selectbox("Opérateur", F.OPERATEURS_NOMBRE, key=f"flt_op_{cid}", label_visibility="collapsed")
                unite = " (%)" if F.NOMBRES[ind] else ""
                if op in (F.ENTRE, F.HORS):
                    v1, v2 = c3.columns(2)
                    a = v1.number_input("de" + unite, value=None, key=f"flt_a_{cid}", placeholder="de" + unite,
                                        label_visibility="collapsed")
                    b = v2.number_input("à" + unite, value=None, key=f"flt_b_{cid}", placeholder="à" + unite,
                                        label_visibility="collapsed")
                    valeurs = [a, b] if a is not None and b is not None else []
                else:
                    a = c3.number_input("valeur" + unite, value=None, key=f"flt_a_{cid}",
                                        placeholder="valeur" + unite, label_visibility="collapsed")
                    valeurs = [a] if a is not None else []
            else:
                ops = F.OPERATEURS_LISTE_MULTIPLE if ind in F.MULTIPLES else F.OPERATEURS_LISTE
                op = c2.selectbox("Opérateur", ops, key=f"flt_op_{cid}", label_visibility="collapsed")
                valeurs = c3.multiselect("Valeurs", F.valeurs_possibles(df, ind), key=f"flt_v_{cid}",
                                         placeholder="Choisir une ou plusieurs valeurs", label_visibility="collapsed")
            c4.button("✕", key=f"flt_supc_{cid}", help="Retirer ce critère", on_click=_retirer_critere, args=(cid,))
            if valeurs:
                criteres.append({"lien": lien, "indicateur": ind, "operateur": op, "valeurs": valeurs})
        b1, _, b3 = st.columns([2, 3, 2])
        b1.button("+ Ajouter un critère", on_click=_ajouter_critere)
        b3.button("Réinitialiser les filtres", on_click=_reinitialiser)
        if criteres:
            criteres[0]["lien"] = "ET"
            st.info("Sélection : " + F.decrire(criteres))
    return F.appliquer(df, criteres)


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
    "Frais totaux": p.get("frais_totaux"),
    "Indice retenu": PAR_CODE.get(p["indice_reference"], {}).get("nom"),
    **{libelle: p.get(champ) for libelle, champ in METRIQUES.items()},
    "VL jusqu'au": p["derniere_vl"],
    "Mis à jour le": (p.get("derniere_maj") or "")[:10] or None,
    "Source des VL": {"yahoo": "Yahoo Finance", "eodhd": "EODHD"}.get(p["source_vl"]),
} for p in complets])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Produits complets", len(complets))
c2.metric("En cours de référencement", len(incomplets))

if df.empty:
    st.info("Aucun produit complet pour l'instant.")
else:
    vue = section_filtres(df)
    c3.metric("Affichés", len(vue))

    st.dataframe(
        vue.sort_values(["Classe d'actifs", "Nom"], na_position="last"),
        hide_index=True, width="stretch", height=600,
        column_config={
            **CONFIG,
            "SRI": st.column_config.NumberColumn(help="Indicateur synthétique de risque (1 à 7) publié par l'assureur"),
        },
    )

pied_de_page("univers.py")
