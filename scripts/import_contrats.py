"""Importe les listes de supports des assureurs (donnees/contrats/<assureur>/) dans Supabase."""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import listes_assureurs  # noqa: E402

db = None
if not os.environ.get("SIMULATION"):
    from supabase import create_client
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

for assureur in sorted(listes_assureurs.LECTEURS):
    dossier = f"donnees/contrats/{assureur}"
    fichiers = sorted(f for ext in ("xlsx", "xls", "csv", "pdf") for f in glob.glob(f"{dossier}/*.{ext}"))
    print(f"\n===== {assureur} =====")
    if not fichiers:
        print(f"Aucun fichier dans {dossier}.")
        continue
    lignes, stats = listes_assureurs.extraire(assureur, fichiers)
    print(f"Fichiers : {len(fichiers)} ; lignes lues : {stats['lignes']} ; doublons écartés : {stats['doublons']} ; "
          f"supports retenus : {len(lignes)}")
    types = {}
    for l in lignes:
        types[l["type_produit"]] = types.get(l["type_produit"], 0) + 1
    print("Répartition :", types)
    for a in stats["anomalies"][:50]:
        print("Anomalie –", a)
    if db is None:
        print("Simulation : rien n'est écrit en base.")
        continue
    for i in range(0, len(lignes), 500):
        db.table("supports_contrat").upsert(lignes[i:i + 500], on_conflict="contrat,isin,date_liste").execute()
    print(f"{len(lignes)} supports enregistrés dans supports_contrat.")
