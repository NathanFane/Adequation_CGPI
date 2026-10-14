"""Connexion partagée à la base (provisoire : utilisateur de test, en attendant la page de connexion)."""
import streamlit as st
from supabase import create_client


@st.cache_resource
def base():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])


db = base()
USER_ID = st.secrets["DEV_USER_ID"]


@st.cache_resource
def _profil():
    """Crée le profil de l'utilisateur de test s'il n'existe pas encore (une fois par démarrage)."""
    db.table("utilisateurs").upsert({
        "id": USER_ID,
        "nom": st.secrets.get("DEV_NOM", "Test"),
        "prenom": st.secrets.get("DEV_PRENOM", "Utilisateur"),
        "email": st.secrets["DEV_EMAIL"],
    }, on_conflict="id").execute()
    return True


_profil()
