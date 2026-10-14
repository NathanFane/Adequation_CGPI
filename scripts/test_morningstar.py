"""Test : mstarpy (Morningstar) fournit-il les VL et le SRI des fonds français ?"""
import datetime as dt
import json
import traceback

import mstarpy

ISINS = ["FR0010135103", "LU1681043599"]
session = None


def chercher(obj, motifs, chemin=""):
    """Liste les clés dont le nom contient un des motifs."""
    trouves = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{chemin}.{k}"
            if any(m in k.lower() for m in motifs):
                trouves.append((p, v if not isinstance(v, (dict, list)) else "…"))
            trouves += chercher(v, motifs, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):
            trouves += chercher(v, motifs, f"{chemin}[{i}]")
    return trouves


for isin in ISINS:
    print(f"\n===== {isin} =====")
    try:
        f = mstarpy.Funds(isin, language="fr", pageSize=1, session=session)
        session = f.session
        print("Nom :", f.name, "| code :", f.code)
    except Exception:
        traceback.print_exc()
        continue

    try:
        fin = dt.datetime.today()
        vl = f.nav(fin - dt.timedelta(days=5 * 365), fin)
        print(f"VL : {len(vl)} points, du {vl[0]['date']} au {vl[-1]['date']}, dernière = {vl[-1]['nav']}")
    except Exception as e:
        print("VL : ERREUR", type(e).__name__, str(e)[:200])

    for methode in ["graphData", "historicalData"]:
        try:
            data = getattr(f, methode)()
            apercu = json.dumps(data, default=str)
            print(f"{methode} : {len(apercu)} car. ; début : {apercu[:600]}")
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list):
                        print(f"   liste {k} : {len(v)} éléments ; premier = {json.dumps(v[0], default=str)[:200] if v else None} ; dernier = {json.dumps(v[-1], default=str)[:200] if v else None}")
        except Exception as e:
            print(f"{methode} : ERREUR", type(e).__name__, str(e)[:200])

    for methode in []:
        try:
            data = getattr(f, methode)()
            hits = chercher(data, ["srri", "sri", "riskindicator", "priip", "sfdr", "article", "ongoing"])
            print(f"{methode} : {len(json.dumps(data, default=str))} car. ; clés trouvées : {hits[:10]}")
        except Exception as e:
            print(f"{methode} : ERREUR", type(e).__name__, str(e)[:200])
