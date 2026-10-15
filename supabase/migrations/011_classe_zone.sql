-- Classe d'actifs et zone géographique des produits (à exécuter une fois dans Supabase)
alter table produits
  add column classe_actifs text check (classe_actifs in ('monetaire', 'obligations', 'actions', 'mixte',
                                       'immobilier', 'matieres_premieres', 'alternatif', 'structure')),
  add column classe_source text check (classe_source in ('assureur', 'indice')),
  add column zone          text;   -- déduite de l'indice le plus corrélé (« Indéterminée » si corrélation < 0,7)

-- Dernières métriques de chaque produit (évite de relire tout l'historique des calculs)
create view metriques_actuelles as
select distinct on (isin) * from metriques order by isin, date_calcul desc;
