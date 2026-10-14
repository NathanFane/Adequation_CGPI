-- Schéma de la base – Adéquation CGPI
-- À exécuter dans Supabase : SQL Editor > New query > coller > Run

-- 1. Profils utilisateurs (e-mail et mot de passe gérés par Supabase Auth)
create table utilisateurs (
  id      uuid primary key references auth.users(id) on delete cascade,
  nom     text not null,
  prenom  text not null,
  email   text not null unique
);

-- 2. Contrats propres à chaque CGPI
create table contrats (
  id        bigint generated always as identity primary key,
  user_id   uuid not null references utilisateurs(id) on delete cascade,
  nom       text not null,
  assureur  text
);

-- 3. Produits communs à tous les utilisateurs
create table produits (
  isin        char(12) primary key check (isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'),
  nom         text,
  statut      text not null default 'a_verifier'
              check (statut in ('a_verifier', 'valide', 'invalide', 'introuvable')),
  date_ajout  timestamptz not null default now()
);

-- 4. Liaison contrats <-> produits
create table contrat_produits (
  contrat_id  bigint   not null references contrats(id) on delete cascade,
  isin        char(12) not null references produits(isin) on delete cascade,
  primary key (contrat_id, isin)
);

-- 5. Historique des valeurs liquidatives
create table historique (
  isin  char(12) not null references produits(isin) on delete cascade,
  date  date     not null,
  vl    numeric(18,6) not null,
  primary key (isin, date)
);

-- 6. Métriques calculées ou importées
create table metriques (
  isin           char(12) not null references produits(isin) on delete cascade,
  date_calcul    date     not null,
  var_cf         numeric,               -- VaR Cornish-Fisher
  volatilite     numeric,
  sharpe         numeric,
  sortino        numeric,
  sri            smallint check (sri between 1 and 7),
  sfdr           smallint check (sfdr in (6, 8, 9)),
  frais_courants numeric,
  primary key (isin, date_calcul)
);

create index on contrats (user_id);
create index on contrat_produits (isin);

-- Sécurité : chaque CGPI ne voit que ses données
alter table utilisateurs     enable row level security;
alter table contrats         enable row level security;
alter table contrat_produits enable row level security;
alter table produits         enable row level security;
alter table historique       enable row level security;
alter table metriques        enable row level security;

create policy "profil personnel" on utilisateurs
  for all using (id = auth.uid()) with check (id = auth.uid());

create policy "contrats personnels" on contrats
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "liaisons personnelles" on contrat_produits
  for all using (exists (select 1 from contrats c where c.id = contrat_id and c.user_id = auth.uid()))
  with check (exists (select 1 from contrats c where c.id = contrat_id and c.user_id = auth.uid()));

-- Produits : lecture et ajout par tout utilisateur connecté
create policy "produits lecture" on produits for select to authenticated using (true);
create policy "produits ajout"   on produits for insert to authenticated with check (true);

-- Historique et métriques : lecture seule côté site
-- (écriture par la tâche quotidienne avec la clé service_role, qui contourne ces règles)
create policy "historique lecture" on historique for select to authenticated using (true);
create policy "metriques lecture"  on metriques  for select to authenticated using (true);
