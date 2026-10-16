-- Nouvelle recherche du ticker Yahoo pour les produits suivis via une cotation secondaire
-- (ni VL Morningstar « 0P… », ni Paris) : à la prochaine mise à jour, le meilleur ticker est
-- recherché puis l'historique complet est rechargé.
update produits
set ticker_yahoo = null, source_vl = null
where ticker_yahoo is not null
  and ticker_yahoo not like '0P%'
  and ticker_yahoo not like '%.PA';
