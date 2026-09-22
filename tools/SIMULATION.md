# Première simulation de l'économie Root

Exécution depuis la racine, sans démarrer le bot ni accéder à MySQL :

```powershell
.\.venv\Scripts\python.exe tools/simulate_balance.py --days 30 --runs 20 --seed 42
```

Seule la bibliothèque standard Python est nécessaire. Le script importe `MathConfig`
pour les statistiques matérielles, le minage, la saturation, les arrondis, la
conversion et les multiplicateurs d'événements. Les prix suivent la formule de
`game/db/players.py`, vérifiée par un test de parité dans l'environnement du projet.
Le fichier `data/math.json` et les données des joueurs ne sont pas modifiés.

## Hypothèses de cette expérience

- Création à l'instant zéro, dotation configurée, premier
  achat immédiat. La dotation suit `initial_grant_usd` (2 000 USD depuis la
  version 1.1.0). Réputation fixe, zéro par défaut.
- Occasionnel : 2 visites par jour, à 9 h et 21 h ; 1 victoire/jour en espérance.
- Régulier : 6 visites par jour, à 9, 12, 15, 18, 21 et 23 h ; 4 victoires/jour.
- Très actif : une visite toutes les 15 minutes entre 9 h et 23 h incluses
  (57 visites/jour) ; 10 victoires/jour.
- Les heures sont des positions dans une journée simulée de 24 h, sans changement
  d'heure. À chaque visite : claim, conversion de tout le RTM récupéré, événements,
  puis décision d'achat. Le minage continue hors ligne jusqu'à saturation.
- Les victoires suivent une loi de Poisson, réparties sur les visites. Les sept
  types de mini-jeux sont équiprobables ; leurs récompenses de base sont tirées
  uniformément en centimes dans leurs bornes configurées. Cela modélise un revenu
  de participation, **pas** le calendrier réel des défis ni les autres joueurs.
- Les mêmes tirages de victoires/récompenses sont utilisés pour comparer les deux
  stratégies d'un profil. Les profils sont des expériences indépendantes.
- `pare_feu_prioritaire` : acheter 1 mineur du meilleur tier disponible, puis
  économiser pour le prochain pare-feu.
- `minage_prioritaire` : acheter 10 mineurs du meilleur tier disponible, puis
  économiser pour le prochain pare-feu. Les achats peuvent être progressifs.
- `reinvestissement_t1` : réinvestir continuellement en T1, sans pare-feu.
- Quatre variantes arrêtent les achats à J5 ou J8 pour épargner le cash,
  à partir des stratégies T1 et minage prioritaire.
- Pendant un chantier, les fonds sont conservés. Livraison à l'échéance exacte,
  achat de nouveaux mineurs à la prochaine visite. Améliorations séquentielles.
- Au pare-feu maximal, chaque visite réinvestit tout le budget disponible en
  mineurs du meilleur tier. Les anciens mineurs restent présents.
- Pas de PvP, défense achetée, compile, scan, échanges ou réputation gagnée.
  Les résultats sont donc un scénario économique sans pertes par attaque.

Ces stratégies sont simples et reproductibles, sans prétention d'optimalité.
Les hypothèses d'activité ne viennent pas de statistiques réelles de joueurs.

## Exports

Dans `simulation_results/baseline/` par défaut :

- `summary.csv` : médianes et P10/P90 empiriques des revenus et de la saturation ;
  taux d'accès aux paliers et médiane du délai **parmi ceux qui les atteignent**.
- `runs.csv` : une ligne par profil, stratégie et graine ; revenus cumulés,
  trésorerie, matériel final, pertes de production et dates des paliers.
  `cash_100k_day` mesure le premier solde d'au moins 100 000 USD, observé après
  les revenus et **avant** les achats ; `peak_cash_usd` garde le maximum observé.
  `income_100k_day` suit séparément les revenus cumulés (dotation exclue).
- `daily.csv` : état quotidien pour la première graine de chaque scénario.
- `actions.csv` : achats et chantiers pour cette même première graine.
- `metadata.json` : paramètres de l'expérience, copie des règles et empreinte.

Les dollars sont la monnaie du jeu. Le revenu cumulé n'est pas le solde final :
les achats le réduisent. Le matériel n'est pas ajouté au solde comme s'il était
revendable. Un palier non atteint reste vide, jamais remplacé par zéro.
Les quantiles empiriques ne sont pas des intervalles de confiance.

Un dépassement de la précision `Decimal` du moteur interrompt le parcours :
`completed=False`, date d'arrêt et dernier état valide dans `runs.csv`. Ce parcours
n'est pas présenté comme un résultat à 30 jours. Les statistiques de revenus
dans `summary.csv` portent seulement sur les parcours terminés (`completed_pct`) ;
si aucun n'aboutit, elles restent vides. Les dates de paliers déjà observées avant
l'arrêt sont conservées. La simulation ne reproduit pas les limites des colonnes
SQL, qui peuvent être atteintes encore plus tôt.

Le minage non récupéré à la fin reste dans le tampon. La perte par saturation
compare la production théorique à celle que la RAM accepte. L'écart dû aux
arrondis du jeu est mesuré séparément (`rounding_rtm`). Les instantanés quotidiens
ne matérialisent pas le minage et n'introduisent donc pas d'arrondis supplémentaires.

## Autres expériences

```powershell
# Isoler le minage sans revenu d'événements
.\.venv\Scripts\python.exe tools/simulate_balance.py --event-scale 0 --runs 1 --output simulation_results/mining_only

# Plus de tirages, sur 90 jours, avec 20 points de réputation fixes
.\.venv\Scripts\python.exe tools/simulate_balance.py --days 90 --runs 100 --reputation 20 --output simulation_results/90_days

# Tester une copie modifiée des règles sans toucher à celles du jeu
.\.venv\Scripts\python.exe tools/simulate_balance.py --config data/math_candidate.json --output simulation_results/candidate

# Vérifications du simulateur
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_balance_simulation.py -v
```

Les exports d'un même répertoire sont remplacés à chaque exécution : utiliser
des répertoires distincts pour conserver les expériences à comparer.

## Calibration du seuil de 100 000 USD

La cadence de claim est une contrainte de gameplay : les versions actuelles du
calibrateur conservent **8 / 12 / 35 / 50 / 75 minutes** de stockage sans bonus.
Une variation de hashrate recalcule la RAM pour préserver cette cadence.
Les anciens exports qui accordaient des heures de RAM sont des archives rejetées.

`tools/calibrate_balance.py` reconstruit les variantes depuis l'instantané initial
conservé dans `simulation_results/baseline/metadata.json`. Les formules de
`MathConfig` sont utilisées avec un instantané de règles figé en mémoire pour
éviter de relire le fichier à chaque calcul et garantir la reproductibilité.

```powershell
# Tester les règles actuellement appliquées avec 30 stratégies et 50 graines
.\.venv\Scripts\python.exe tools/calibrate_balance.py --config data/math.json --days 15 --runs 50 --reputation 100 --stress-wins 600 --stress-only --sweep-saving --output simulation_results/recheck

# Comparer sur 90 jours, sans bonus de réputation
.\.venv\Scripts\python.exe tools/calibrate_balance.py --price-based --days 90 --runs 5 --output simulation_results/recheck_90days
```

`--apply` écrit également le candidat dans `data/math.json`. Sans ce drapeau,
seuls les fichiers de résultats sont écrits. `--sweep-saving` teste l'arrêt des
achats à chacun des jours J1 à J9 pour trois politiques d'investissement.
Le profil extrême effectue un claim toutes les 8 minutes, 24 h/24. Ses victoires
restent une hypothèse de stress, pas un calendrier réalisable garanti.

Le critère concerne le **cash disponible**, pas les revenus cumulés, le matériel
ou l'inflation des prix entre joueurs. Un test réussi n'est pas un verrou d'âge :
les transferts, le matériel préexistant, les dons et les réputations hors scénario
peuvent contourner ce rythme. La croissance à long terme reste possible puisque
le nombre de mineurs n'est pas plafonné.

## Vote et parrainage : simulation de bonus RAM

Les règles proposées sont mémorisées sous `ram_rewards` dans `data/math.json`,
avec des champs `_comment` pour conserver un JSON valide. Ces paramètres
n'activent aucun bonus dans le bot : la réception des votes et le suivi des
parrainages restent à implémenter.

- Vote : +20 % pendant 6 heures ; renouvellement sans empiler plusieurs votes.
- Premier pare-feu niveau 1 du filleul : +10 % au parrain et +10 % à ce filleul,
  pendant 7 jours à partir du même instant.
- Maximum de trois filleuls simultanés pour un parrain ; expirations indépendantes.
- Les deux rôles comptent : trois filleuls et son propre parrain donnent +40 %.
  Le vote porterait la somme à +60 %, mais **le plafond global ramène le total à +50 %**.

```powershell
.\.venv\Scripts\python.exe tools/simulate_ram_rewards.py --runs 3 --output simulation_results/ram_rewards/capped_50
.\.venv\Scripts\python.exe tools/simulate_ram_rewards.py --runs 3 --cohort active-referrals --output simulation_results/ram_rewards/capped_50/active_referrals
```

La comparaison utilise les mêmes graines et stratégies, avec ou sans bonus.
Deux précisions sont testées : le moteur actuel et un stockage précis avec
transfert des fractions vers le portefeuille lors du claim. Dans ce deuxième
mode, les conversions restent à cinq décimales RTM et les reliquats sont conservés
hors RAM. Ce mécanisme n'est implémenté que dans le simulateur.

Les scénarios temporaires emploient un vote par jour et les dates de FW1 de
trois autres joueurs simulés sans bonus. La cohorte `active-referrals` emploie
des joueurs à 100 victoires/jour pour observer effectivement les activations et
les expirations sur 30 jours. Le test extrême accorde le bonus maximal dès J0
en permanence, même avant les conditions de déblocage : c'est une hypothèse
plus favorable au joueur que la règle demandée.
