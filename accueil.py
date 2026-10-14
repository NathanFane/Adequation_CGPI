"""Page d'accueil : import et visualisation des produits par contrat."""
import io

import pandas as pd
import streamlit as st

from calculs import calculer_et_enregistrer
from collecte import mettre_a_jour
from base import USER_ID, db
from isin import est_valide, extraire, normaliser
from openfigi import TYPES, infos_produits



# ---------- Accès aux données ----------

def mes_contrats() -> pd.DataFrame:
    rows = db.table("contrats").select("id, nom, assureur").eq("user_id", USER_ID).order("nom").execute().data
    return pd.DataFrame(rows, columns=["id", "nom", "assureur"])


def contrat_id(nom: str, assureur: str | None, contrats: pd.DataFrame) -> int:
    """Renvoie l'id du contrat, en le créant s'il n'existe pas."""
    existant = contrats[contrats["nom"].str.lower() == nom.lower()]
    if not existant.empty:
        return int(existant.iloc[0]["id"])
    r = db.table("contrats").insert({"user_id": USER_ID, "nom": nom, "assureur": assureur or None}).execute()
    return r.data[0]["id"]


def importer(lignes: list[tuple[str, str, str | None]]) -> dict:
    """lignes = [(isin brut, nom du contrat, assureur)]. Renvoie un compte rendu."""
    contrats = mes_contrats()
    rapport = {"ajoutes": 0, "deja_presents": 0, "invalides": [], "introuvables": []}

    valides, vus = [], set()
    for brut, contrat, assureur in lignes:
        isin = normaliser(brut)
        if not est_valide(isin):
            rapport["invalides"].append(str(brut))
            continue
        if (isin, contrat.lower()) in vus:
            continue
        vus.add((isin, contrat.lower()))
        valides.append((isin, contrat, assureur))

    if not valides:
        return rapport

    # Produits : on ne cherche que les ISIN inconnus, sans nom ou sans type
    isins = sorted({v[0] for v in valides})
    connus = {p["isin"]: p for p in db.table("produits").select("isin, nom, type_produit")
              .in_("isin", isins).execute().data}
    a_chercher = [i for i in isins
                  if not (connus.get(i) or {}).get("nom") or not (connus.get(i) or {}).get("type_produit")]
    if a_chercher:
        with st.spinner(f"Recherche de {len(a_chercher)} produit(s)…"):
            infos = infos_produits(a_chercher, st.secrets.get("OPENFIGI_KEY"))
        lignes_produits = []
        for i in a_chercher:
            if i in infos:
                lignes_produits.append({"isin": i, "nom": (connus.get(i) or {}).get("nom") or infos[i]["nom"],
                                        "type_produit": infos[i]["type"], "statut": "valide"})
            elif i not in connus:
                lignes_produits.append({"isin": i, "nom": None, "type_produit": None, "statut": "introuvable"})
        if lignes_produits:
            db.table("produits").upsert(lignes_produits, on_conflict="isin").execute()
        rapport["introuvables"] = [i for i in a_chercher if i not in infos]

    # Liaisons contrat <-> produit
    ids = {}
    for _, contrat, assureur in valides:
        if contrat.lower() not in ids:
            ids[contrat.lower()] = contrat_id(contrat, assureur, contrats)
            contrats = mes_contrats()
    existants = {
        (l["contrat_id"], l["isin"])
        for l in db.table("contrat_produits").select("contrat_id, isin")
        .in_("contrat_id", list(ids.values())).execute().data
    }
    nouvelles = [{"contrat_id": ids[c.lower()], "isin": i} for i, c, _ in valides
                 if (ids[c.lower()], i) not in existants]
    if nouvelles:
        db.table("contrat_produits").insert(nouvelles).execute()
    rapport["ajoutes"] = len(nouvelles)
    rapport["deja_presents"] = len(valides) - len(nouvelles)
    return rapport


def modele_excel() -> bytes:
    tampon = io.BytesIO()
    pd.DataFrame({"ISIN": ["FR0010135103", "LU1681043599"],
                  "Contrat": ["Mon contrat", "Mon contrat"],
                  "Assureur": ["", ""]}).to_excel(tampon, index=False)
    return tampon.getvalue()


def lire_fichier(fichier) -> pd.DataFrame:
    if fichier.name.lower().endswith(".csv"):
        df = pd.read_csv(fichier, sep=None, engine="python", dtype=str)
    else:
        df = pd.read_excel(fichier, dtype=str)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


# ---------- Interface ----------

st.title("Mes produits")

onglet_import, onglet_liste = st.tabs(["1. Importer", "2. Visualiser"])

with onglet_import:
    contrats = mes_contrats()
    mode = st.radio("Méthode", ["Copier-coller", "Fichier Excel ou CSV"], horizontal=True)

    # Choix du contrat (sauf si le fichier contient une colonne Contrat)
    choix = st.selectbox("Contrat", list(contrats["nom"]) + ["➕ Nouveau contrat"], key="choix_contrat")
    nom_contrat, assureur = choix, None
    if choix == "➕ Nouveau contrat":
        c1, c2 = st.columns(2)
        nom_contrat = c1.text_input("Nom du contrat", key="nouveau_nom").strip()
        assureur = c2.text_input("Assureur", key="nouveau_assureur").strip()

    lignes = []
    if mode == "Copier-coller":
        texte = st.text_area("ISIN (un par ligne, ou séparés par des virgules)", height=200, key="texte_isin")
        lignes = [(i, nom_contrat, assureur) for i in extraire(texte)]
    else:
        st.download_button("Télécharger le modèle Excel", modele_excel(), "modele_import.xlsx")
        fichier = st.file_uploader("Fichier", type=["xlsx", "xls", "csv"], key="fichier_isin")
        if fichier:
            df = lire_fichier(fichier)
            col_isin = "isin" if "isin" in df.columns else df.columns[0]
            if "contrat" in df.columns:
                st.caption("La colonne Contrat du fichier est utilisée à la place du choix ci-dessus.")
            for _, r in df.iterrows():
                if pd.isna(r[col_isin]):
                    continue
                c = r.get("contrat") if "contrat" in df.columns and pd.notna(r.get("contrat")) else nom_contrat
                a = r.get("assureur") if "assureur" in df.columns and pd.notna(r.get("assureur")) else assureur
                lignes.append((r[col_isin], str(c).strip(), a))

    st.caption(f"{len(lignes)} ligne(s) détectée(s)")
    if st.button("Importer", type="primary", disabled=not lignes):
        if any(not c for _, c, _ in lignes):
            st.error("Indiquez un nom de contrat.")
        else:
            st.session_state["rapport"] = importer(lignes)

    if r := st.session_state.get("rapport"):
        st.success(f"{r['ajoutes']} produit(s) ajouté(s), {r['deja_presents']} déjà présent(s).")
        if r["invalides"]:
            st.error("ISIN invalides, non importés : " + ", ".join(r["invalides"]))
        if r["introuvables"]:
            st.warning("ISIN valides mais nom introuvable : " + ", ".join(r["introuvables"]))

with onglet_liste:
    contrats = mes_contrats()
    if contrats.empty:
        st.info("Aucun contrat pour l'instant. Importez vos produits dans l'onglet 1.")
    else:
        rows = (db.table("contrat_produits")
                .select("contrat_id, isin, contrats(nom), produits(nom, type_produit, statut, derniere_vl)")
                .in_("contrat_id", contrats["id"].tolist()).execute().data)
        df = pd.DataFrame([{
            "Retirer": False,
            "ISIN": r["isin"],
            "Nom": r["produits"]["nom"] or "—",
            "Type": r["produits"]["type_produit"],
            "Contrat": r["contrats"]["nom"],
            "Statut": r["produits"]["statut"],
            "VL jusqu'au": r["produits"]["derniere_vl"],
            "contrat_id": r["contrat_id"],
        } for r in rows], columns=["Retirer", "ISIN", "Nom", "Type", "Contrat", "Statut", "VL jusqu'au", "contrat_id"])

        # Récupération des VL (EODHD) pour les produits de l'utilisateur
        if st.button("Récupérer les données", help="Télécharge les VL manquantes de vos produits"):
            barre = st.progress(0.0, text="Démarrage…")
            rapport = mettre_a_jour(db, st.secrets["EODHD_API_KEY"], df["ISIN"].unique().tolist(),
                                    progression=lambda x, nom: barre.progress(x, text=nom))
            barre.progress(1.0, text="Calcul des métriques…")
            rapport["metriques"] = calculer_et_enregistrer(db, df["ISIN"].unique().tolist())
            barre.empty()
            st.session_state["rapport_vl"] = rapport
            st.rerun()
        if rv := st.session_state.pop("rapport_vl", None):
            total = sum(n for _, n in rv["maj"])
            if rv["maj"] or not (rv["sans_donnees"] or rv["erreur"]):
                st.success(f"{total} VL ajoutée(s) pour {len(rv['maj'])} produit(s). Les autres étaient à jour.")
            if rv["sans_donnees"]:
                st.warning("Aucune VL trouvée pour : " + ", ".join(rv["sans_donnees"]))
            if rv["erreur"]:
                st.error(rv["erreur"] + " — réessayez demain ou passez à l'offre payante.")
            if m := rv.get("metriques"):
                st.info(f"Métriques calculées pour {len(m['calcules'])} produit(s)."
                        + (f" Historique insuffisant (moins de 6 mois) : {', '.join(m['insuffisants'])}."
                           if m["insuffisants"] else ""))

        # Dernières métriques de chaque produit
        mets = (db.table("metriques").select("isin, date_calcul, var_cf, volatilite, sharpe, sortino")
                .in_("isin", df["ISIN"].unique().tolist() or [""]).order("date_calcul", desc=True)
                .execute().data)
        dernieres = {}
        for m in mets:
            dernieres.setdefault(m["isin"], m)
        df["VaR 97,5 % 1 an"] = df["ISIN"].map(lambda i: (dernieres.get(i) or {}).get("var_cf"))
        df["Volatilité"] = df["ISIN"].map(lambda i: (dernieres.get(i) or {}).get("volatilite"))
        df["Sharpe"] = df["ISIN"].map(lambda i: (dernieres.get(i) or {}).get("sharpe"))
        df["Sortino"] = df["ISIN"].map(lambda i: (dernieres.get(i) or {}).get("sortino"))

        f1, f2 = st.columns(2)
        filtre = f1.multiselect("Filtrer par contrat", list(contrats["nom"]))
        filtre_type = f2.multiselect("Filtrer par type", TYPES)
        if filtre:
            df = df[df["Contrat"].isin(filtre)]
        if filtre_type:
            df = df[df["Type"].isin(filtre_type)]

        if df.empty:
            st.info("Aucun produit.")
        else:
            st.caption(f"{len(df)} produit(s) · {(df['Statut'] == 'introuvable').sum()} introuvable(s)")
            df = df.sort_values(["Contrat", "Nom"]).reset_index(drop=True)
            edite = st.data_editor(
                df,
                hide_index=True, width="stretch",
                disabled=["ISIN", "Nom", "Contrat", "Statut", "VL jusqu'au",
                          "VaR 97,5 % 1 an", "Volatilité", "Sharpe", "Sortino"],
                column_config={
                    "contrat_id": None,
                    "Type": st.column_config.SelectboxColumn("Type", options=TYPES),
                    "VaR 97,5 % 1 an": st.column_config.NumberColumn(
                        help="Perte maximale sur 1 an dans 97,5 % des cas (Cornish-Fisher, méthode PRIIPs)",
                        format="percent"),
                    "Volatilité": st.column_config.NumberColumn(help="Volatilité annualisée", format="percent"),
                    "Sharpe": st.column_config.NumberColumn(format="%.2f"),
                    "Sortino": st.column_config.NumberColumn(format="%.2f"),
                },
                key="tableau",
            )
            a_retirer = edite[edite["Retirer"]]
            types_modifies = edite[(edite["Type"] != df["Type"]) & edite["Type"].notna()][["ISIN", "Type"]].drop_duplicates()
            nb = len(a_retirer) + len(types_modifies)
            if st.button(f"Enregistrer ({nb} modification(s))", type="primary", disabled=nb == 0):
                for _, l in types_modifies.iterrows():
                    db.table("produits").update({"type_produit": l["Type"]}).eq("isin", l["ISIN"]).execute()
                for _, l in a_retirer.iterrows():
                    (db.table("contrat_produits").delete()
                     .eq("contrat_id", int(l["contrat_id"])).eq("isin", l["ISIN"]).execute())
                st.rerun()


# ---------- Pied de page ----------
st.divider()
st.page_link("methodologie.py", label="Méthodologie : détail du calcul des métriques", icon="📐")
