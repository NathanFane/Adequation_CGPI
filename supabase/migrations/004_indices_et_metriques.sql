-- Indices de référence et nouvelles métriques (à exécuter une fois dans Supabase : SQL Editor > Run)

-- Cours des ETF servant d'indices de référence
create table indices_historique (
  ticker  text not null,
  date    date not null,
  valeur  numeric(18,6) not null,
  primary key (ticker, date)
);
alter table indices_historique enable row level security;
create policy "indices lecture" on indices_historique for select to authenticated using (true);

-- Indice de référence de chaque produit (choisi automatiquement, ou par le CGPI)
alter table produits
  add column indice_reference text,
  add column indice_manuel    boolean not null default false;

-- Nouvelles métriques
alter table metriques
  add column rendement_annuel   numeric,
  add column cvar               numeric,   -- perte moyenne des 2,5 % pires jours
  add column max_drawdown       numeric,   -- pire baisse depuis un plus haut
  add column recouvrement_jours integer,   -- jours pour revenir au plus haut (vide si pas encore revenu)
  add column correlation_indice numeric,
  add column indice_reference   text;
