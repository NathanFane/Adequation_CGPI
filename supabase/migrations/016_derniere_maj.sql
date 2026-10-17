-- Date de la dernière mise à jour des VL de chaque produit (à exécuter une fois dans Supabase)
alter table produits add column if not exists derniere_maj timestamptz;
update produits set derniere_maj = derniere_vl::timestamptz where derniere_maj is null and derniere_vl is not null;

-- Les vues reprennent la nouvelle colonne (ajoutée en fin de liste)
create or replace view produits_complets with (security_invoker = true) as
select p.isin, p.nom, p.type_produit, p.classe_actifs, p.zone, p.indice_reference,
       p.derniere_vl, p.source_vl,
       s.contrats, s.assureurs, s.sri, s.sfdr, s.frais_actif, s.label_isr,
       m.date_calcul, m.rendement_annuel, m.volatilite, m.var_cf, m.cvar, m.max_drawdown,
       m.recouvrement_jours, m.sharpe, m.sortino, m.correlation_indice,
       p.derniere_maj
from produits p
join metriques_actuelles m on m.isin = p.isin
left join (
  select isin,
         array_agg(distinct contrat order by contrat) as contrats,
         string_agg(distinct assureur, ', ')          as assureurs,
         max(sri)         as sri,
         max(sfdr)        as sfdr,
         min(frais_actif) as frais_actif,
         bool_or(label_isr) as label_isr
  from supports_contrat_actuels group by isin
) s on s.isin = p.isin
where p.statut = 'valide' and p.derniere_vl is not null;
