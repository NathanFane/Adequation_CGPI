"""Tâche quotidienne (GitHub Actions).

1. Rafraîchit les VL des produits dont la dernière VL a plus de 30 jours (les plus anciennes d'abord).
2. Avec le reste du budget EODHD, ajoute de nouveaux supports issus des listes des assureurs.
3. Met à jour les indices de référence (yfinance) et recalcule les métriques.
"""
import os
import sys

from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collecte  # noqa: E402
from calculs import calculer_et_enregistrer  # noqa: E402
from remplissage import ajouter_nouveaux  # noqa: E402

RAFRAICHISSEMENT_JOURS = 30

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
cle = os.environ["EODHD_API_KEY"]
collecte.QUOTA = int(os.environ.get("QUOTA_EODHD") or 20)

# Utilisateur de test (en attendant la page de connexion) : secret DEV_USER_ID, sinon le seul profil existant
user_id = os.environ.get("DEV_USER_ID") or db.table("utilisateurs").select("id").limit(1).execute().data[0]["id"]

# 1. Rafraîchissement mensuel
rapport = collecte.mettre_a_jour(db, cle, anciennete_max=RAFRAICHISSEMENT_JOURS)
for isin, n in rapport["maj"]:
    print(f"{isin} : {n} VL ajoutée(s)")
if rapport["sans_donnees"]:
    print("Sans données :", ", ".join(rapport["sans_donnees"]))
    jamais = [p["isin"] for p in db.table("produits").select("isin, derniere_vl")
              .in_("isin", rapport["sans_donnees"]).execute().data if not p["derniere_vl"]]
    if jamais:  # jamais trouvés : on arrête de les redemander chaque jour
        db.table("produits").update({"statut": "introuvable"}).in_("isin", jamais).execute()

# 2. Nouveaux supports avec le budget restant
if not rapport["erreur"]:
    n = ajouter_nouveaux(db, cle, user_id)
    print(f"Nouveaux supports : {len(n['ajoutes'])} ajouté(s), {len(n['introuvables'])} introuvable(s), "
          f"{n['restants']} restant(s) à traiter")
print(f"Appels EODHD utilisés : {collecte.APPELS}/{collecte.QUOTA}")

# 3. Indices de référence (yfinance, indépendant du quota EODHD)
i = collecte.mettre_a_jour_indices(db)
print(f"Indices : {i['maj']} cours enregistrés" + (f" ; échecs : {', '.join(i['echecs'])}" if i['echecs'] else ""))

# Métriques (calculées sur les VL déjà présentes)
m = calculer_et_enregistrer(db)
print(f"Métriques calculées : {len(m['calcules'])} produit(s) ; taux sans risque = {m['taux_sans_risque']}")
if m["insuffisants"]:
    print("Historique insuffisant :", ", ".join(m["insuffisants"]))
