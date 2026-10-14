"""Adéquation CGPI – point d'entrée : navigation entre les pages."""
import streamlit as st

st.set_page_config(page_title="Adéquation CGPI", page_icon="📊", layout="wide")

page = st.navigation([
    st.Page("accueil.py", title="Mes produits", default=True),
    st.Page("methodologie.py", title="Méthodologie"),
], position="hidden")
page.run()
