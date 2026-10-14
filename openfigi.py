"""Récupération du nom et du type des produits via l'API OpenFIGI (Bloomberg, gratuite)."""
import time
import requests

URL = "https://api.openfigi.com/v3/mapping"
TYPES = ["fonds", "etf", "action", "obligation", "scpi", "autre"]


def type_produit(d: dict) -> str:
    """Traduit la classification OpenFIGI dans nos catégories."""
    t1, t2, secteur = d.get("securityType", ""), d.get("securityType2", ""), d.get("marketSector", "")
    if t1 == "ETP":
        return "etf"
    if t2 == "Mutual Fund" or "Fund" in t1:
        return "fonds"
    if t2 in ("Common Stock", "Preferred Stock", "Depositary Receipt"):
        return "action"
    if secteur in ("Govt", "Corp", "Muni") or t2 in ("Govt", "Corp"):
        return "obligation"
    return "autre"


def infos_produits(isins: list[str], cle_api: str | None = None) -> dict[str, dict]:
    """Renvoie {isin: {"nom": ..., "type": ...}}. Les ISIN non reconnus sont absents.

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
        for _ in range(3):
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
                resultat[isin] = {"nom": donnees[0]["name"].strip(), "type": type_produit(donnees[0])}
    return resultat
