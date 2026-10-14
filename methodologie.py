"""Page Méthodologie : formules et calcul pas à pas des métriques."""
import datetime as dt

import pandas as pd
import streamlit as st

from base import USER_ID, db
from calculs import (JOURS, MIN_POINTS, MIN_SEMAINES, correlations, detail, lire_historique, lire_indices,
                     rendements_references, taux_sans_risque)
from indices import PAR_CODE, REFERENCES


def pct(x, d=2):
    return "—" if x is None else f"{x * 100:,.{d}f} %".replace(",", " ").replace(".", ",")


def nb(x, d=4):
    return "—" if x is None else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def tpct(x, d=2):
    """Pourcentage au format LaTeX (virgule décimale, signe %)."""
    return pct(x, d).replace(",", "{,}").replace("%", r"\%").replace(" ", r"\,")


def tnb(x, d=4):
    return nb(x, d).replace(",", "{,}").replace(" ", r"\,")


st.page_link("accueil.py", label="Retour à mes produits", icon="⬅️")
st.title("Méthodologie des calculs")
st.caption("Comment sont calculées les métriques affichées dans « Mes produits ».")

# ---------- 1. Données ----------
st.header("1. Données utilisées")
st.markdown(f"""
- **VL quotidiennes** fournies par EODHD (End Of Day Historical Data), identifiées par ISIN.
- **VL ajustées** des dividendes : un fonds de distribution n'apparaît pas en baisse le jour du détachement.
- **Période** : les 5 dernières années disponibles (1 an avec l'offre gratuite d'EODHD).
- **Minimum** : {MIN_POINTS} VL, soit environ 6 mois. En dessous, aucune métrique n'est calculée.
- **{JOURS} jours de bourse** par an pour annualiser.
- **Taux sans risque** : moyenne de l'€STR (Euro Short-Term Rate) publié par la BCE sur la même période.
- **Mise à jour** : chaque matin du mardi au samedi, et à chaque clic sur « Récupérer les données ».
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

# ---------- 4. Limites ----------
st.header("4. Limites")
st.markdown("""
- **Historique court** : la méthode PRIIPs prévoit 5 ans de données ; sur 1 an, les résultats dépendent fortement de l'année écoulée.
- **Passé ≠ futur** : toutes ces mesures sont historiques.
- **Sharpe et Sortino** dépendent de la période : un même fonds peut changer de classement d'une année à l'autre.
- **Cornish-Fisher** reste une approximation : elle devient instable pour des distributions très asymétriques.
- **CVaR quotidienne** : elle mesure un risque sur un jour, à ne pas comparer directement à la VaR sur un an.
- **Indices de référence** : ce sont des approximations par ETF ; l'indice officiel du prospectus peut différer.
  Les indices Royaume-Uni et Suisse sont en devise locale.
""")
