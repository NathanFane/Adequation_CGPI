-- VL via Yahoo Finance (source principale), EODHD en secours (à exécuter une fois dans Supabase)
alter table produits
  add column ticker_yahoo  text,                            -- ex. 0P0000I43E.F, CW8.PA
  add column absent_yahoo  boolean not null default false,  -- recherché sur Yahoo sans résultat
  add column source_vl     text check (source_vl in ('yahoo', 'eodhd'));

update produits set source_vl = 'eodhd' where derniere_vl is not null;
