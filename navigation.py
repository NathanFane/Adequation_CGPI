"""Pied de page commun : liens vers les autres pages, et toujours « Retour à mes produits » en dernier."""
import streamlit as st

PAGES = [
    ("univers.py", "Univers d'investissement : tous les produits référencés", "🗂️"),
    ("en_cours.py", "Produits en cours de référencement", "⏳"),
    ("page_indices.py", "Indices de référence : composition, indicateurs et évolution", "📈"),
    ("methodologie.py", "Méthodologie : détail du calcul des métriques", "📐"),
]


def pied_de_page(page_actuelle: str):
    st.divider()
    for fichier, libelle, icone in PAGES:
        if fichier != page_actuelle:
            st.page_link(fichier, label=libelle, icon=icone)
    if page_actuelle != "accueil.py":
        st.page_link("accueil.py", label="Retour à mes produits", icon="⬅️")
