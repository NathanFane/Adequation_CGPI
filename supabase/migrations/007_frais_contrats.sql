-- Frais des contrats d'assurance-vie (en décimal : 0,0085 = 0,85 %)
alter table contrats
  add column frais_gestion_uc   numeric,
  add column frais_gestion_euro numeric,
  add column frais_versement    numeric,
  add column frais_arbitrage    numeric;

-- Exception : frais de gestion propres à un support dans un contrat (remplace frais_gestion_uc)
alter table contrat_produits add column frais_specifiques numeric;
