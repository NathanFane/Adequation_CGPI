-- Données réglementaires issues des fichiers EMT (à exécuter une fois dans Supabase : SQL Editor > Run)
create table donnees_emt (
  isin                   char(12) primary key,
  nom                    text,
  devise                 text,
  societe_gestion        text,
  date_reference         date,          -- 00050 : date des données
  version_emt            text,          -- 00001

  -- Marché cible (condensé à partir des colonnes Y/N de l'EMT)
  connaissance_min       text check (connaissance_min in ('debutant', 'informe', 'avance')),
  perte_acceptable_min   text check (perte_acceptable_min in ('aucune', 'limitee', 'capital', 'au_dela')),
  perte_limitee_niveau   numeric,       -- 03030 : niveau de perte si « perte limitée »
  sri                    smallint check (sri between 1 and 7),
  duree_detention_ans    numeric,       -- 05080
  objectif_preservation  text,          -- Y / N / NEUTRAL
  objectif_croissance    text,
  objectif_revenus       text,
  durabilite             text,          -- 05105

  -- Frais (en décimal : 0,0147 = 1,47 %)
  frais_entree_max       numeric,
  frais_sortie_max       numeric,
  frais_courants         numeric,
  frais_gestion          numeric,
  frais_transaction      numeric,
  commission_performance boolean,
  distribution           boolean,       -- true : distribue ses revenus ; false : capitalise
  levier                 boolean,

  fichier_source         text,
  date_import            timestamptz not null default now()
);
alter table donnees_emt enable row level security;
create policy "emt lecture" on donnees_emt for select to authenticated using (true);
