"""Indices de référence, représentés par des ETF (cours via yfinance, dividendes réinvestis).

Chaque indice est une composition {ticker Yahoo: poids}. Les indices « mixtes » combinent
plusieurs ETF, rééquilibrés chaque semaine.
"""

REFERENCES = [
    # --- Actions : monde et grandes zones ---
    {"code": "act_monde", "categorie": "Actions", "nom": "Actions monde développé (MSCI World)", "composition": {"CW8.PA": 1}},
    {"code": "act_monde_tous", "categorie": "Actions", "nom": "Actions monde, émergents inclus (MSCI ACWI)", "composition": {"IUSQ.DE": 1}},
    {"code": "act_monde_small", "categorie": "Actions", "nom": "Actions monde petites capitalisations (MSCI World Small Cap)", "composition": {"IUSN.DE": 1}},
    {"code": "act_monde_isr", "categorie": "Actions", "nom": "Actions monde ISR (MSCI World SRI)", "composition": {"WSRI.PA": 1}},
    {"code": "act_usa", "categorie": "Actions", "nom": "Actions États-Unis (S&P 500)", "composition": {"ESE.PA": 1}},
    {"code": "act_usa_tech", "categorie": "Actions", "nom": "Actions États-Unis technologie (Nasdaq-100)", "composition": {"PUST.PA": 1}},
    {"code": "act_usa_small", "categorie": "Actions", "nom": "Actions États-Unis petites capitalisations (Russell 2000)", "composition": {"RS2K.PA": 1}},
    {"code": "act_europe", "categorie": "Actions", "nom": "Actions Europe (MSCI Europe)", "composition": {"EUNK.DE": 1}},
    {"code": "act_europe_600", "categorie": "Actions", "nom": "Actions Europe (Stoxx Europe 600)", "composition": {"MEUD.PA": 1}},
    {"code": "act_europe_small", "categorie": "Actions", "nom": "Actions Europe petites capitalisations (MSCI Europe Small Cap)", "composition": {"SMC.PA": 1}},
    {"code": "act_zone_euro", "categorie": "Actions", "nom": "Actions zone euro (Euro Stoxx 50)", "composition": {"C50.PA": 1}},
    {"code": "act_zone_euro_small", "categorie": "Actions", "nom": "Actions zone euro petites capitalisations (MSCI EMU Small Cap)", "composition": {"SXRJ.DE": 1}},
    {"code": "act_france", "categorie": "Actions", "nom": "Actions France (CAC 40)", "composition": {"CAC.PA": 1}},
    {"code": "act_royaume_uni", "categorie": "Actions", "nom": "Actions Royaume-Uni (FTSE 100, en livres)", "composition": {"ISF.L": 1}},
    {"code": "act_suisse", "categorie": "Actions", "nom": "Actions Suisse (SMI, en francs suisses)", "composition": {"CSSMI.SW": 1}},
    {"code": "act_japon", "categorie": "Actions", "nom": "Actions Japon (MSCI Japan)", "composition": {"CJ1.PA": 1}},
    {"code": "act_emergents", "categorie": "Actions", "nom": "Actions pays émergents (MSCI Emerging Markets)", "composition": {"AEEM.PA": 1}},
    {"code": "act_asie_emergente", "categorie": "Actions", "nom": "Actions Asie émergente (MSCI EM Asia)", "composition": {"AASI.PA": 1}},
    {"code": "act_chine", "categorie": "Actions", "nom": "Actions Chine (MSCI China)", "composition": {"ASI.PA": 1}},
    {"code": "act_inde", "categorie": "Actions", "nom": "Actions Inde (MSCI India)", "composition": {"CI2.PA": 1}},
    # --- Actions : styles ---
    {"code": "style_min_vol", "categorie": "Actions – style", "nom": "Actions monde faible volatilité (MSCI World Minimum Volatility)", "composition": {"IQQ0.DE": 1}},
    {"code": "style_qualite", "categorie": "Actions – style", "nom": "Actions monde qualité (MSCI World Quality)", "composition": {"IS3Q.DE": 1}},
    {"code": "style_momentum", "categorie": "Actions – style", "nom": "Actions monde momentum (MSCI World Momentum)", "composition": {"IS3R.DE": 1}},
    {"code": "style_dividendes", "categorie": "Actions – style", "nom": "Actions monde dividendes (Global Quality Dividend Growth)", "composition": {"WTEM.DE": 1}},
    # --- Actions : secteurs ---
    {"code": "sect_tech", "categorie": "Actions – secteur", "nom": "Secteur technologie monde", "composition": {"XDWT.DE": 1}},
    {"code": "sect_sante", "categorie": "Actions – secteur", "nom": "Secteur santé monde", "composition": {"XDWH.DE": 1}},
    {"code": "sect_finance", "categorie": "Actions – secteur", "nom": "Secteur financier monde", "composition": {"XDWF.DE": 1}},
    {"code": "sect_banques_europe", "categorie": "Actions – secteur", "nom": "Secteur banques Europe", "composition": {"EXV1.DE": 1}},
    {"code": "sect_energie", "categorie": "Actions – secteur", "nom": "Secteur énergie monde", "composition": {"XDW0.DE": 1}},
    {"code": "sect_industrie", "categorie": "Actions – secteur", "nom": "Secteur industrie monde", "composition": {"XDWI.DE": 1}},
    {"code": "sect_conso_cyclique", "categorie": "Actions – secteur", "nom": "Secteur consommation cyclique monde", "composition": {"XDWC.DE": 1}},
    {"code": "sect_conso_base", "categorie": "Actions – secteur", "nom": "Secteur consommation de base monde", "composition": {"XDWS.DE": 1}},
    {"code": "sect_materiaux", "categorie": "Actions – secteur", "nom": "Secteur matériaux monde", "composition": {"XDWM.DE": 1}},
    {"code": "sect_services_publics", "categorie": "Actions – secteur", "nom": "Secteur services publics monde", "composition": {"XDWU.DE": 1}},
    # --- Immobilier coté ---
    {"code": "immo_europe", "categorie": "Immobilier coté", "nom": "Immobilier coté Europe", "composition": {"IPRP.AS": 1}},
    {"code": "immo_monde", "categorie": "Immobilier coté", "nom": "Immobilier coté monde développé", "composition": {"IWDP.AS": 1}},
    # --- Obligations ---
    {"code": "obl_euro_agregat", "categorie": "Obligations", "nom": "Obligations euro, toutes catégories (Euro Aggregate)", "composition": {"EUN4.DE": 1}},
    {"code": "obl_etat_euro", "categorie": "Obligations", "nom": "Obligations d'État zone euro", "composition": {"EUNH.DE": 1}},
    {"code": "obl_etat_euro_court", "categorie": "Obligations", "nom": "Obligations d'État zone euro 1-3 ans", "composition": {"IBGS.AS": 1}},
    {"code": "obl_etat_euro_long", "categorie": "Obligations", "nom": "Obligations d'État zone euro 7-10 ans", "composition": {"SXRQ.DE": 1}},
    {"code": "obl_inflation_euro", "categorie": "Obligations", "nom": "Obligations indexées sur l'inflation zone euro", "composition": {"IBCI.AS": 1}},
    {"code": "obl_entreprises_euro", "categorie": "Obligations", "nom": "Obligations d'entreprises euro (Investment Grade)", "composition": {"EUN5.DE": 1}},
    {"code": "obl_haut_rendement_euro", "categorie": "Obligations", "nom": "Obligations haut rendement euro (High Yield)", "composition": {"EUNW.DE": 1}},
    {"code": "obl_monde_couvert", "categorie": "Obligations", "nom": "Obligations monde couvertes en euro (Global Aggregate)", "composition": {"AGGH.AS": 1}},
    {"code": "obl_usa_couvert", "categorie": "Obligations", "nom": "Obligations d'État américaines 7-10 ans couvertes en euro", "composition": {"IBB1.DE": 1}},
    {"code": "obl_emergents", "categorie": "Obligations", "nom": "Obligations pays émergents (en dollars)", "composition": {"IUS7.DE": 1}},
    {"code": "obl_convertibles", "categorie": "Obligations", "nom": "Obligations convertibles monde", "composition": {"ZPRC.DE": 1}},
    # --- Monétaire, or, matières premières ---
    {"code": "monetaire_euro", "categorie": "Monétaire", "nom": "Monétaire euro (€STR)", "composition": {"CSH2.PA": 1}},
    {"code": "or", "categorie": "Matières premières", "nom": "Or", "composition": {"GOLD.PA": 1}},
    {"code": "matieres_premieres", "categorie": "Matières premières", "nom": "Matières premières diversifiées", "composition": {"SXRS.DE": 1}},
    # --- Allocations mixtes (actions monde + obligations euro) ---
    {"code": "mixte_prudent", "categorie": "Mixte", "nom": "Mixte prudent (20 % actions monde, 80 % obligations euro)", "composition": {"CW8.PA": 0.2, "EUN4.DE": 0.8}},
    {"code": "mixte_equilibre", "categorie": "Mixte", "nom": "Mixte équilibré (50 % actions monde, 50 % obligations euro)", "composition": {"CW8.PA": 0.5, "EUN4.DE": 0.5}},
    {"code": "mixte_dynamique", "categorie": "Mixte", "nom": "Mixte dynamique (75 % actions monde, 25 % obligations euro)", "composition": {"CW8.PA": 0.75, "EUN4.DE": 0.25}},
    {"code": "mixte_flexible_or", "categorie": "Mixte", "nom": "Mixte avec or (40 % actions, 40 % obligations, 20 % or)", "composition": {"CW8.PA": 0.4, "EUN4.DE": 0.4, "GOLD.PA": 0.2}},
]

PAR_CODE = {r["code"]: r for r in REFERENCES}
TICKERS = sorted({t for r in REFERENCES for t in r["composition"]})


def nom(code: str | None) -> str:
    return PAR_CODE[code]["nom"] if code in PAR_CODE else "—"
