"""Tâche quotidienne : met à jour les VL de tous les produits (lancée par GitHub Actions)."""
import os
import sys

from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculs import calculer_et_enregistrer  # noqa: E402
from collecte import mettre_a_jour  # noqa: E402

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
rapport = mettre_a_jour(db, os.environ["EODHD_API_KEY"])

for isin, n in rapport["maj"]:
    print(f"{isin} : {n} VL ajoutée(s)")
if rapport["sans_donnees"]:
    print("Sans données :", ", ".join(rapport["sans_donnees"]))

# Métriques (calculées même si le quota EODHD est atteint, sur les VL déjà présentes)
m = calculer_et_enregistrer(db)
print(f"Métriques calculées : {len(m['calcules'])} produit(s) ; taux sans risque = {m['taux_sans_risque']}")
if m["insuffisants"]:
    print("Historique insuffisant :", ", ".join(m["insuffisants"]))

if rapport["erreur"]:
    print("ERREUR :", rapport["erreur"])
    sys.exit(1)
