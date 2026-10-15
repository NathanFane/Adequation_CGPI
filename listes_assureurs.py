"""Lecture des listes de supports publiées par les assureurs.

Un lecteur par assureur : le dossier donnees/contrats/<assureur>/ indique lequel utiliser.
Chaque lecteur renvoie des lignes au format de la table supports_contrat.
"""
from datetime import date

import pandas as pd

from isin import est_valide, normaliser


def _texte(v):
    if v is None or pd.isna(v):
        return None
    v = str(v).strip()
    return v or None


def _pourcent(v):
    """« 1.93 » ou « 1,93 » (en %) -> 0.0193. Vide ou non numérique -> None."""
    v = _texte(v)
    if v is None:
        return None
    try:
        return round(float(v.replace(",", ".").replace("%", "")) / 100, 6)
    except ValueError:
        return None


def _on(v):
    """« O » -> True, « N » -> False, autre -> None."""
    v = (_texte(v) or "").upper()
    return True if v == "O" else False if v == "N" else None


def _sfdr(v):
    v = (_texte(v) or "").lower().replace("article", "").strip()
    return int(v) if v in ("6", "8", "9") else None


def _lire_csv(chemin):
    """CSV « ; » en UTF-8 ou, à défaut, Latin-1 (export Windows)."""
    try:
        return pd.read_csv(chemin, sep=";", dtype=str, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(chemin, sep=";", dtype=str, encoding="latin-1")


# ---------------------------------------------------------------- Generali
def lire_generali(chemin: str):
    df = _lire_csv(chemin)
    df.columns = [c.strip() for c in df.columns]
    lignes, anomalies = [], []
    for _, r in df.iterrows():
        isin = normaliser(r.get("Code ISIN"))
        if not est_valide(isin):
            nom = _texte(r.get("Libelle de l'element financier"))
            anomalies.append(f"ISIN invalide : {r.get('Code ISIN')!r} ({nom})")
            continue
        if _on(r.get("Indicateur ETFs")):
            type_produit = "etf"
        elif _on(r.get("Indicateur Titres vifs /Actions")):
            type_produit = "action"
        elif (_texte(r.get("Nature juridique")) or "").upper() == "SCPI":
            type_produit = "scpi"
        else:
            type_produit = "fonds"
        lignes.append({
            "contrat": f"generali_{_texte(r.get('Code produit'))}",
            "assureur": "Generali",
            "isin": isin,
            "nom": _texte(r.get("Libelle de l'element financier")),
            "code_support": _texte(r.get("Code garantie elementaire")),
            "forme_juridique": _texte(r.get("Nature juridique")),
            "type_produit": type_produit,
            "societe_gestion": _texte(r.get("Societe de gestion")),
            "classification": _texte(r.get("Classification EUROPERF")),
            "sfdr": _sfdr(r.get("Classification SFDR")),
            "frais_actif": _pourcent(r.get("Frais de gestion de l'actif")),
            "retrocessions": _pourcent(r.get("Taux de retrocessions de commissionnement")),
            "frais_contrat": _pourcent(r.get("Frais de gestion du contrat")),
            "frais_totaux": _pourcent(r.get("Frais de gestion totaux")),
            "perf_brute_n1": _pourcent(r.get("Performance brute de l'actif N-1")),
            "perf_nette_n1": _pourcent(r.get("Performance nette de l'unite de compte N-1")),
            "perf_finale_n1": _pourcent(r.get("Performance finale")),
            "ouvert": (_texte(r.get("Etat de l'element financier")) or "").lower() == "ouvert",
            "avenant_requis": _on(r.get("Indicateur Fonds a avenant ?")),
            "cotation_quotidienne": _on(r.get("Cotation quotidienne")),
            "eligible_pea": _on(r.get("Eligibilite P.E.A.")),
            "complements": {
                "gestion_libre": _on(r.get("Gestion libre ?")),
                "gestion_pilotee": _on(r.get("Gestion pilotee ?")),
                "liste": _texte(r.get("Mandataire")),
            },
        })
    return lignes, anomalies


LECTEURS = {"generali": lire_generali}


def extraire(dossier_assureur: str, fichiers: list[str]):
    """Lit les fichiers d'un dossier assureur. Une ligne par (contrat, ISIN) ; doublons signalés."""
    lecteur = LECTEURS[dossier_assureur]
    retenues, anomalies, nb = {}, [], 0
    for chemin in fichiers:
        lignes, anom = lecteur(chemin)
        nb += len(lignes)
        anomalies += anom
        for l in lignes:
            l["fichier_source"] = chemin.rsplit("/", 1)[-1]
            l.setdefault("date_liste", date.today().isoformat())
            cle = (l["contrat"], l["isin"])
            if cle in retenues:
                a = retenues[cle]
                if (a["frais_contrat"], a["frais_actif"]) != (l["frais_contrat"], l["frais_actif"]):
                    anomalies.append(f"{l['isin']} en double avec des frais différents "
                                     f"({a['code_support']} / {l['code_support']}) : première ligne gardée")
                continue
            retenues[cle] = l
    return list(retenues.values()), {"lignes": nb, "doublons": nb - len(retenues), "anomalies": anomalies}
