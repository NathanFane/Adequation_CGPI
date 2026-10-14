-- Ajout du type de produit (à exécuter une fois dans Supabase : SQL Editor > Run)
alter table produits
  add column type_produit text
  check (type_produit in ('fonds', 'etf', 'action', 'obligation', 'scpi', 'autre'));

-- Les CGPI peuvent corriger le type d'un produit
create policy "produits modification" on produits for update to authenticated using (true) with check (true);
