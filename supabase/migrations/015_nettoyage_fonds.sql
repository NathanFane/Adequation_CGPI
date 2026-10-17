-- Nettoyage de l'univers (à exécuter une fois dans Supabase : SQL Editor > Run)
-- Supprime : les fonds incomplets (sauf 10 gardés en exemple), les fonds sans SRI,
-- les fonds à la volatilité aberrante (> 60 %). Leurs VL, métriques et rattachements partent avec eux.
-- Les ISIN supprimés sont notés dans fonds_exclus pour ne pas être réimportés depuis les listes des assureurs.

create table if not exists fonds_exclus (
  isin            char(12) primary key,
  raison          text not null,
  date_exclusion  date not null default current_date
);
alter table fonds_exclus enable row level security;
create policy "exclus lecture" on fonds_exclus for select to authenticated using (true);

-- 1. Fonds incomplets, sauf 10 exemples (pris dans chaque raison à tour de rôle)
insert into fonds_exclus (isin, raison)
select isin, 'Incomplet : ' || raison from produits_incomplets
where isin not in (
  select isin from (
    select isin, row_number() over (partition by raison order by isin) as rang
    from produits_incomplets
  ) t order by rang, isin limit 10
)
on conflict (isin) do nothing;

-- 2. Fonds complets sans SRI dans aucune liste d'assureur (adéquation DDA impossible)
insert into fonds_exclus (isin, raison)
select isin, 'Pas de SRI' from produits_complets where sri is null
on conflict (isin) do nothing;

-- 3. Fonds à la volatilité aberrante (> 60 % par an) : presque toujours une erreur de VL
insert into fonds_exclus (isin, raison)
select isin, 'Volatilité aberrante (' || round(volatilite * 100) || ' %)' from produits_complets where volatilite > 0.6
on conflict (isin) do nothing;

delete from produits where isin in (select isin from fonds_exclus);

-- Bilan
select raison, count(*) from fonds_exclus group by 1 order by 2 desc;
