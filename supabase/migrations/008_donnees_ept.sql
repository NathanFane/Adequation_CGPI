-- Données PRIIPs issues des fichiers EPT (à exécuter une fois dans Supabase : SQL Editor > Run)
create table donnees_ept (
  isin                    char(12) primary key,
  nom                     text,
  devise                  text,
  societe_gestion         text,
  date_dic                date,       -- 00070 : date de publication du DIC
  version_ept             text,
  categorie_priips        smallint,   -- 00080 : méthode de calcul du risque (1 à 4)

  -- Risque
  sri                     smallint check (sri between 1 and 7),
  mrm                     smallint,   -- classe de risque de marché
  crm                     smallint,   -- classe de risque de crédit
  vev                     numeric,    -- volatilité équivalente à la VaR
  duree_detention_ans     numeric,
  risque_liquidite        text,       -- 01140
  garantie_capital        boolean,
  alerte_comprehension    boolean,    -- produit complexe

  -- Paramètres PRIIPs officiels (rendements quotidiens sur 5 ans)
  priips_nb_rendements    integer,
  priips_moyenne          numeric,
  priips_sigma            numeric,
  priips_skewness         numeric,
  priips_kurtosis         numeric,    -- excès de kurtosis
  volatilite_stress       numeric,

  -- Scénarios de performance (rendement en décimal)
  scenario_tension_1an          numeric,
  scenario_tension_rhp          numeric,
  scenario_defavorable_1an      numeric,
  scenario_defavorable_rhp      numeric,
  scenario_intermediaire_1an    numeric,
  scenario_intermediaire_rhp    numeric,
  scenario_favorable_1an        numeric,
  scenario_favorable_rhp        numeric,

  -- Coûts du DIC (décimal)
  frais_entree            numeric,
  frais_sortie_rhp        numeric,
  frais_gestion_courants  numeric,    -- frais de gestion et autres frais administratifs
  frais_transaction       numeric,

  fichier_source          text,
  date_import             timestamptz not null default now()
);
alter table donnees_ept enable row level security;
create policy "ept lecture" on donnees_ept for select to authenticated using (true);
