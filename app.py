"""Adéquation CGPI – point d'entrée : navigation entre les pages."""
import streamlit as st

st.set_page_config(page_title="Adéquation CGPI", page_icon="📊", layout="wide")

page = st.navigation([
    st.Page("accueil.py", title="Mes produits", default=True),
    st.Page("univers.py", title="Univers d'investissement"),
    st.Page("en_cours.py", title="Produits en cours de référencement"),
    st.Page("page_indices.py", title="Indices de référence"),
    st.Page("methodologie.py", title="Méthodologie"),
], position="hidden")
page.run()
