"""Test : EODHD fournit-il les VL quotidiennes de nos produits ?"""
import os
import requests

CLE = os.environ["EODHD_API_KEY"]
ISINS = ["FR0010135103", "FR0000292278", "FR0010148981", "LU1681043599", "FR0011550185"]
BASE = "https://eodhd.com/api"

for isin in ISINS:
    print(f"\n===== {isin} =====")
    # 1. Les fonds européens sont référencés directement par ISIN sur la place EUFUND
    for ticker in [f"{isin}.EUFUND"]:
        r = requests.get(f"{BASE}/eod/{ticker}", params={"api_token": CLE, "fmt": "json"}, timeout=30)
        if r.ok and isinstance(r.json(), list) and r.json():
            d = r.json()
            print(f"{ticker} : {len(d)} VL, du {d[0]['date']} au {d[-1]['date']}, dernière = {d[-1]['close']}")
        else:
            print(f"{ticker} : rien ({r.status_code}) {r.text[:150]}")
    # 2. Recherche par ISIN (utile pour les ETF cotés)
    r = requests.get(f"{BASE}/search/{isin}", params={"api_token": CLE, "fmt": "json"}, timeout=30)
    print("Recherche :", [(x.get("Code"), x.get("Exchange"), x.get("Type")) for x in (r.json() if r.ok else [])][:5])
