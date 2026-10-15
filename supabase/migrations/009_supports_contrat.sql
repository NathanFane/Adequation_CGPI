-- Listes de supports publiées par les assureurs (à exécuter une fois dans Supabase : SQL Editor > Run)
-- Une ligne par contrat, support et date de liste : l'historique permet de repérer
-- les changements de SRI ou de frais d'une liste à l'autre.
create table supports_contrat (
  contrat            text     not null,   -- ex. generali_8301
  assureur           text     not null,
  isin               char(12) not null,
  date_liste         date     not null,   -- date de la liste (date d'import si absente du fichier)

  nom                text,
  code_support       text,                -- code interne de l'assureur
  forme_juridique    text,                -- FCP, SICAV, SCPI, Action…
  type_produit       text check (type_produit in ('fonds', 'etf', 'action', 'obligation', 'scpi', 'autre')),
  societe_gestion    text,
  classification     text,                -- classification propre à l'assureur

  -- Risque et durabilité
  sri                smallint check (sri between 1 and 7),
  sfdr               smallint check (sfdr in (6, 8, 9)),
  label_isr          boolean,
  label_greenfin     boolean,

  -- Frais et performances (décimal : 0,0193 = 1,93 %)
  frais_actif        numeric,             -- frais de gestion du fonds
  retrocessions      numeric,             -- part des frais du fonds reversée
  frais_contrat      numeric,             -- frais de gestion du contrat sur ce support
  frais_totaux       numeric,
  perf_brute_n1      numeric,
  perf_nette_n1      numeric,             -- après frais du fonds
  perf_finale_n1     numeric,             -- après frais du fonds et du contrat

  -- Conditions d'accès
  ouvert             boolean,
  avenant_requis     boolean,             -- souscription soumise à un avenant
  cotation_quotidienne boolean,
  eligible_pea       boolean,

  complements        jsonb,               -- colonnes propres à un seul assureur
  fichier_source     text,
  date_import        timestamptz not null default now(),
  primary key (contrat, isin, date_liste)
);
create index on supports_contrat (isin);

alter table supports_contrat enable row level security;
create policy "supports lecture" on supports_contrat for select to authenticated using (true);

-- Dernière liste connue de chaque contrat
create view supports_contrat_actuels as
select s.* from supports_contrat s
where s.date_liste = (select max(date_liste) from supports_contrat t where t.contrat = s.contrat);
