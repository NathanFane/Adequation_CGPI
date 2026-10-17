"""Univers d'investissement : tous les produits complets (VL et indicateurs disponibles)."""
import pandas as pd
import streamlit as st

from base import db
from collecte import _tout
from indices import PAR_CODE, ZONES
from remplissage import NOMS_CONTRATS
import filtres as F

NOMS_CLASSES = {"monetaire": "Monétaire", "obligations": "Obligations", "actions": "Actions", "mixte": "Mixte",
                "immobilier": "Immobilier", "matieres_premieres": "Matières premières",
                "alternatif": "Alternatif", "structure": "Structuré / à formule"}

st.title("Univers d'investissement")
st.caption("Produits référencés dont les VL et tous les indicateurs sont disponibles. "
           "Un produit apparaît ici dès que ses données sont complètes.")


def _nouvel_id():
    etat = st.session_state.filtres
    etat["suivant"] += 1
    return etat["suivant"]


def _ajouter_groupe():
    st.session_state.filtres["groupes"].append({"id": _nouvel_id(), "criteres": [_nouvel_id()]})


def _ajouter_critere(g):
    g["criteres"].append(_nouvel_id())


def _retirer_critere(g, cid):
    g["criteres"].remove(cid)
    if not g["criteres"]:
        st.session_state.filtres["groupes"].remove(g)


def _reinitialiser():
    for k in [k for k in st.session_state if k.startswith("flt_")]:
        del st.session_state[k]
    st.session_state.filtres = {"groupes": [], "suivant": 0}


def section_filtres(df):
    """Section « Filtres » : groupes de critères reliés par ET / OU. Renvoie le tableau filtré."""
    st.session_state.setdefault("filtres", {"groupes": [], "suivant": 0})
    etat = st.session_state.filtres
    indicateurs = F.LISTES + list(F.NOMBRES)
    groupes = []
    with st.expander("Filtres", expanded=True):
        st.caption("Dans un critère, plusieurs valeurs = OU (ex. Zone = France ou Monde). "
                   "Dans un groupe, les critères sont reliés par ET ou OU. Entre les groupes, un seul lien ET ou OU.")
        for n, g in enumerate(etat["groupes"], 1):
            with st.container(border=True):
                t1, t2, t3 = st.columns([2, 3, 1])
                t1.markdown(f"**Groupe {n}**")
                lien = t2.radio("Lien entre les critères du groupe", ["ET", "OU"], horizontal=True,
                                key=f"flt_lien_{g['id']}", label_visibility="collapsed")
                t3.button("Supprimer le groupe", key=f"flt_supg_{g['id']}",
                          on_click=lambda g=g: etat["groupes"].remove(g))
                criteres = []
                for cid in list(g["criteres"]):
                    c1, c2, c3, c4 = st.columns([3, 2, 4, 1])
                    ind = c1.selectbox("Indicateur", indicateurs, key=f"flt_ind_{cid}", label_visibility="collapsed")
                    if ind in F.NOMBRES:
                        op = c2.selectbox("Opérateur", F.OPERATEURS_NOMBRE, key=f"flt_op_{cid}",
                                          label_visibility="collapsed")
                        unite = " (%)" if F.NOMBRES[ind] else ""
                        if op in ("entre", "hors de"):
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
                                                 placeholder="Choisir une ou plusieurs valeurs",
                                                 label_visibility="collapsed")
                    c4.button("✕", key=f"flt_supc_{cid}", help="Retirer ce critère",
                              on_click=_retirer_critere, args=(g, cid))
                    if valeurs:
                        criteres.append({"indicateur": ind, "operateur": op, "valeurs": valeurs})
                st.button("+ Ajouter un critère", key=f"flt_addc_{g['id']}", on_click=_ajouter_critere, args=(g,))
                groupes.append({"lien": lien, "criteres": criteres})
        b1, b2, b3 = st.columns([2, 3, 2])
        b1.button("+ Ajouter un groupe", on_click=_ajouter_groupe)
        lien_groupes = b2.radio("Lien entre les groupes", ["ET", "OU"], horizontal=True, key="flt_lien_groupes")
        b3.button("Réinitialiser les filtres", on_click=_reinitialiser)
        formule = F.decrire(groupes, lien_groupes)
        if formule:
            st.info("Sélection : " + formule)
    return F.appliquer(df, groupes, lien_groupes)


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
    vue = section_filtres(df)
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

st.divider()
st.page_link("en_cours.py", label=f"Produits en cours de référencement ({len(incomplets)})", icon="⏳")
st.page_link("accueil.py", label="Retour à mes produits", icon="⬅️")
st.page_link("methodologie.py", label="Méthodologie : détail du calcul des métriques", icon="📐")
