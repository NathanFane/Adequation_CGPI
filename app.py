"""Adéquation CGPI – point d'entrée : navigation entre les pages."""
import streamlit as st

from navigation import pied_de_page

st.set_page_config(page_title="Adéquation CGPI", page_icon="📊", layout="wide")

PAGES = {
    "accueil.py": st.Page("accueil.py", title="Mes produits", default=True),
    "univers.py": st.Page("univers.py", title="Univers d'investissement"),
    "en_cours.py": st.Page("en_cours.py", title="Produits en cours de référencement"),
    "page_indices.py": st.Page("page_indices.py", title="Indices de référence"),
    "methodologie.py": st.Page("methodologie.py", title="Méthodologie"),
}
page = st.navigation(list(PAGES.values()), position="hidden")

# Le pied de page s'affiche avant le contenu (qui se remplit au-dessus) : les liens restent
# disponibles pendant le chargement, et même si la page plante.
corps = st.container()
pied_de_page(next(f for f, p in PAGES.items() if p is page))
with corps:
    try:
        page.run()
    except Exception as e:   # st.rerun / st.stop ne sont pas des Exception : ils passent
        st.exception(e)
