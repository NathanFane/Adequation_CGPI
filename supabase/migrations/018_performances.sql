-- Performances 3 mois / 6 mois / 1 an et durée d'historique (à exécuter une fois dans Supabase :
-- SQL Editor > Run, AVANT le déploiement du code)
alter table metriques
  add column if not exists perf_3m           numeric,
  add column if not exists perf_6m           numeric,
  add column if not exists perf_1an          numeric,
  add column if not exists historique_annees numeric;   -- années de VL disponibles (5 au plus)

create or replace view metriques_actuelles with (security_invoker = true) as
select distinct on (isin) * from metriques order by isin, date_calcul desc;

create or replace view produits_complets with (security_invoker = true) as
select p.isin, p.nom, p.type_produit, p.classe_actifs, p.zone, p.indice_reference,
       p.derniere_vl, p.source_vl,
       s.contrats, s.assureurs, s.sri, s.sfdr, s.frais_actif, s.label_isr,
       m.date_calcul, m.rendement_annuel, m.volatilite, m.var_cf, m.cvar, m.max_drawdown,
       m.recouvrement_jours, m.sharpe, m.sortino, m.correlation_indice,
       p.derniere_maj,
       s.frais_totaux,
       m.r2, m.beta, m.alpha, m.tracking_error, m.ratio_information, m.calmar,
       m.pct_mois_positifs, m.pire_mois, m.pire_annee, m.skewness, m.kurtosis,
       m.perf_3m, m.perf_6m, m.perf_1an, m.historique_annees
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
