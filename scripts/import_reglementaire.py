"""Importe les fichiers EMT (donnees/emt) et EPT (donnees/ept) dans Supabase (GitHub Actions)."""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import emt  # noqa: E402
import ept  # noqa: E402

SOURCES = [("EMT", "donnees/emt", emt.extraire, "donnees_emt"),
           ("EPT", "donnees/ept", ept.extraire, "donnees_ept")]

db = None
if not os.environ.get("SIMULATION"):
    from supabase import create_client
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

for nom, dossier, extraire, table in SOURCES:
    fichiers = sorted(f for ext in ("xlsx", "xls", "csv") for f in glob.glob(f"{dossier}/*.{ext}"))
    print(f"\n===== {nom} =====")
    if not fichiers:
        print(f"Aucun fichier dans {dossier}.")
        continue
    lignes, stats = extraire(fichiers)
    print(f"Fichiers lus : {len(fichiers)} ; lignes : {stats['lignes']} ; ignorées : {stats['ignorees']} ; "
          f"produits retenus : {len(lignes)}")
    for a in stats["anomalies"][:50]:
        print("Anomalie –", a)
    if len(stats["anomalies"]) > 50:
        print(f"… et {len(stats['anomalies']) - 50} autres anomalies")
    if db is None:
        print("Simulation : rien n'est écrit en base.")
        continue
    for i in range(0, len(lignes), 500):
        db.table(table).upsert(lignes[i:i + 500], on_conflict="isin").execute()
    print(f"{len(lignes)} produits enregistrés dans {table}.")
