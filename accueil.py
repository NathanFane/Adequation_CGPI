"""Page d'accueil : import et visualisation des produits par contrat."""
import io

import pandas as pd
import streamlit as st

from navigation import pied_de_page

from calculs import calculer_et_enregistrer
from collecte import _tout, actualiser
from base import USER_ID, db
from isin import est_valide, extraire, normaliser
from indices import PAR_CODE, REFERENCES, ZONES
from openfigi import TYPES, infos_produits

AUTO = "Automatique (meilleure corrélation)"
NOMS_CLASSES = {"monetaire": "Monétaire", "obligations": "Obligations", "actions": "Actions", "mixte": "Mixte",
                "immobilier": "Immobilier", "matieres_premieres": "Matières premières",
                "alternatif": "Alternatif", "structure": "Structuré / à formule"}
NOMS_INDICES = [AUTO] + [r["nom"] for r in REFERENCES]
CODE_PAR_NOM = {r["nom"]: r["code"] for r in REFERENCES}



def premier(valeur):
    """Un même ISIN peut figurer dans plusieurs contrats : on prend sa première valeur."""
    return valeur.iloc[0] if isinstance(valeur, pd.Series) else valeur


# ---------- Suppression en masse ----------

def _retirer_liens(liens):
    """Supprime des rattachements contrat-produit par lots (une requête par contrat et par 200 ISIN)."""
    par_contrat = {}
    for l in liens:
        par_contrat.setdefault(l["contrat_id"], []).append(l["isin"])
    for cid, isins in par_contrat.items():
        for i in range(0, len(isins), 200):
            db.table("contrat_produits").delete().eq("contrat_id", cid).in_("isin", isins[i:i + 200]).execute()


def suppression_en_masse(vue: pd.DataFrame, contrats: pd.DataFrame):
    """Retirer d'un coup les lignes affichées (selon les filtres), ou supprimer des contrats entiers."""
    with st.expander("Suppression en masse"):
        st.markdown(f"**Retirer de leurs contrats les {len(vue)} ligne(s) affichée(s)** "
                    "(utilisez les filtres ci-dessus pour choisir lesquelles).")
        ok1 = st.checkbox(f"Je confirme le retrait de {len(vue)} ligne(s)", key="confirme_retrait_masse")
        if st.button("Retirer les lignes affichées", disabled=not ok1 or vue.empty):
            liens = [{"contrat_id": int(l["contrat_id"]), "isin": l["ISIN"],
                      "frais_specifiques": en_decimal(l["Frais spécifiques (%)"])} for _, l in vue.iterrows()]
            with st.spinner("Retrait en cours…"):
                _retirer_liens(liens)
            st.session_state["dernier_enregistrement"] = {
                "resume": f"{len(liens)} retrait(s) du contrat", "retraits": liens, "types": [], "indices": []}
            st.session_state["version_tableau"] = st.session_state.get("version_tableau", 0) + 1
            st.rerun()

        st.divider()
        st.markdown("**Supprimer des contrats entiers** (le contrat et la liste de ses produits ; "
                    "les fonds restent dans l'univers d'investissement).")
        choix = st.multiselect("Contrats à supprimer", list(contrats["nom"]), key="contrats_a_supprimer")
        ok2 = st.checkbox("Je confirme la suppression de ces contrats", key="confirme_suppression_contrats")
        if st.button("Supprimer les contrats choisis", disabled=not (choix and ok2)):
            supprimes = []
            with st.spinner("Suppression en cours…"):
                for _, c in contrats[contrats["nom"].isin(choix)].iterrows():
                    liens = _tout(db.table("contrat_produits").select("isin, frais_specifiques")
                                  .eq("contrat_id", int(c["id"])).order("isin"))
                    contrat = {k: (None if pd.isna(c[k]) else (c[k].item() if hasattr(c[k], "item") else c[k])) for k in
                               ("nom", "assureur", "frais_gestion_uc", "frais_gestion_euro",
                                "frais_versement", "frais_arbitrage")}
                    contrat["user_id"] = USER_ID
                    supprimes.append((contrat, liens))
                    db.table("contrats").delete().eq("id", int(c["id"])).eq("user_id", USER_ID).execute()
            st.session_state["dernier_enregistrement"] = {
                "resume": f"{len(supprimes)} contrat(s) supprimé(s)", "contrats_supprimes": supprimes,
                "retraits": [], "types": [], "indices": []}
            st.session_state["version_tableau"] = st.session_state.get("version_tableau", 0) + 1
            st.rerun()


# ---------- Accès aux données ----------

def mes_contrats() -> pd.DataFrame:
    rows = (db.table("contrats").select("id, nom, assureur, frais_gestion_uc, frais_gestion_euro, "
                                        "frais_versement, frais_arbitrage")
            .eq("user_id", USER_ID).order("nom").execute().data)
    return pd.DataFrame(rows, columns=["id", "nom", "assureur", "frais_gestion_uc", "frais_gestion_euro",
                                       "frais_versement", "frais_arbitrage"])


def en_pourcent(x):
    return None if x is None or pd.isna(x) else round(float(x) * 100, 4)


def en_decimal(x):
    return None if x is None or pd.isna(x) else round(float(x) / 100, 6)


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

onglet_liste, onglet_import = st.tabs(["1. Visualiser", "2. Importer"])

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
    # Annulation du dernier enregistrement
    if precedent := st.session_state.get("dernier_enregistrement"):
        c1, c2 = st.columns([4, 1])
        c1.success(precedent["resume"] + " enregistré(s).")
        if c2.button("Annuler", help="Rétablit la situation d'avant le dernier enregistrement"):
            # Contrats supprimés : recréés (nouvel identifiant) avec leurs produits
            for contrat, liens in precedent.get("contrats_supprimes", []):
                nouvel_id = db.table("contrats").insert(contrat).execute().data[0]["id"]
                for l in liens:
                    l["contrat_id"] = nouvel_id
                for i in range(0, len(liens), 500):
                    db.table("contrat_produits").upsert(liens[i:i + 500], on_conflict="contrat_id,isin").execute()
            retraits = precedent["retraits"]
            for i in range(0, len(retraits), 500):
                db.table("contrat_produits").upsert(retraits[i:i + 500], on_conflict="contrat_id,isin").execute()
            for isin, type_avant in precedent["types"]:
                db.table("produits").update({"type_produit": type_avant}).eq("isin", isin).execute()
            for cid, isin, ancien in precedent.get("frais", []):
                (db.table("contrat_produits").update({"frais_specifiques": ancien})
                 .eq("contrat_id", cid).eq("isin", isin).execute())
            for isin, maj in precedent["indices"]:
                db.table("produits").update(maj).eq("isin", isin).execute()
            if precedent["indices"]:
                calculer_et_enregistrer(db, [i for i, _ in precedent["indices"]])
            del st.session_state["dernier_enregistrement"]
            st.session_state["version_tableau"] = st.session_state.get("version_tableau", 0) + 1
            st.rerun()

    contrats = mes_contrats()
    if contrats.empty:
        st.info("Aucun contrat pour l'instant. Importez vos produits dans l'onglet 2.")
    else:
        rows = _tout(db.table("contrat_produits")
                     .select("contrat_id, isin, frais_specifiques, contrats(nom), produits(nom, type_produit, "
                             "classe_actifs, zone, statut, derniere_vl, derniere_maj, source_vl, indice_reference, "
                             "indice_manuel)")
                     .in_("contrat_id", contrats["id"].tolist()).order("isin").order("contrat_id"))
        df = pd.DataFrame([{
            "Retirer du contrat": False,
            "ISIN": r["isin"],
            "Nom": r["produits"]["nom"] or "—",
            "Type": r["produits"]["type_produit"],
            "Classe d'actifs": NOMS_CLASSES.get(r["produits"]["classe_actifs"]),
            "Zone": r["produits"]["zone"],
            "Contrat": r["contrats"]["nom"],
            "Statut": r["produits"]["statut"],
            "VL jusqu'au": r["produits"]["derniere_vl"],
            "Mis à jour le": (r["produits"].get("derniere_maj") or "")[:10] or None,
            "Source des VL": {"yahoo": "Yahoo Finance", "eodhd": "EODHD"}.get(r["produits"].get("source_vl")),
            "Indice de référence": (PAR_CODE[r["produits"]["indice_reference"]]["nom"]
                                    if r["produits"]["indice_manuel"] and r["produits"]["indice_reference"] in PAR_CODE
                                    else AUTO),
            "Indice retenu": PAR_CODE.get(r["produits"]["indice_reference"], {}).get("nom"),
            "Frais spécifiques (%)": en_pourcent(r.get("frais_specifiques")),
            "contrat_id": r["contrat_id"],
        } for r in rows], columns=["Retirer du contrat", "ISIN", "Nom", "Type", "Classe d'actifs", "Zone", "Contrat",
                                   "Statut", "VL jusqu'au", "Mis à jour le", "Source des VL",
                                   "Indice de référence", "Indice retenu", "Frais spécifiques (%)", "contrat_id"])

        # Frais des contrats
        with st.expander("Frais de mes contrats"):
            st.caption("En % par an pour les frais de gestion, en % du montant pour les versements et arbitrages. "
                       "Un support facturé différemment se règle dans la colonne « Frais spécifiques » du tableau.")
            frais = pd.DataFrame({
                "id": contrats["id"], "Contrat": contrats["nom"], "Assureur": contrats["assureur"],
                "Gestion UC (%)": contrats["frais_gestion_uc"].map(en_pourcent),
                "Gestion fonds euros (%)": contrats["frais_gestion_euro"].map(en_pourcent),
                "Versements (%)": contrats["frais_versement"].map(en_pourcent),
                "Arbitrages (%)": contrats["frais_arbitrage"].map(en_pourcent),
            })
            frais_edites = st.data_editor(
                frais, hide_index=True, width="stretch", disabled=["Contrat"],
                column_config={"id": None, **{c: st.column_config.NumberColumn(min_value=0, max_value=20, format="%.2f")
                                              for c in frais.columns if c.endswith("(%)")}},
                key=f"frais_{st.session_state.get('version_frais', 0)}",
            )
            modifie = not frais_edites.fillna(-1).equals(frais.fillna(-1))
            if st.button("Enregistrer les frais", disabled=not modifie):
                for _, l in frais_edites.iterrows():
                    db.table("contrats").update({
                        "assureur": l["Assureur"] or None,
                        "frais_gestion_uc": en_decimal(l["Gestion UC (%)"]),
                        "frais_gestion_euro": en_decimal(l["Gestion fonds euros (%)"]),
                        "frais_versement": en_decimal(l["Versements (%)"]),
                        "frais_arbitrage": en_decimal(l["Arbitrages (%)"]),
                    }).eq("id", int(l["id"])).eq("user_id", USER_ID).execute()
                st.session_state["version_frais"] = st.session_state.get("version_frais", 0) + 1
                st.rerun()

        # Récupération des VL (Yahoo Finance, EODHD en secours) pour les produits de l'utilisateur
        if st.button("Récupérer les données", help="Télécharge les VL manquantes de vos produits"):
            barre = st.progress(0.0, text="Démarrage…")
            rapport = actualiser(db, st.secrets["EODHD_API_KEY"], df["ISIN"].unique().tolist(),
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
        mes_isins = set(df["ISIN"])
        dernieres = {m["isin"]: m for m in _tout(
            db.table("metriques_actuelles").select("isin, date_calcul, rendement_annuel, volatilite, var_cf, cvar, "
                                                   "max_drawdown, recouvrement_jours, sharpe, sortino, "
                                                   "correlation_indice").order("isin"))
            if m["isin"] in mes_isins}
        COLONNES_METRIQUES = {
            "Rendement annuel": "rendement_annuel", "Volatilité": "volatilite", "VaR 97,5 % 1 an": "var_cf",
            "CVaR 1 jour": "cvar", "Max Drawdown": "max_drawdown", "Recouvrement (jours)": "recouvrement_jours",
            "Sharpe": "sharpe", "Sortino": "sortino", "Corrélation à l'indice": "correlation_indice",
        }
        for colonne, champ in COLONNES_METRIQUES.items():
            df[colonne] = df["ISIN"].map(lambda i, c=champ: (dernieres.get(i) or {}).get(c))

        f1, f2, f3, f4 = st.columns(4)
        filtre = f1.multiselect("Filtrer par contrat", list(contrats["nom"]))
        filtre_type = f2.multiselect("Filtrer par type", TYPES)
        filtre_classe = f3.multiselect("Filtrer par classe d'actifs", list(NOMS_CLASSES.values()))
        filtre_zone = f4.multiselect("Filtrer par zone", ZONES)
        if filtre:
            df = df[df["Contrat"].isin(filtre)]
        if filtre_type:
            df = df[df["Type"].isin(filtre_type)]
        if filtre_classe:
            df = df[df["Classe d'actifs"].isin(filtre_classe)]
        if filtre_zone:
            df = df[df["Zone"].isin(filtre_zone)]

        if df.empty:
            st.info("Aucun produit.")
        else:
            suppression_en_masse(df, contrats)
            st.caption(f"{len(df)} ligne(s) = {df['ISIN'].nunique()} produit(s) distinct(s) "
                       "(un produit présent dans 3 contrats compte pour 3 lignes) · "
                       f"{(df['Statut'] == 'introuvable').sum()} introuvable(s) · "
                       "cochez « Retirer du contrat » ou modifiez le type, l'indice ou les frais spécifiques, "
                       "puis enregistrez.")
            df = df.sort_values(["Contrat", "Nom"]).reset_index(drop=True)
            edite = st.data_editor(
                df,
                hide_index=True, width="stretch",
                disabled=["ISIN", "Nom", "Classe d'actifs", "Zone", "Contrat", "Statut", "VL jusqu'au", "Mis à jour le",
                          "Source des VL", "Indice retenu",
                          *COLONNES_METRIQUES],
                column_config={
                    "contrat_id": None,
                    "Classe d'actifs": st.column_config.TextColumn(
                        help="Selon la classification de l'assureur ; à défaut, selon l'indice le plus corrélé"),
                    "Zone": st.column_config.TextColumn(
                        help="Zone de l'indice le plus corrélé ; « Indéterminée » si la corrélation est inférieure à 0,7"),
                    "Type": st.column_config.SelectboxColumn("Type", options=TYPES),
                    "VaR 97,5 % 1 an": st.column_config.NumberColumn(
                        help="Perte maximale sur 1 an dans 97,5 % des cas (Cornish-Fisher, méthode PRIIPs)",
                        format="percent"),
                    "Volatilité": st.column_config.NumberColumn(help="Volatilité annualisée", format="percent"),
                    "Rendement annuel": st.column_config.NumberColumn(format="percent"),
                    "CVaR 1 jour": st.column_config.NumberColumn(
                        help="Perte moyenne lors des 2,5 % pires jours", format="percent"),
                    "Max Drawdown": st.column_config.NumberColumn(
                        help="Pire baisse depuis un plus haut", format="percent"),
                    "Recouvrement (jours)": st.column_config.NumberColumn(
                        help="Jours entre le point bas et le retour au plus haut (vide : pas encore revenu)"),
                    "Sharpe": st.column_config.NumberColumn(format="%.2f"),
                    "Sortino": st.column_config.NumberColumn(format="%.2f"),
                    "Indice de référence": st.column_config.SelectboxColumn(
                        options=NOMS_INDICES, width="medium",
                        help="Automatique : l'indice le plus corrélé au produit. Vous pouvez en imposer un."),
                    "Frais spécifiques (%)": st.column_config.NumberColumn(
                        min_value=0, max_value=20, format="%.2f",
                        help="À remplir seulement si ce support est facturé différemment des autres UC du contrat"),
                    "Corrélation à l'indice": st.column_config.NumberColumn(
                        help="Corrélation des rendements hebdomadaires avec l'indice retenu", format="%.2f"),
                },
                key=f"tableau_{st.session_state.get('version_tableau', 0)}",
            )
            a_retirer = edite[edite["Retirer du contrat"]]
            types_modifies = edite[(edite["Type"] != df["Type"]) & edite["Type"].notna()][["ISIN", "Type"]].drop_duplicates()
            indices_modifies = edite[edite["Indice de référence"] != df["Indice de référence"]][
                ["ISIN", "Indice de référence"]].drop_duplicates("ISIN")
            frais_modifies = edite[edite["Frais spécifiques (%)"].fillna(-1) != df["Frais spécifiques (%)"].fillna(-1)]
            nb = len(a_retirer) + len(types_modifies) + len(indices_modifies) + len(frais_modifies)
            resume = ", ".join(x for x in [
                f"{len(a_retirer)} retrait(s) du contrat" if len(a_retirer) else "",
                f"{len(types_modifies)} type(s) modifié(s)" if len(types_modifies) else "",
                f"{len(indices_modifies)} indice(s) modifié(s)" if len(indices_modifies) else "",
                f"{len(frais_modifies)} frais modifié(s)" if len(frais_modifies) else "",
            ] if x)

            b1, b2, _ = st.columns([2, 2, 3])
            enregistrer = b1.button(f"Enregistrer : {resume}" if nb else "Aucune modification", type="primary",
                                    disabled=nb == 0, width="stretch")
            if b2.button("Annuler les modifications", disabled=nb == 0, width="stretch",
                         help="Remet le tableau dans son état d'origine, sans rien enregistrer"):
                st.session_state["version_tableau"] = st.session_state.get("version_tableau", 0) + 1
                st.rerun()

            if enregistrer:
                avant = df.set_index("ISIN")
                precedent = {
                    "resume": resume,
                    "retraits": [{"contrat_id": int(l["contrat_id"]), "isin": l["ISIN"],
                                  "frais_specifiques": en_decimal(l["Frais spécifiques (%)"])}
                                 for _, l in a_retirer.iterrows()],
                    "types": [(l["ISIN"], premier(avant.loc[l["ISIN"], "Type"])) for _, l in types_modifies.iterrows()],
                    "indices": [],
                    "frais": [(int(l["contrat_id"]), l["ISIN"], en_decimal(df.loc[i, "Frais spécifiques (%)"]))
                              for i, l in frais_modifies.iterrows()],
                }
                for _, l in frais_modifies.iterrows():
                    (db.table("contrat_produits").update({"frais_specifiques": en_decimal(l["Frais spécifiques (%)"])})
                     .eq("contrat_id", int(l["contrat_id"])).eq("isin", l["ISIN"]).execute())
                for _, l in types_modifies.iterrows():
                    db.table("produits").update({"type_produit": l["Type"]}).eq("isin", l["ISIN"]).execute()
                for _, l in indices_modifies.iterrows():
                    ancien = premier(avant.loc[l["ISIN"], "Indice de référence"])
                    precedent["indices"].append((l["ISIN"], {"indice_manuel": False} if ancien == AUTO
                                                 else {"indice_reference": CODE_PAR_NOM[ancien], "indice_manuel": True}))
                    choix_indice = l["Indice de référence"]
                    db.table("produits").update(
                        {"indice_manuel": False} if choix_indice == AUTO
                        else {"indice_reference": CODE_PAR_NOM[choix_indice], "indice_manuel": True}
                    ).eq("isin", l["ISIN"]).execute()
                if len(indices_modifies):
                    with st.spinner("Recalcul des corrélations…"):
                        calculer_et_enregistrer(db, indices_modifies["ISIN"].tolist())
                for _, l in a_retirer.iterrows():
                    (db.table("contrat_produits").delete()
                     .eq("contrat_id", int(l["contrat_id"])).eq("isin", l["ISIN"]).execute())
                st.session_state["dernier_enregistrement"] = precedent
                st.session_state["version_tableau"] = st.session_state.get("version_tableau", 0) + 1
                st.rerun()


pied_de_page("accueil.py")
