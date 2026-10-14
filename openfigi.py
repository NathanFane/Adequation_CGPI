"""Récupération du nom des produits via l'API OpenFIGI (Bloomberg, gratuite)."""
import time
import requests

URL = "https://api.openfigi.com/v3/mapping"


def noms_produits(isins: list[str], cle_api: str | None = None) -> dict[str, str]:
    """Renvoie {isin: nom}. Les ISIN non reconnus sont absents du résultat.

    Sans clé : 10 ISIN par requête, 25 requêtes par minute.
    Avec clé : 100 ISIN par requête.
    """
    taille = 100 if cle_api else 10
    entetes = {"Content-Type": "application/json"}
    if cle_api:
        entetes["X-OPENFIGI-APIKEY"] = cle_api

    resultat = {}
    for i in range(0, len(isins), taille):
        lot = isins[i:i + taille]
        corps = [{"idType": "ID_ISIN", "idValue": isin} for isin in lot]
        for essai in range(3):
            r = requests.post(URL, json=corps, headers=entetes, timeout=30)
            if r.status_code == 429:  # limite de débit atteinte
                time.sleep(int(r.headers.get("ratelimit-reset", 10)) + 1)
                continue
            r.raise_for_status()
            break
        else:
            r.raise_for_status()
        for isin, reponse in zip(lot, r.json()):
            donnees = reponse.get("data") or []
            if donnees:
                resultat[isin] = donnees[0]["name"].strip()
    return resultat
