-- Récupération des VL via EODHD (à exécuter une fois dans Supabase : SQL Editor > Run)
alter table produits
  add column ticker_eodhd text,   -- identifiant EODHD (ex. FR0010135103.EUFUND ou CW8.PA)
  add column derniere_vl  date;   -- date de la dernière VL enregistrée

alter table historique
  add column vl_ajustee numeric(18,6);  -- VL corrigée des dividendes (pour les calculs de risque)
