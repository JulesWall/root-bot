# :rocket: Beta Update N°4

## :currency_exchange: **Comptoir de Marché unifié : Achat & Vente de Rootium (`/market` & `!market`)**

Les commandes autonomes `/convert` et `!sell` ont été retirées au profit d'un **Terminal de Marché unifié** accessible via `/market` et `!market`. Vous pouvez désormais :
- **Consulter votre solde** : affichage direct de vos avoirs en temps réel (`Portefeuille : X USD · Y RTM`).
- **Vendre du Rootium** (RTM → USD) : transformez vos gains de minage en dollars au cours dynamique en direct.
- **Acheter du Rootium** (USD → RTM) : investissez vos dollars pour acquérir des tokens Rootium au cours du marché.
- **Interface interactive** : lancez vos ordres en un clic via les boutons `[🛒 Acheter RTM]` et `[💰 Vendre RTM]` et saisissez le montant (ou `all`) dans un formulaire dédié avec confirmation instantanée.
- **Commandes rapides** : exécutez vos ordres directement en commandes texte :
  - `!market buy <montant|all> [confirm]` (ou alias `!buy`)
  - `!market sell <montant|all> [confirm]` (ou alias `!sell`, `!cv`)
- **Stabilité** : correction d'une anomalie lors de la soumission des formulaires modaux de vente et d'achat sur le terminal.

## :globe_with_meridians: **Poste de Commande & Navigation (`/network` & `!n`)**

- **Refonte et fusion des rubriques** : suppression de l'onglet distinct « Matériel » ; l'ensemble des modules de défense et des accès boutique est désormais centralisé directement sur la page **Opérations** pour une vue complète de la sécurité.
- **Épuration des Opérations** : retrait du bouton de récolte de minage sur la page Opérations, recentrant l'interface sur la surveillance et le combat.
- **Terminal Marché optimisé** : suppression de la rangée d'onglets sur la page Marché pour mettre en valeur les commandes de trading, et remplacement du bouton de récolte par un bouton `[↩️ Retour]` vers l'accueil.
- **Nouvel onglet `[📈 Marché]`** : accédez au terminal de marché complet directement depuis votre interface réseau (`/network` ou `!n market`).

## :receipt: **Frais de transaction de 1 % & Traçabilité Blockchain**

- **Frais de 1 %** : une commission fixe de 1 % s'applique désormais sur toutes les opérations du comptoir (achats et ventes). Ces frais sont détaillés de manière transparente sur chaque devis avant confirmation.
- **Registre `#blockchain`** : chaque achat (`BUY TOKEN`) et chaque vente (`SELL TOKEN`) est immédiatement ancré sur la blockchain publique avec l'adresse du DEX (`0xROOTIUM_DEX`), le montant net et les frais prélevés (`FEE`).
- **Suivi économique** : les volumes d'achat, de vente et les commissions de marché sont désormais suivis et consolidés en temps réel dans les rapports économiques.

## :chart_with_upwards_trend: **Cours dynamique du Rootium**

Le cours **RTM / USD** évolue désormais **toutes les 15 minutes** selon l'activité et les variations du marché. Si le marché est haussier, le Rootium s'apprécie ; si le cours est stable, le cours ne bouge pas. Si le cours varie entre votre devis et votre confirmation, la transaction est sécurisée et un nouveau devis actualisé vous est proposé.
- **Volatilité amplifiée** : la variation de chaque bougie de 15 minutes est désormais multipliée par un coefficient de volatilité (`volatility_multiplier` dans `math.json`, fixé à **×2.5** par défaut) pour offrir des mouvements de cours plus dynamiques et stimulants.

Le Rootium reste une monnaie interne au jeu : aucune transaction réelle en cryptomonnaie n'est effectuée. L'équilibrage des combats (`/hack`) reste calculé sur un taux de référence stable.

## :bar_chart: **Terminal de marché & Graphiques**

Un terminal complet permet de suivre le cours du Rootium en temps réel :
- **Vue instantanée** : cours courant, variation sur la période (24 h, 7 j, 30 j) et statut du flux.
- **Navigation fluide** : basculez d'une période à l'autre en un clic sur les boutons temporels (`24 h`, `7 j`, `30 j`) avec génération du graphique correspondant.
- **Rattrapage automatique au démarrage** : le bot analyse désormais les 7 derniers jours en base et calcule tous les créneaux de 15 minutes manquants pour combler les interruptions d'activité. Même après une coupure du bot, l'historique et les graphiques restent continus, complets et fidèles au marché réel.

## :bell: **Alertes de cours personnalisées (`/market` & `!market alert`)**

Tu peux désormais programmer jusqu'à **5 alertes de prix** pour être notifié en message privé dès que le Rootium franchit tes objectifs :
- **Sens au choix** : surveillance à la hausse (`above`, ≥) ou à la baisse (`below`, ≤).
- **Configuration simplifiée** : saisie directe du seuil et du sens via le formulaire interactif (sans délai de rappel superflu).
- **Usage unique & Zéro spam** : dès que l'alerte se déclenche et t'est envoyée en message privé, elle est automatiquement supprimée de la base de données.
- **Gestion complète** : consultation, activation/désactivation et suppression de tes alertes en attente directement dans l'interface Discord.

## :zap: **Ordres Automatiques Unifiés : Achat & Vente (`/market` & `/network`)**

Automatise tes investissements et tes prises de profit avec des ordres intelligents programmables :
- **Un seul bouton unifié `[⚡ Ordres auto]`** : accessible sur le terminal de marché `/market` ainsi que sur la page Marché du réseau `/network`.
- **Achat et Vente configurables (jusqu'à 3 ordres)** : choisis l'action (`buy` pour convertir des USD en RTM ou `sell` pour convertir des RTM en USD), le seuil cible en USD (`above` ≥ ou `below` ≤), et la quantité (montant fixe, pourcentage `%` ou `all`).
- **Gestion intuitive** : badges clairs `🛒 [ACHAT]` et `💰 [VENTE]` dans l'aperçu, menu d'activation/désactivation et de suppression en un clic.
- **Exécution transactionnelle garantie** : exécuté atomiquement au cours validé du cycle, sans historique encombrant en base de données.
- **Notifications privées & Blockchain** : reçu détaillé envoyé en DM dès l'exécution de l'ordre (achat ou vente) et journalisation publique dans `#blockchain` (`AUTO BUY` ou `AUTO SELL`).

## :zap: **Commandes rapides d'Achat et de Vente**

Pour les traders réactifs, des raccourcis dédiés permettent d'opérer instantanément :
- **Vente rapide** :
  - `!sell <montant|all> [confirm]` (alias `!vente`, `!cv`)
  - Commande slash `/sell <amount> [confirm]`
- **Achat rapide** :
  - `!buyrtm <montant|all> [confirm]` (alias `!achat`, `!mbuy`)
  - `!buy rtm <montant|all> [confirm]` (délégation automatique depuis la commande d'achat classique)

## :wrench: **Optimisation Base de Données & Corrections**

- **Nettoyage SQL** : suppression des tables et historiques superflus (`rtm_auto_sell_runs`), l'idempotence des ordres automatiques étant désormais intégrée directement à la table des règles (`last_run_market_ts`).
- **Continuité & Fiabilité du Cours de Marché** : correction définitive du redémarrage accidentel au cours d'amorçage après le rattrapage historique. Tout nouveau cycle s'enchaîne désormais strictement sur la dernière bougie historique (`price_after`). Un système d'auto-réparation assainit et recalcule automatiquement toute rupture de continuité au démarrage du bot.
- **Synchronisation du cours** : correction de la synchronisation entre le texte de l'embed et le graphique, garantissant l'affichage immédiat du cours variable en temps réel sans blocage sur la valeur d'amorçage.
- **Correction d'exception** : résolution de l'erreur `VisualState.CONFIRMATION` lors des validations interactives de conversion de marché.
- *Rappel : le Rootium et ses échanges sont des mécaniques virtuelles internes au jeu sans interaction avec des marchés réels.*

## :stopwatch: **Lisibilité des Événements Réseau (`/event` & `!event`)**

- **Clarté des statuts indisponibles** : les événements en attente ou en recharge affichent désormais explicitement l'état `Indisponible` accompagné du pictogramme dédié Root OS **`root_temps_rouge`** (horloge rouge `#FF5A5F`), permettant d'identifier immédiatement d'un coup d'œil les défis actifs par rapport à ceux en cours de cooldown.
- **Précision temporelle** : conservation des horodatages dynamiques Discord et des durées restantes pour savoir exactement quand chaque événement redevient disponible.


