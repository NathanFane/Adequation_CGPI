"""Colonnes de métriques communes aux tableaux « Mes produits » et « Univers d'investissement »."""
import streamlit as st

# Libellé affiché -> champ des vues metriques_actuelles / produits_complets
METRIQUES = {
    "Rendement annuel": "rendement_annuel", "Volatilité": "volatilite", "VaR 97,5 % 1 an": "var_cf",
    "CVaR 1 jour": "cvar", "Max Drawdown": "max_drawdown", "Recouvrement (jours)": "recouvrement_jours",
    "Pire mois": "pire_mois", "Pire année": "pire_annee", "Mois positifs": "pct_mois_positifs",
    "Sharpe": "sharpe", "Sortino": "sortino", "Calmar": "calmar",
    "Corrélation à l'indice": "correlation_indice", "R²": "r2", "Bêta": "beta", "Alpha": "alpha",
    "Tracking error": "tracking_error", "Ratio d'information": "ratio_information",
    "Skewness": "skewness", "Kurtosis": "kurtosis",
}


def _pct(aide=None):
    return st.column_config.NumberColumn(help=aide, format="percent")


def _nb(aide=None):
    return st.column_config.NumberColumn(help=aide, format="%.2f")


CONFIG = {
    "Frais du fonds": _pct("Frais de gestion du fonds (le plus bas des listes des assureurs)"),
    "Frais totaux": _pct("Frais du fonds + frais de gestion du contrat"),
    "Rendement annuel": _pct("Rendement annualisé sur la période (5 ans au plus)"),
    "Volatilité": _pct("Volatilité annualisée"),
    "VaR 97,5 % 1 an": _pct("Perte maximale sur 1 an dans 97,5 % des cas (Cornish-Fisher, méthode PRIIPs)"),
    "CVaR 1 jour": _pct("Perte moyenne lors des 2,5 % pires jours"),
    "Max Drawdown": _pct("Pire baisse depuis un plus haut"),
    "Recouvrement (jours)": st.column_config.NumberColumn(
        help="Jours entre le point bas et le retour au plus haut (vide : pas encore revenu)"),
    "Pire mois": _pct("Plus mauvaise performance sur un mois civil"),
    "Pire année": _pct("Plus mauvaise performance sur 12 mois glissants"),
    "Mois positifs": _pct("Part des mois civils terminés en hausse"),
    "Sharpe": _nb("Rendement au-delà du taux sans risque (€STR), par unité de volatilité"),
    "Sortino": _nb("Comme le Sharpe, mais seule la volatilité à la baisse est pénalisée"),
    "Calmar": _nb("Rendement annuel ÷ Max Drawdown"),
    "Corrélation à l'indice": _nb("Corrélation des rendements hebdomadaires avec l'indice retenu"),
    "R²": _nb("Part des variations du fonds expliquée par l'indice retenu (corrélation²)"),
    "Bêta": _nb("Sensibilité à l'indice : 1,2 = le fonds varie en moyenne de 1,2 % quand l'indice varie de 1 %"),
    "Alpha": _pct("Alpha de Jensen : rendement annuel au-delà de ce qu'explique le bêta"),
    "Tracking error": _pct("Volatilité annualisée de l'écart de performance avec l'indice"),
    "Ratio d'information": _nb("Surperformance annuelle par rapport à l'indice ÷ tracking error"),
    "Skewness": _nb("Asymétrie des rendements : négative = baisses plus fortes que les hausses"),
    "Kurtosis": _nb("Excès de kurtosis : élevé = pertes extrêmes plus fréquentes que la loi normale"),
}
