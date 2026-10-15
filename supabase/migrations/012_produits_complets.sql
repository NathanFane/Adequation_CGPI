-- Produits complets / incomplets (à exécuter une fois dans Supabase : SQL Editor > Run)
-- Ce sont des vues : elles se mettent à jour d'elles-mêmes. Dès qu'un produit a ses VL et ses
-- métriques, il passe de produits_incomplets à produits_complets, sans aucune copie de données.

-- Les vues respectent les droits de l'utilisateur qui les lit (recommandation Supabase)
alter view metriques_actuelles set (security_invoker = true);
alter view supports_contrat_actuels set (security_invoker = true);

create view produits_complets with (security_invoker = true) as
select p.isin, p.nom, p.type_produit, p.classe_actifs, p.zone, p.indice_reference,
       p.derniere_vl, p.source_vl,
       s.contrats, s.assureurs, s.sri, s.sfdr, s.frais_actif, s.label_isr,
       m.date_calcul, m.rendement_annuel, m.volatilite, m.var_cf, m.cvar, m.max_drawdown,
       m.recouvrement_jours, m.sharpe, m.sortino, m.correlation_indice
from produits p
join metriques_actuelles m on m.isin = p.isin
left join (
  select isin,
         array_agg(distinct contrat order by contrat) as contrats,
         string_agg(distinct assureur, ', ')          as assureurs,
         max(sri)         as sri,          -- le plus prudent si deux listes diffèrent
         max(sfdr)        as sfdr,
         min(frais_actif) as frais_actif,
         bool_or(label_isr) as label_isr
  from supports_contrat_actuels group by isin
) s on s.isin = p.isin
where p.statut = 'valide' and p.derniere_vl is not null;

create view produits_incomplets with (security_invoker = true) as
select p.isin, p.nom, p.type_produit, p.statut, p.derniere_vl, p.ticker_yahoo, p.ticker_eodhd,
       case
         when p.statut = 'introuvable' then 'Introuvable (ni Yahoo Finance ni EODHD)'
         when p.statut <> 'valide'     then 'À vérifier'
         when p.derniere_vl is null    then 'VL pas encore récupérées'
         else 'Historique trop court (moins de 6 mois) ou métriques pas encore calculées'
       end as raison
from produits p
where p.isin not in (select isin from produits_complets);

-- Les VL Yahoo déjà importées sont rechargées entièrement à la prochaine mise à jour,
-- cette fois sans les valeurs aberrantes (ex. VL multipliée par 100 un seul jour)
update produits set source_vl = null where source_vl = 'yahoo';
