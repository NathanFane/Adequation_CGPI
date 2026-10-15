"""Importe tous les fichiers EMT du dossier donnees/emt dans la table donnees_emt (GitHub Actions)."""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from emt import extraire  # noqa: E402

fichiers = sorted(f for ext in ("xlsx", "xls", "csv") for f in glob.glob(f"donnees/emt/*.{ext}"))
if not fichiers:
    print("Aucun fichier dans donnees/emt.")
    sys.exit(0)

lignes, stats = extraire(fichiers)
print(f"Fichiers lus : {len(fichiers)} ; lignes : {stats['lignes']} ; "
      f"ignorées (non ouvertes aux particuliers ou ISIN invalide) : {stats['ignorees']} ; "
      f"produits retenus : {len(lignes)}")
for a in stats["anomalies"][:50]:
    print("Anomalie –", a)
if len(stats["anomalies"]) > 50:
    print(f"… et {len(stats['anomalies']) - 50} autres anomalies")

if os.environ.get("SIMULATION"):
    print("Simulation : rien n'est écrit en base.")
    sys.exit(0)

from supabase import create_client  # noqa: E402
db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
for i in range(0, len(lignes), 500):
    db.table("donnees_emt").upsert(lignes[i:i + 500], on_conflict="isin").execute()
print(f"{len(lignes)} produits enregistrés dans donnees_emt.")
