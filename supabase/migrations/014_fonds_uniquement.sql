-- Le projet ne garde que les fonds : suppression des actions, ETF, SCPI et autres produits.
-- Leurs VL (historique), métriques et rattachements aux contrats sont supprimés avec eux
-- (clés étrangères « on delete cascade »).
delete from produits where type_produit is distinct from 'fonds';
