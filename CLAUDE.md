# CLAUDE.md – Contexte complet du projet « Adéquation CGPI »

Ce fichier est lu automatiquement par Claude Code à l'ouverture du dépôt. Il résume tout ce qui a été
décidé et construit. **À tenir à jour après chaque changement important.**
Dernière mise à jour : 19 octobre 2026.

---

## 1. Le projet

- **Auteur** : Nathan, étudiant en M2 Finance – Gestion privée (Mastère Gestion de patrimoine), ESG Rouen.
- **Mémoire** : devoir de conseil et outil d'adéquation pour cabinets de CGPI (conseillers en gestion de
  patrimoine indépendants). Le prototype web fait partie du mémoire.
- **Objectif de l'outil** : partir du profil d'un client pour proposer une **allocation objective** en
  assurance-vie, en respectant la **DDA** (directive sur la distribution d'assurances : adéquation du
  produit au profil, devoir de conseil).
- **Étapes déjà faites** : base de produits fiable et à jour (VL, métriques, données assureurs),
  univers d'investissement filtrable.
- **Étapes à venir** (voir §11) : méthodes d'allocation, questionnaire et profil client, contrôle
  d'adéquation, page de connexion.

---

## 2. Règles de travail avec Nathan (à respecter strictement)

- Répondre **en français**, **très brièvement** (il le rappelle souvent : « sois bref »). Pas de longs pavés.
- **Toujours expliquer les sigles** (ex. « SRI (indicateur synthétique de risque) »).
- **Être critique**, pas complaisant ; signaler les problèmes de méthode ou de données.
- **Ne coder que lorsqu'il le demande explicitement** (« va y », « oui », « je code ? » → « oui »).
  Sinon : expliquer, proposer, puis demander « Je code ? ».
- Avant de coder une demande ambiguë, **reformuler pour vérifier** qu'on a compris.
- Interface **simple et compréhensible par un CGPI non technicien** (il a refusé des libellés
  techniques comme « est l'un de (OU) » et la notion de « groupes de critères »).
- Il travaille depuis GitHub (interface web) et Supabase (SQL Editor) : donner des **liens directs**
  et des étapes courtes.
- **Sécurité** : ne jamais demander ni réafficher une clé secrète. La clé `service_role` de Supabase
  ne va que dans les secrets Streamlit et GitHub. Le site est public : ne pas diffuser le lien tant
  qu'il n'y a pas de page de connexion.

---

## 3. Architecture

| Élément | Rôle |
|---|---|
| **Streamlit Cloud** | Site web. URL : https://dequation-cgpi.streamlit.app (application `app.py`) |
| **Supabase** (PostgreSQL) | Base de données. RLS (sécurité par ligne) activée ; le code utilise la clé `service_role` qui la contourne |
| **GitHub** | Dépôt `NathanFane/Adequation_CGPI` (branche `main`). Le site se redéploie à chaque push |
| **GitHub Actions** | Tâches automatiques : mise à jour quotidienne, imports de fichiers |

**Secrets Streamlit** : `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `EODHD_API_KEY`, `DEV_USER_ID`,
`DEV_EMAIL`, `DEV_NOM`, `DEV_PRENOM`, (`OPENFIGI_KEY` facultatif).
**Secrets GitHub** : `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `EODHD_API_KEY`.

Pas encore de page de connexion : tout le site fonctionne avec un **utilisateur de test**
(`DEV_USER_ID`), créé automatiquement par `base.py`. La tâche quotidienne prend `DEV_USER_ID` s'il
existe, sinon le seul profil de la table `utilisateurs`.

### Procédure habituelle après un changement
1. Si une migration SQL est ajoutée : Nathan la lance **avant** tout dans Supabase → SQL Editor
   (sinon le site et la tâche quotidienne plantent).
2. Push sur `main` → Streamlit se redéploie.
3. **Piège connu** : Streamlit Cloud garde parfois en mémoire l'ancienne version d'un module importé
   (ex. `filtres.py`) → erreurs incohérentes. Solution : « Manage app » → ⋮ → **Reboot app**.

---

## 4. Fichiers du dépôt

### Pages Streamlit (navigation cachée, liens en pied de page)
| Fichier | Page |
|---|---|
| `app.py` | Routeur : `st.navigation([...], position="hidden")` ; page par défaut = `accueil.py`. Affiche le **pied de page avant le contenu** (contenu dans un `st.container()` réservé au-dessus) : liens visibles pendant le chargement et même si la page plante (erreur affichée par `st.exception`). Les pages n'appellent donc plus `pied_de_page` |
| `accueil.py` | **Mes produits**. Onglet 1 « Visualiser » (par défaut), onglet 2 « Importer » |
| `univers.py` | **Univers d'investissement** : tous les produits complets + section Filtres |
| `en_cours.py` | **Produits en cours de référencement** (produits incomplets avec la raison) |
| `page_indices.py` | **Indices de référence** : composition, indicateurs 5 ans, fonds rattachés, graphique base 100 |
| `methodologie.py` | **Méthodologie** : données, formules (LaTeX), calcul pas à pas sur un produit, limites |
| `navigation.py` | `retour_en_haut()` : lien « Retour à mes produits » en haut de chaque page (sauf Mes produits) ; `pied_de_page(page)` : liens vers les autres pages + « Retour à mes produits » en dernier |

**Mes produits – onglet Visualiser** (`accueil.py`) :
- bandeau « Annuler » du dernier enregistrement (toujours en haut de l'onglet) ;
- expander « Mes contrats » : frais (gestion UC, fonds euros, versements, arbitrages, en %) et colonne
  « Supprimer » (contrat + liste de ses produits ; case de confirmation ; annulable ; fonctionne aussi pour
  un contrat vide) ;
- bouton « Récupérer les données » (Yahoo puis EODHD, puis métriques) ;
- filtres simples : contrat, type, classe d'actifs, zone ;
- expander « Suppression en masse » : retirer d'un coup les lignes affichées (selon les filtres) ;
  case de confirmation obligatoire ; annulable ;
- tableau éditable (`st.data_editor`) : une ligne = un couple (produit, contrat). Colonnes : Retirer du
  contrat, ISIN, Nom, Type (modifiable), Classe d'actifs, Zone, Contrat, Statut, VL jusqu'au, Mis à jour
  le, Source des VL, Indice de référence (modifiable : Automatique ou l'un des 54), Indice retenu, Frais
  spécifiques (%) (modifiable), Frais totaux (frais du fonds + frais spécifiques, sinon frais UC du contrat),
  puis les métriques ;
- compteur « N ligne(s) = M produit(s) distinct(s) » (un fonds dans 3 contrats = 3 lignes) ;
- boutons « Enregistrer : résumé des changements » / « Annuler les modifications » ; clé d'éditeur
  versionnée `tableau_{version}`.

**Mes produits – onglet Importer** : copier-coller d'ISIN ou fichier Excel/CSV (modèle fourni, colonne
Contrat possible) ; noms et types via OpenFIGI.

**Univers d'investissement** (`univers.py` + `filtres.py`) :
- compteurs : produits complets, en cours de référencement, affichés ;
- **section Filtres** : une liste de critères ; chaque critère = indicateur + opérateur + valeur(s) ;
  entre deux critères, choix **ET / OU** ; **ET prioritaire** (« A ET B OU C » = « (A ET B) OU C »).
  Plusieurs valeurs dans un même critère = OU. Libellés : « égal à l'une des valeurs suivantes »,
  « différent des valeurs suivantes », « présent dans l'un / dans tous / absent des contrats suivants »,
  « supérieur à », « supérieur ou égal à », « inférieur à », « inférieur ou égal à », « compris entre »,
  « en dehors de ». Les pourcentages se saisissent en % (2 = 2 %). Une valeur manquante ne satisfait
  jamais un critère chiffré. La formule appliquée s'affiche en clair. (Les « groupes de critères »
  ont été supprimés à sa demande : trop compliqué.)

### Modules
| Fichier | Contenu |
|---|---|
| `base.py` | Client Supabase en cache (secrets Streamlit), `USER_ID`, création du profil de test |
| `calculs.py` | Métriques (voir §6) : `taux_sans_risque`, `detail`, `metriques`, `relatif` (R², bêta, alpha, TE, IR), `lire_historique`, `lire_indices`, `rendements_hebdo`, `rendements_references`, `correlations`, `calculer_et_enregistrer` |
| `collecte.py` | `executer` (requête avec reprise si connexion coupée), `_tout` (pagination 1000), EODHD (`mettre_a_jour`, quota), `actualiser` (Yahoo puis EODHD), `mettre_a_jour_indices` (yfinance) |
| `yahoo.py` | Source principale des VL : `chercher` (ticker par ISIN), `nettoyer` (VL aberrantes), `mettre_a_jour` |
| `indices.py` | 54 indices de référence (`REFERENCES`), `PAR_CODE`, `TICKERS`, `CLASSES`, `ZONES`, `SEUIL_ZONE = 0.7`, `classe_indice`, `zone_indice` |
| `listes_assureurs.py` | Lecteurs des listes de supports (Excel, CSV, PDF) : un par assureur ; `classe_assureur` |
| `remplissage.py` | Ajout automatique de fonds depuis les listes ; `classer` ; `rattacher` ; `NOMS_CONTRATS` |
| `filtres.py` | Moteur des filtres ET/OU (`appliquer`, `decrire`, `valeurs_possibles`) |
| `colonnes.py` | Colonnes de métriques communes à Mes produits et à l'Univers : `METRIQUES` (libellé → champ), `CONFIG` (format et bulle d'aide) |
| `emt.py`, `ept.py` | Lecture des fichiers FinDatEx EMT V4 et EPT V21 (colonnes repérées par leur code à 5 chiffres) |
| `openfigi.py` | Nom et type d'un ISIN via OpenFIGI (`TYPES = fonds, etf, action, obligation, scpi, autre`) |
| `isin.py` | `normaliser`, `est_valide` (clé de Luhn), `extraire` (découpe un copier-coller) |

### Scripts et workflows
| Workflow | Déclencheur | Script |
|---|---|---|
| `maj_quotidienne.yml` « Mise à jour quotidienne des VL » | tous les jours **6 h UTC (8 h Paris)** + manuel ; `concurrency` (jamais deux en même temps) ; timeout 120 min | `scripts/maj_quotidienne.py` |
| `import_contrats.yml` | push dans `donnees/contrats/**` + manuel | `scripts/import_contrats.py` |
| `import_reglementaire.yml` | push dans `donnees/emt/**` ou `donnees/ept/**` + manuel | `scripts/import_reglementaire.py` |
| `test_eodhd.yml`, `test_morningstar.yml` | anciens tests, inutiles | – |

Restes inutilisés : `index.html`, `questionnaire.yaml` (ancien formulaire), `.devcontainer/`.
Variable `SIMULATION=1` : les scripts d'import lisent les fichiers sans rien écrire en base (test à blanc).

---

## 5. Base de données (Supabase)

Schéma initial : `supabase/schema.sql`, puis migrations `002` à `018` (`018` à exécuter par Nathan, les autres le sont).

### Tables
| Table | Contenu |
|---|---|
| `utilisateurs` | Profils (id = auth.users) |
| `contrats` | Contrats d'un utilisateur : nom, assureur, `frais_gestion_uc`, `frais_gestion_euro`, `frais_versement`, `frais_arbitrage` (décimaux : 0,01 = 1 %) |
| `contrat_produits` | Lien contrat ↔ ISIN ; `frais_specifiques` (remplace les frais UC du contrat pour ce support) ; cascade à la suppression |
| `produits` | Un ISIN : nom, `type_produit`, `statut` (valide / a_verifier / invalide / introuvable), `ticker_yahoo`, `absent_yahoo`, `ticker_eodhd`, `source_vl` (yahoo/eodhd), `derniere_vl`, `derniere_maj`, `indice_reference`, `indice_manuel`, `classe_actifs`, `classe_source` (assureur/indice), `zone` |
| `historique` | VL quotidiennes (isin, date, vl, vl_ajustee) – cascade |
| `metriques` | Une ligne par produit et par jour de calcul (voir §6) – cascade |
| `indices_historique` | Cours des ETF de référence (ticker, date, valeur) |
| `supports_contrat` | Listes de supports des assureurs : une ligne par (contrat, ISIN, date_liste) ; SRI, SFDR, labels, frais du fonds, rétrocessions, frais du contrat, frais totaux, performances, ouvert, avenant_requis, `complements` (jsonb, colonnes propres à un assureur) |
| `fonds_exclus` | ISIN supprimés volontairement + raison ; jamais réimportés |
| `donnees_emt`, `donnees_ept` | Données réglementaires FinDatEx (BlackRock uniquement pour l'instant) |

### Vues (se mettent à jour d'elles-mêmes, `security_invoker = true`)
| Vue | Contenu |
|---|---|
| `supports_contrat_actuels` | Dernière liste connue de chaque contrat |
| `metriques_actuelles` | Dernier calcul de métriques de chaque produit |
| `produits_complets` | Produits valides avec VL **et** métriques ; + contrats, assureurs, SRI (max si listes différentes), SFDR, frais du fonds (min), frais totaux (min des contrats de `coalesce(frais_totaux, frais_actif + frais_contrat)`), label ISR, `derniere_maj` |
| `produits_incomplets` | Les autres, avec `raison` : introuvable / VL pas encore récupérées / historique < 6 mois ou métriques pas calculées |

### Migrations (ordre et but)
002 type de produit · 003 historique EODHD · 004 indices et métriques · 005-006 EMT · 007 frais des
contrats · 008 EPT · 009 `supports_contrat` · 010 colonnes Yahoo · 011 classe d'actifs, zone,
`metriques_actuelles` · 012 vues complets/incomplets + rechargement Yahoo · 013 nouvelle recherche des
tickers Yahoo · 014 **fonds uniquement** (suppression actions, ETF, SCPI…) · 015 nettoyage (incomplets
sauf 10 exemples, sans SRI, volatilité > 60 %) + `fonds_exclus` · 016 `derniere_maj` · 017 nouvelles métriques
(colonnes de `metriques`, vues `metriques_actuelles` et `produits_complets` + `frais_totaux`) · 018 perf 3 mois /
6 mois / 1 an et `historique_annees`.

### État des données (17/10/2026)
- **1 808 fonds complets** : 1 659 via Yahoo, 148 via EODHD, 1 en attente.
- 10 fonds incomplets gardés volontairement comme exemples (pour que la vue ne soit pas vide).
- Exclus (`fonds_exclus`) : 371 sans VL, 167 historique trop court ou métriques non calculées,
  18 introuvables, 332 sans SRI, 2 volatilité aberrante (89 % et 411 %).
  - Point ouvert : certains des 167 avaient peut-être leurs VL (métriques perdues lors de 2 passages
    plantés). Pour les réimporter : `delete from fonds_exclus where raison like 'Incomplet : Historique%';`
    (proposé à Nathan, pas encore confirmé).
- Espace Supabase : surveiller (offre gratuite 500 Mo ; ~2 700 fonds × 5 ans ≈ 350 Mo).

---

## 6. Métriques (calculs.py) – validées

Sur les VL **ajustées** (dividendes réinvestis), 5 dernières années, 252 jours de bourse/an,
minimum **120 VL** (~6 mois) sinon pas de métrique.

| Métrique | Définition |
|---|---|
| Rendement annuel | Annualisé (géométrique) |
| Volatilité | Écart-type des rendements quotidiens × √252 |
| **VaR Cornish-Fisher 97,5 % à 1 an** | Formule **PRIIPs** (N = 252), stockée en perte positive. Validée contre la VEV officielle BlackRock (écart < 0,1 pt) |
| CVaR | Historique, quotidienne (moyenne des 2,5 % pires jours) |
| Max Drawdown | Pire baisse depuis un plus haut (positif) |
| Recouvrement (jours) | Du point bas au retour au plus haut précédent ; vide si pas encore revenu (normal) |
| Sharpe, Sortino | Avec le taux sans risque = moyenne de l'**€STR** (BCE) sur la période |
| Corrélation à l'indice | Rendements **hebdomadaires** (vendredi), ≥ 26 semaines communes ; indice retenu = le plus corrélé des 54, sauf choix manuel du CGPI |
| R², bêta, alpha de Jensen, tracking error, ratio d'information | Contre l'indice retenu, mêmes rendements hebdomadaires communs ; rendements annualisés sur ces semaines (52/an) ; alpha = R_p − [r_f + β(R_i − r_f)] ; TE = σ(r_p − r_i)·√52 ; IR = (R_p − R_i)/TE. Réserve : indice choisi a posteriori |
| Calmar | Rendement annuel ÷ max drawdown (même période, 5 ans au plus) |
| Mois positifs, pire mois | Rendements mensuels de fin de mois (premier mois incomplet écarté) |
| Pire année | Pire performance sur **12 mois glissants** (fins de mois) ; pas les années civiles (1re et dernière incomplètes) |
| Skewness, kurtosis | Ceux de la VaR Cornish-Fisher (rendements log quotidiens ; kurtosis = excès) |
| Perf 3 mois, 6 mois, 1 an | VL finale ÷ VL à la même date n mois plus tôt (ou dernière VL avant) − 1 ; vide si historique trop court. Servent à la stratégie momentum |
| Historique (ans) | Durée couverte par les VL utilisées, **plafonnée à 5** (période de calcul ; 1 an pour EODHD) ; arrondie à 0,1. Filtre « Historique (ans) ≥ 3 / ≥ 5 » dans l'Univers. La date de création réelle du fonds n'est pas connue |
| Frais totaux | Pas dans `metriques` : Univers = vue `produits_complets` ; Mes produits = frais du fonds + frais du contrat de l'utilisateur. Hors frais de versement/arbitrage |

**Classe d'actifs** : d'abord la classification de l'assureur (mots-clés, `classe_assureur`), sinon la
catégorie de l'indice le plus corrélé si corrélation ≥ 0,7. Valeurs : monetaire, obligations, actions,
mixte, immobilier, matieres_premieres, alternatif, structure.
**Zone** : celle de l'indice le plus corrélé si corrélation ≥ 0,7, sinon « Indéterminée ». C'est une zone
dominante, pas une répartition en %. Aucune source gratuite ne donne la vraie répartition géographique.

**Limites connues** (à mettre dans le mémoire) : historique court pour certains fonds ; VL Yahoo
parfois manquantes certains jours ; monétaire / obligations très courtes → corrélation proche de 0 et
Sharpe/Sortino artificiellement élevés (volatilité quasi nulle) ; fonds alternatifs volontairement
décorrélés (une corrélation faible n'est **pas** une raison d'exclure, Nathan l'a confirmé) ; indices =
approximations par ETF ; listes assureurs datées.

---

## 7. Sources de données

| Source | Usage | Limites |
|---|---|---|
| **Yahoo Finance** (yfinance) | **Source principale des VL des fonds** (5 ans) et des cours des 54 indices | API non officielle ; usage personnel/académique uniquement (pas pour un outil commercial) ; jours manquants ; erreurs ponctuelles |
| **EODHD** | Secours pour les fonds absents de Yahoo (`ISIN.EUFUND` ou recherche) | Offre gratuite : **~20 appels/jour**, 1 an d'historique |
| **OpenFIGI** | Nom et type d'un ISIN à l'import | – |
| **BCE** | €STR (taux sans risque) | – |
| **Listes de supports des assureurs** | SRI, SFDR, labels, frais, rétrocessions, performances, classification | Datées ; formats différents par assureur |
| **FinDatEx EMT / EPT** | Marché cible, frais / données PRIIPs | Seulement BlackRock ; les sociétés de gestion françaises ne les publient pas librement |

Abandonné : Morningstar via `mstarpy` (exige Chrome, VL refusées 401/403).

### Choix du ticker Yahoo (`yahoo.chercher`)
Recherche par ISIN ; classement : fonds → ticker **« 0P… »** (VL officielle Morningstar) d'abord ;
ETF/actions → **« .PA »** (Paris) d'abord ; petites bourses allemandes (.MU, .HM, .DU, .BE, .SG, .HA, .F)
en dernier. On prend le premier ticker ayant **≥ 120 VL sur 1 an** ; sinon aucun (→ EODHD).
Raison : des cotations secondaires peu échangées (prix figés) donnaient des corrélations absurdes.

### Nettoyage des VL (`yahoo.nettoyer`)
Suppression des points isolés à plus de **30 %** de la médiane des 5 jours voisins (ex. une VL ×100 un
seul jour : fonds OFI à 7 574 € au lieu de ~76 €). Une vraie chute de plusieurs jours est conservée.
Mise à jour incrémentale avec chevauchement de 10 jours : si les VL ajustées déjà en base diffèrent de
plus de 0,5 % (dividende détaché), l'historique est **entièrement rechargé**.

---

## 8. Listes de supports des assureurs (`donnees/contrats/<dossier>/`)

Le **nom du dossier** choisit le lecteur. Dépôt d'un fichier → import automatique (workflow
`import_contrats.yml`) dans `supports_contrat`.

| Dossier | Contrat (code / nom affiché) | Format | Particularités |
|---|---|---|---|
| `generali` | `generali_8301` / Generali 8301 | CSV `;` Latin-1 | **Pas de SRI** ; frais déjà en colonnes ; 41 ISIN en double ; colonne avenant ; frais contrat 1 % (1,5 % ETF/actions) |
| `vieplus` | `vieplus_patrimoine_vie_plus_multiprojet` / Patrimoine Vie Plus Multiprojet | .xls (titre ligne 1, en-têtes ligne 2) | Vie Plus (assureur Suravenir). SRI, SFDR, labels, catégorie Morningstar, volatilités, Sharpe, dates de fermeture ; **pas de frais du contrat** |
| `cardif` | `cardif_elite` / Cardif Elite | .xlsx (en-tête à 2 lignes repérée par « Code ISIN » ; 2 tableaux : fonds puis titres vifs) | Liste du 01/07/2025 ; frais en texte « 0,46% (dont 0,14%) » ; « NC »/« NA » |
| `generali_lux` | `generali_espace_lux` / Generali Espace Lux | **PDF** (univers Global, 01/06/2026) | Colonnes repérées par les traits verticaux ; noms sur 2 lignes recollés par proximité |
| `cardif_panthea` | `cardif_panthea_vie_2` / Cardif Panthéa Vie 2 | **PDF** (généré depuis Excel, 01/10/2025) | Colonnes = fins rectangles ; pas de SFDR fonds par fonds ; 26 SRI « NC » |

Nathan n'a réellement que 3 contrats (Cardif Elite, Generali 8301, Vie Plus) ; les 2 PDF ont été ajoutés
pour enrichir l'univers. Les SCPI ont souvent un code interne au lieu d'un ISIN → écartées.

---

## 9. Automatismes

### Mise à jour quotidienne (`scripts/maj_quotidienne.py`, 8 h Paris)
1. `collecte.actualiser` :
   - recherche du ticker Yahoo pour les produits jamais cherchés ;
   - **Yahoo : tous les fonds ayant un ticker, chaque jour** (lots de 100, incrémental) ;
   - **EODHD : fonds sans ticker Yahoo, tous les 7 jours**, plus anciens d'abord, budget 20 appels/jour ;
   - produits jamais trouvés → `statut = introuvable`.
2. `remplissage.ajouter_nouveaux` : ajoute jusqu'à 500 fonds/jour depuis les listes (plafond 2 800),
   **fonds uniquement**, ouverts, sans avenant, hors `fonds_exclus` ; ordre équilibré par
   (contrat, classe d'actifs) puis complétude des données. Les listes sont **épuisées** aujourd'hui.
   Ne rattache aux contrats de l'utilisateur **que les fonds ajoutés le jour même** (pour ne jamais
   recréer ce que l'utilisateur a supprimé). Met aussi à jour la classe d'actifs (`classer`).
3. Indices de référence (yfinance, rechargement complet 5 ans).
4. `calculer_et_enregistrer` : métriques de tous les produits valides, enregistrées par lots de 200 ;
   reprise automatique si Supabase coupe la connexion (il la ferme après ~20 000 requêtes).

---

## 10. Historique des décisions importantes

- Questionnaire YAML abandonné au profit d'une base produits fiable orientée CGPI.
- Morningstar/mstarpy abandonné → OpenFIGI (noms) + EODHD (VL) → puis **Yahoo en source principale**
  (gratuit, 5 ans, ~85 % de couverture des fonds) avec EODHD en secours.
- Une seule table `supports_contrat` pour tous les assureurs (pas une table par contrat).
- Remplissage d'abord limité (1 000), puis **fonds uniquement** et import de tous les fonds des listes,
  puis suppression des incomplets (sauf 10), des fonds sans SRI (adéquation DDA impossible) et des
  volatilités aberrantes. Un historique < 3 ans n'est **pas** un motif d'exclusion (choix de Nathan).
- `produits_complets` / `produits_incomplets` en **vues** plutôt qu'en tables copiées (toujours à jour).
- Filtres : groupes supprimés, ET/OU entre chaque critère, ET prioritaire.
- Ordre des onglets : Visualiser d'abord.
- Suppression en masse avec confirmation et annulation.
- Suppression des contrats déplacée dans l'expander « Mes contrats » (avant : dans « Suppression en masse »,
  invisible quand aucun produit n'était affiché).

---

## 11. Prochaines étapes / points ouverts

1. **Nouvelles métriques** : codées le 18/10 (voir §6), migration `017` exécutée. Écartés car redondants :
   Treynor, Omega, Sterling, Martin, Ulcer. Les métriques de portefeuille (matrice de corrélation,
   contribution au risque, VaR du portefeuille) seront calculées à l'étape d'allocation.
2. **Stratégies d'allocation** (en cours de discussion, 19/10). Principe retenu : **la stratégie choisit les
   fonds, le profil fixe la répartition entre classes d'actifs** ; les fonds sont comparés **au sein de chaque
   classe d'actifs** (sinon les ratios favorisent monétaire et obligations). 7 stratégies validées par Nathan,
   indépendantes du profil de risque :
   1. Core-satellite (cœur : frais bas, R² élevé, faible tracking error ; satellites : alpha et IR élevés) ;
   2. Low cost (frais totaux les plus bas) ;
   3. Qualité / régularité (Sharpe, Sortino, Calmar, % de mois positifs) ;
   4. Convictions (alpha, ratio d'information) ;
   5. Momentum (perf 6 mois / 1 an) ;
   6. Diversification maximale (faibles corrélations entre fonds, zones et classes variées) ;
   7. ISR / durable (SFDR 8 ou 9, label ISR).
   Impossibles faute de composition des fonds : value / croissance, petites capitalisations, secteurs.
   Réserve : 1 et 4 reposent sur un indice choisi a posteriori. Reste à définir : pondération des fonds
   (1/N, inverse volatilité, parité de risque, HRP), nombre de fonds, plafonds par fonds. Le Max Sharpe
   (Markowitz) est déconseillé (instable, concentré).
3. Questionnaire client, tables `clients` / `profils`, contrôle d'adéquation (marché cible EMT, SRI).
4. Page de connexion (Supabase Auth) ; ensuite seulement partager le lien du site.
5. Afficher les données EMT/EPT dans le tableau ; importer l'EET (SFDR) si un fichier est obtenu.
6. Éventuellement : contrôle qualité en comparant la performance N-1 calculée à celle des listes
   assureurs (proposé, Nathan l'a trouvé trop complexe pour l'instant).
7. Réimport éventuel des 167 fonds « historique trop court » (voir §5).
8. Mettre à jour les listes des assureurs quand de nouvelles versions sont disponibles (déposer le
   fichier dans le bon dossier ; la date de liste permet de suivre les changements de SRI).
