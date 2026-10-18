-- Nouvelles métriques (à exécuter une fois dans Supabase : SQL Editor > Run, AVANT le déploiement du code)
alter table metriques
  add column if not exists r2                numeric,   -- corrélation² à l'indice retenu
  add column if not exists beta              numeric,
  add column if not exists alpha             numeric,   -- alpha de Jensen annualisé
  add column if not exists tracking_error    numeric,   -- volatilité annualisée de l'écart à l'indice
  add column if not exists ratio_information numeric,
  add column if not exists calmar            numeric,   -- rendement annuel ÷ max drawdown
  add column if not exists pct_mois_positifs numeric,
  add column if not exists pire_mois         numeric,
  add column if not exists pire_annee        numeric,   -- pire performance sur 12 mois glissants
  add column if not exists skewness          numeric,   -- asymétrie des rendements logarithmiques quotidiens
  add column if not exists kurtosis          numeric;   -- excès de kurtosis

-- La vue reprend les nouvelles colonnes de la table (ajoutées en fin de liste)
create or replace view metriques_actuelles with (security_invoker = true) as
select distinct on (isin) * from metriques order by isin, date_calcul desc;

-- Frais totaux d'un support dans un contrat : ceux de la liste de l'assureur, sinon frais du fonds + frais
-- du contrat. Dans l'univers : le plus bas des contrats où le fonds est référencé.
create or replace view produits_complets with (security_invoker = true) as
select p.isin, p.nom, p.type_produit, p.classe_actifs, p.zone, p.indice_reference,
       p.derniere_vl, p.source_vl,
       s.contrats, s.assureurs, s.sri, s.sfdr, s.frais_actif, s.label_isr,
       m.date_calcul, m.rendement_annuel, m.volatilite, m.var_cf, m.cvar, m.max_drawdown,
       m.recouvrement_jours, m.sharpe, m.sortino, m.correlation_indice,
       p.derniere_maj,
       s.frais_totaux,
       m.r2, m.beta, m.alpha, m.tracking_error, m.ratio_information, m.calmar,
       m.pct_mois_positifs, m.pire_mois, m.pire_annee, m.skewness, m.kurtosis
from produits p
join metriques_actuelles m on m.isin = p.isin
left join (
  select isin,
         array_agg(distinct contrat order by contrat) as contrats,
         string_agg(distinct assureur, ', ')          as assureurs,
         max(sri)         as sri,
         max(sfdr)        as sfdr,
         min(frais_actif) as frais_actif,
         min(coalesce(frais_totaux, frais_actif + frais_contrat)) as frais_totaux,
         bool_or(label_isr) as label_isr
  from supports_contrat_actuels group by isin
) s on s.isin = p.isin
where p.statut = 'valide' and p.derniere_vl is not null;
