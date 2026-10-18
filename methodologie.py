"""Page Méthodologie : formules et calcul pas à pas des métriques."""
import datetime as dt

import pandas as pd
import streamlit as st

from navigation import pied_de_page, retour_en_haut

from base import USER_ID, db
from calculs import (JOURS, MIN_POINTS, MIN_SEMAINES, correlations, detail, lire_historique, lire_indices,
                     relatif, rendements_references, taux_sans_risque)
from indices import PAR_CODE, REFERENCES, SEUIL_ZONE


def pct(x, d=2):
    return "—" if x is None else f"{x * 100:,.{d}f} %".replace(",", " ").replace(".", ",")


def nb(x, d=4):
    return "—" if x is None else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def tpct(x, d=2):
    """Pourcentage au format LaTeX (virgule décimale, signe %)."""
    return pct(x, d).replace(",", "{,}").replace("%", r"\%").replace(" ", r"\,")


def tnb(x, d=4):
    return nb(x, d).replace(",", "{,}").replace(" ", r"\,")


retour_en_haut()
st.title("Méthodologie des calculs")
st.caption("Comment sont calculées les métriques affichées dans « Mes produits ».")

# ---------- 1. Données ----------
st.header("1. Données utilisées")
st.markdown(f"""
- **VL quotidiennes** fournies par Yahoo Finance (données Morningstar pour les fonds), identifiées par ISIN ;
  à défaut par EODHD (End Of Day Historical Data).
- **VL ajustées** des dividendes : un fonds de distribution n'apparaît pas en baisse le jour du détachement.
- **Période** : les 5 dernières années disponibles (1 an pour les produits suivis via l'offre gratuite d'EODHD).
- **Minimum** : {MIN_POINTS} VL, soit environ 6 mois. En dessous, aucune métrique n'est calculée.
- **{JOURS} jours de bourse** par an pour annualiser.
- **Taux sans risque** : moyenne de l'€STR (Euro Short-Term Rate) publié par la BCE sur la même période.
- **Mise à jour** : chaque matin (Yahoo Finance) ; tous les 30 jours pour les produits suivis via EODHD ;
  et à chaque clic sur « Récupérer les données ».
- **Listes de supports des assureurs** (Cardif, Generali, Vie Plus) : SRI, frais, SFDR, classification.
""")

# ---------- 2. Formules ----------
st.header("2. Formules")

st.subheader("Rendements quotidiens")
st.latex(r"r_t = \frac{VL_t}{VL_{t-1}} - 1 \qquad \ell_t = \ln\frac{VL_t}{VL_{t-1}}")
st.markdown("Les rendements simples $r_t$ servent à la volatilité, au Sharpe et au Sortino ; "
            "les rendements logarithmiques $\\ell_t$ servent à la VaR, comme dans la méthode PRIIPs.")

st.subheader("Rendement annualisé")
st.latex(r"R = \left(\frac{VL_{fin}}{VL_{début}}\right)^{1/T} - 1 \qquad T = \frac{\text{nombre de rendements}}{252}")

st.subheader("Volatilité annualisée")
st.latex(r"\sigma_{an} = \sigma(r_t) \times \sqrt{252}")

st.subheader("VaR Cornish-Fisher à 97,5 % sur 1 an")
st.markdown("Formule du règlement délégué PRIIPs (UE) 2017/653, annexe II, utilisée pour classer "
            "les fonds de 1 à 7 sur l'échelle SRI (Synthetic Risk Indicator) du DIC.")
st.latex(r"z = -1{,}96 + 0{,}474\,\frac{S}{\sqrt{N}} - 0{,}0687\,\frac{K}{N} + 0{,}146\,\frac{S^2}{N}")
st.latex(r"\text{VaR} = -\left(e^{\,\sigma\sqrt{N}\,z \;-\; \frac{1}{2}\sigma^2 N} - 1\right)")
st.markdown("""
- $\\sigma$ : écart-type des rendements logarithmiques quotidiens
- $S$ : skewness (asymétrie) ; négative, elle signale des baisses plus fortes que les hausses
- $K$ : excès de kurtosis ; élevé, il signale des pertes extrêmes plus fréquentes que la loi normale
- $N$ = 252 : horizon d'un an en jours de bourse
- $-1{,}96$ : quantile à 2,5 % de la loi normale ; les trois termes suivants le corrigent de $S$ et $K$

Résultat exprimé en **perte** : une VaR de 15 % signifie que, dans 97,5 % des cas, la perte sur un an ne dépasse pas 15 %.
""")

st.subheader("Ratio de Sharpe")
st.latex(r"\text{Sharpe} = \frac{R - r_f}{\sigma_{an}}")
st.markdown("Rendement obtenu au-delà du taux sans risque $r_f$, par unité de volatilité.")

st.subheader("Ratio de Sortino")
st.latex(r"\text{Sortino} = \frac{R - r_f}{\sigma_{baisse}} \qquad "
         r"\sigma_{baisse} = \sqrt{\tfrac{1}{n}\sum \min(r_t - r_{f,jour},\,0)^2} \times \sqrt{252}")
st.markdown("Comme le Sharpe, mais seule la volatilité **à la baisse** est pénalisée : "
            "un fonds qui monte fortement n'est pas sanctionné.")

st.subheader("CVaR (Conditional Value at Risk) quotidienne")
st.latex(r"\text{CVaR} = -\,\text{moyenne}\left(r_t \;\middle|\; r_t \le q_{2{,}5\%}\right)")
st.markdown("Perte moyenne lors des 2,5 % pires jours de la période. Là où la VaR donne un seuil, "
            "la CVaR mesure **l'ampleur** des pertes au-delà de ce seuil. Calculée sur l'historique réel, "
            "sans hypothèse de loi.")

st.subheader("Max Drawdown et temps de recouvrement")
st.latex(r"\text{Max Drawdown} = -\min_t\left(\frac{VL_t}{\max_{s \le t} VL_s} - 1\right)")
st.markdown("Pire baisse subie entre un plus haut et le point bas qui suit. Le **temps de recouvrement** "
            "est le nombre de jours entre ce point bas et le retour au plus haut précédent ; "
            "il reste vide si le produit n'est pas encore revenu à ce niveau.")

st.subheader("Ratio de Calmar")
st.latex(r"\text{Calmar} = \frac{R}{\text{Max Drawdown}}")
st.markdown("Rendement annuel obtenu par unité de pire baisse : plus il est élevé, mieux la performance "
            "compense les pertes subies. Calculé sur la même période que les autres métriques (5 ans au plus).")

st.subheader("Mois positifs, pire mois, pire année")
st.markdown("""
- Rendements **mensuels** calculés sur les VL de fin de mois ; le premier mois, incomplet, est écarté.
- **Mois positifs** : part des mois terminés en hausse.
- **Pire mois** : plus mauvaise performance sur un mois civil.
- **Pire année** : plus mauvaise performance sur **12 mois glissants** (d'une fin de mois à la même fin de mois
  un an plus tard). Les années civiles n'ont pas été retenues : avec 5 ans d'historique, la première et la
  dernière sont incomplètes. Vide si l'historique fait moins de 12 mois.
""")

st.subheader("Skewness et kurtosis")
st.markdown("Ce sont les paramètres $S$ et $K$ de la VaR Cornish-Fisher ci-dessus, affichés tels quels : "
            "une skewness négative signale des baisses plus fortes que les hausses ; un excès de kurtosis "
            "élevé, des pertes extrêmes plus fréquentes que la loi normale (0 pour une loi normale).")

st.subheader("Corrélation à l'indice de référence")
st.latex(r"\rho = \frac{\text{cov}(R^{hebdo}_{produit},\,R^{hebdo}_{indice})}{\sigma_{produit}\,\sigma_{indice}}")
st.markdown(f"""
- Calculée sur les **rendements hebdomadaires** (cours du vendredi) : les VL des fonds sont souvent
  publiées avec un jour de décalage par rapport à la clôture des marchés, ce qui fausserait une corrélation quotidienne.
- Au moins {MIN_SEMAINES} semaines communes.
- **Indice retenu** : par défaut, celui des {len(REFERENCES)} indices ci-dessous qui est le **plus corrélé** au produit.
  Le CGPI peut en imposer un autre dans le tableau.
- Chaque indice est représenté par un ETF (cours dividendes réinvestis, source Yahoo Finance) ;
  les indices mixtes combinent plusieurs ETF, rééquilibrés chaque semaine.
""")
st.subheader("Mesures relatives à l'indice retenu")
st.markdown(f"Sur les mêmes **rendements hebdomadaires** que la corrélation (au moins {MIN_SEMAINES} semaines communes). "
            "$R_p$ et $R_i$ : rendements annualisés du produit et de l'indice sur les semaines communes ; "
            "$r_f$ : taux sans risque.")
st.latex(r"R^2 = \rho^2 \qquad \beta = \frac{\text{cov}(r_p,\,r_i)}{\text{var}(r_i)}")
st.latex(r"\alpha = R_p - \left[r_f + \beta\,(R_i - r_f)\right]")
st.latex(r"TE = \sigma(r_p - r_i) \times \sqrt{52} \qquad IR = \frac{R_p - R_i}{TE}")
st.markdown("""
- **R²** : part des variations du produit expliquée par l'indice (0,9 = 90 %). Un R² faible rend le bêta,
  l'alpha et le ratio d'information peu significatifs.
- **Bêta** : sensibilité à l'indice ; 1,2 = le produit varie en moyenne de 1,2 % quand l'indice varie de 1 %.
- **Alpha de Jensen** : rendement annuel au-delà de ce qu'explique l'exposition à l'indice (le bêta).
- **Tracking error** : volatilité de l'écart de performance avec l'indice ; faible pour un fonds indiciel.
- **Ratio d'information** : surperformance annuelle par unité de tracking error ; il mesure la régularité
  de la surperformance du gérant.
- **Réserve** : l'indice est celui qui ressemble le plus au produit (ou celui choisi par le CGPI), pas forcément
  l'indice officiel du prospectus. Ces mesures comparent donc le produit à un indice proche, choisi a posteriori.
""")
st.subheader("Classe d'actifs et zone géographique")
st.markdown(f"""
- **Classe d'actifs** (monétaire, obligations, actions, mixte, immobilier, matières premières, alternatif,
  structuré) : d'après la classification de l'assureur ; à défaut, d'après la catégorie de l'indice le plus corrélé.
- **Zone** : celle de l'indice le plus corrélé (ex. MSCI Japan → Japon, obligations d'État euro → Zone euro).
- Si cette corrélation est inférieure à **{SEUIL_ZONE:.1f}**, la zone est « Indéterminée » plutôt que fausse.
- C'est une **zone dominante**, pas une répartition en pourcentage : un fonds flexible ou international
  peut ressembler davantage à un indice monde qu'à sa zone réelle.
""")
with st.expander(f"Liste des {len(REFERENCES)} indices de référence"):
    st.dataframe(pd.DataFrame([{
        "Catégorie": r["categorie"], "Indice": r["nom"],
        "ETF utilisé(s)": " + ".join(f"{int(p * 100)} % {t}" if p < 1 else t for t, p in r["composition"].items()),
    } for r in REFERENCES]), hide_index=True, width="stretch")

# ---------- 3. Calcul pas à pas ----------
st.header("3. Calcul pas à pas sur un de vos produits")

contrats = db.table("contrats").select("id").eq("user_id", USER_ID).execute().data
liens = (db.table("contrat_produits").select("isin, produits(nom, derniere_vl)")
         .in_("contrat_id", [c["id"] for c in contrats] or [0]).execute().data) if contrats else []
produits = {l["isin"]: l["produits"]["nom"] or l["isin"] for l in liens if l["produits"]["derniere_vl"]}

if not produits:
    st.info("Aucun produit avec des VL pour l'instant. Utilisez « Récupérer les données » dans Mes produits.")
else:
    isin = st.selectbox("Produit", list(produits), format_func=lambda i: f"{produits[i]} ({i})")
    depuis = dt.date.today() - dt.timedelta(days=365 * 5)
    with st.spinner("Calcul…"):
        vl = lire_historique(db, isin, depuis)
        rf = taux_sans_risque(depuis)
        d = detail(vl, rf)

    if d is None:
        st.warning(f"Historique insuffisant : {len(vl)} VL, il en faut au moins {MIN_POINTS}.")
    else:
        if rf is None:
            st.warning("€STR indisponible : taux sans risque pris à 0 %.")
        st.line_chart(vl.rename("VL ajustée"), height=220)

        st.subheader("Étape 1 : données")
        st.markdown(f"""
| | |
|---|---|
| Période | du {d['debut']:%d/%m/%Y} au {d['fin']:%d/%m/%Y} |
| Nombre de VL | {d['nb_vl']} |
| Nombre de rendements quotidiens | {d['nb_rendements']} |
| Durée $T$ | {d['nb_rendements']} / 252 = {nb(d['annees'], 3)} an(s) |
| Taux sans risque $r_f$ (€STR moyen) | {pct(d['rf'], 3)} |
""")

        st.subheader("Étape 2 : rendement et volatilité")
        st.latex(rf"R = \left(\frac{{{tnb(d['vl_fin'], 2)}}}{{{tnb(d['vl_debut'], 2)}}}\right)^{{1/{tnb(d['annees'], 3)}}} - 1"
                 rf" = {tpct(d['rendement'])}")
        st.latex(rf"\sigma_{{an}} = {tpct(d['vol_jour'], 3)} \times \sqrt{{252}}"
                 rf" = {tpct(d['volatilite'])}")

        st.subheader("Étape 3 : VaR Cornish-Fisher")
        st.markdown(f"""
| Paramètre | Valeur |
|---|---|
| $\\sigma$ (log, quotidien) | {pct(d['sigma_log'], 3)} |
| $S$ (skewness) | {nb(d['skew'])} |
| $K$ (excès de kurtosis) | {nb(d['kurt'])} |
| $N$ | {d['n']} |
""")
        st.latex(rf"z = -1{{,}}96 + 0{{,}}474 \times \frac{{{tnb(d['skew'])}}}{{\sqrt{{252}}}}"
                 rf" - 0{{,}}0687 \times \frac{{{tnb(d['kurt'])}}}{{252}}"
                 rf" + 0{{,}}146 \times \frac{{({tnb(d['skew'])})^2}}{{252}} = {tnb(d['z'])}")
        st.latex(rf"\text{{VaR}} = -\left(e^{{{tnb(d['var_rendement'])}}} - 1\right)"
                 rf" = {tpct(d['var_cf'])}")
        ecart = d["z"] + 1.96
        st.caption(f"Correction de Cornish-Fisher : {nb(ecart)} par rapport au quantile normal (−1,96). "
                   + ("Elle alourdit la VaR : distribution plus risquée que la loi normale."
                      if ecart < 0 else "Elle allège la VaR."))

        st.subheader("Étape 4 : Sharpe et Sortino")
        st.latex(rf"\text{{Sharpe}} = \frac{{{tpct(d['rendement'])} - {tpct(d['rf'], 3)}}}"
                 rf"{{{tpct(d['volatilite'])}}} = {tnb(d['sharpe'], 2)}")
        st.markdown(f"Volatilité à la baisse : {d['nb_baisse']} jours sur {d['nb_rendements']} sous le taux sans risque "
                    f"→ $\\sigma_{{baisse}}$ = {pct(d['vol_baisse'])}")
        st.latex(rf"\text{{Sortino}} = \frac{{{tpct(d['rendement'])} - {tpct(d['rf'], 3)}}}"
                 rf"{{{tpct(d['vol_baisse'])}}} = {tnb(d['sortino'], 2)}")

        st.subheader("Étape 5 : CVaR")
        st.markdown(f"Seuil des 2,5 % pires jours : rendement ≤ {pct(d['seuil_cvar'])}, "
                    f"soit {d['nb_pires']} jours sur {d['nb_rendements']}.")
        st.latex(rf"\text{{CVaR}} = -\text{{moyenne de ces {d['nb_pires']} rendements}} = {tpct(d['cvar'])}")

        st.subheader("Étape 6 : Max Drawdown et recouvrement")
        st.markdown(f"""
| | Date | VL |
|---|---|---|
| Plus haut | {d['date_haut']:%d/%m/%Y} | {nb(d['vl_haut'], 2)} |
| Point bas | {d['date_bas']:%d/%m/%Y} | {nb(d['vl_bas'], 2)} |
| Retour au plus haut | {f"{d['date_retour']:%d/%m/%Y}" if d['date_retour'] else "pas encore"} | |
""")
        st.latex(rf"\text{{Max Drawdown}} = -\left(\frac{{{tnb(d['vl_bas'], 2)}}}{{{tnb(d['vl_haut'], 2)}}} - 1\right)"
                 rf" = {tpct(d['max_drawdown'])}")
        st.markdown(f"Temps de recouvrement : **{d['recouvrement_jours']} jours**" if d["recouvrement_jours"] is not None
                    else "Temps de recouvrement : **non mesurable**, le produit n'est pas revenu à son plus haut.")

        st.subheader("Étape 7 : corrélation aux indices")
        with st.spinner("Lecture des indices…"):
            corr = correlations(vl, rendements_references(lire_indices(db)))
        if corr.empty:
            st.info("Indices pas encore chargés : ils le seront lors de la prochaine mise à jour quotidienne.")
        else:
            st.markdown(f"Indice le plus corrélé : **{PAR_CODE[corr.index[0]]['nom']}** (ρ = {nb(corr.iloc[0], 2)}).")
            st.dataframe(pd.DataFrame({"Indice": [PAR_CODE[c]["nom"] for c in corr.index[:10]],
                                       "Corrélation": corr.values[:10].round(3)}),
                         hide_index=True, width="stretch")

        st.subheader("Étape 8 : mesures relatives à l'indice retenu")
        produit = db.table("produits").select("indice_reference, indice_manuel").eq("isin", isin).execute().data
        code = (produit[0]["indice_reference"] if produit and produit[0]["indice_manuel"]
                else (corr.index[0] if len(corr) else None))
        refs = rendements_references(lire_indices(db)) if code else pd.DataFrame()
        rel = relatif(vl, refs[code], rf) if code in refs.columns else None
        if rel is None:
            st.info(f"Non calculables : il faut au moins {MIN_SEMAINES} semaines communes avec l'indice retenu.")
        else:
            st.markdown(f"""
Indice retenu : **{PAR_CODE[code]['nom']}**, {rel['nb_semaines']} semaines communes
(du {rel['debut']:%d/%m/%Y} au {rel['fin']:%d/%m/%Y}).

| | Valeur |
|---|---|
| $R_p$ (produit, annualisé) | {pct(rel['rendement_produit'])} |
| $R_i$ (indice, annualisé) | {pct(rel['rendement_indice'])} |
| $\\rho$ | {nb(rel['correlation'], 3)} |
""")
            st.latex(rf"R^2 = ({tnb(rel['correlation'], 3)})^2 = {tnb(rel['r2'], 3)}")
            st.latex(rf"\beta = {tnb(rel['beta'], 3)}")
            st.latex(rf"\alpha = {tpct(rel['rendement_produit'])} - \left[{tpct(rel['rf'], 3)} + {tnb(rel['beta'], 3)}"
                     rf" \times ({tpct(rel['rendement_indice'])} - {tpct(rel['rf'], 3)})\right] = {tpct(rel['alpha'])}")
            st.latex(rf"TE = {tpct(rel['tracking_error'])} \qquad IR = \frac{{{tpct(rel['rendement_produit'])} - "
                     rf"({tpct(rel['rendement_indice'])})}}{{{tpct(rel['tracking_error'])}}} = {tnb(rel['ratio_information'], 2)}")

        st.subheader("Étape 9 : Calmar, mois et années")
        if d["calmar"] is not None:
            st.latex(rf"\text{{Calmar}} = \frac{{{tpct(d['rendement'])}}}{{{tpct(d['max_drawdown'])}}} = {tnb(d['calmar'], 2)}")
        st.markdown(f"""
| | Valeur |
|---|---|
| Mois positifs | {d['nb_mois_positifs']} sur {d['nb_mois']} = {pct(d['pct_mois_positifs'], 1)} |
| Pire mois | {pct(d['pire_mois'])}{f" ({d['date_pire_mois']:%m/%Y})" if d['date_pire_mois'] else ""} |
| Pire année (12 mois glissants) | {pct(d['pire_annee'])}{f" (12 mois finissant en {d['fin_pire_annee']:%m/%Y})" if d['fin_pire_annee'] else " (historique inférieur à 12 mois)"} |
| Skewness / kurtosis | {nb(d['skew'], 2)} / {nb(d['kurt'], 2)} (voir étape 3) |
""")

# ---------- 4. Limites ----------
st.header("4. Limites")
st.markdown("""
- **Historique court** : la méthode PRIIPs prévoit 5 ans de données ; sur 1 an, les résultats dépendent fortement de l'année écoulée.
- **Passé ≠ futur** : toutes ces mesures sont historiques.
- **Sharpe et Sortino** dépendent de la période : un même fonds peut changer de classement d'une année à l'autre.
- **Cornish-Fisher** reste une approximation : elle devient instable pour des distributions très asymétriques.
- **CVaR quotidienne** : elle mesure un risque sur un jour, à ne pas comparer directement à la VaR sur un an.
- **Données Yahoo Finance** : source non officielle ; certains jours de VL manquent, le rendement suivant couvre
  alors deux jours, ce qui peut légèrement fausser la volatilité et la VaR.
- **Listes des assureurs** datées (juillet et novembre 2025) : SRI et frais ont pu évoluer depuis.
- **Bêta, alpha, tracking error, ratio d'information** : mesurés contre l'indice le plus ressemblant, choisi
  a posteriori ; si le R² est faible, ces chiffres ont peu de sens.
- **Frais totaux** : frais du fonds + frais de gestion du contrat, d'après les listes des assureurs (et les frais
  saisis pour vos contrats dans « Mes produits ») ; les frais de versement et d'arbitrage ne sont pas inclus.
- **Indices de référence** : ce sont des approximations par ETF ; l'indice officiel du prospectus peut différer.
  Les indices Royaume-Uni et Suisse sont en devise locale.
""")

pied_de_page("methodologie.py")
