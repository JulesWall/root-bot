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

## :globe_with_meridians: **Intégration au Poste de Commande (`/network` & `!n`)**

- **Nouvel onglet `[📈 Marché]`** : accédez au terminal de marché directement depuis votre interface réseau `/network` (`!n` ou `!n market`).
- **Expérience complète** : affiche le graphique dynamique de la période, les cours et le portefeuille, tout en conservant les boutons d'achat/vente, d'alertes et de retour vers Accueil, Ferme, Matériel et Opérations.

## :receipt: **Frais de transaction de 1 % & Traçabilité Blockchain**

- **Frais de 1 %** : une commission fixe de 1 % s'applique désormais sur toutes les opérations du comptoir (achats et ventes). Ces frais sont détaillés de manière transparente sur chaque devis avant confirmation.
- **Registre `#blockchain`** : chaque achat (`BUY TOKEN`) et chaque vente (`SELL TOKEN`) est immédiatement ancré sur la blockchain publique avec l'adresse du DEX (`0xROOTIUM_DEX`), le montant net et les frais prélevés (`FEE`).
- **Suivi économique** : les volumes d'achat, de vente et les commissions de marché sont désormais suivis et consolidés en temps réel dans les rapports économiques.

## :chart_with_upwards_trend: **Cours dynamique du Rootium**

Le cours **RTM / USD** évolue désormais **toutes les 15 minutes** selon l'activité et les variations du marché. Si le marché est haussier, le Rootium s'apprécie ; si le cours est stable, le cours ne bouge pas. Si le cours varie entre votre devis et votre confirmation, la transaction est sécurisée et un nouveau devis actualisé vous est proposé.

Le Rootium reste une monnaie interne au jeu : aucune transaction réelle en cryptomonnaie n'est effectuée. L'équilibrage des combats (`/hack`) reste calculé sur un taux de référence stable.

## :bar_chart: **Terminal de marché & Graphiques**

Un terminal complet permet de suivre le cours du Rootium en temps réel :
- **Vue instantanée** : cours courant, variation sur la période (24 h, 7 j, 30 j) et statut du flux.
- **Navigation fluide** : basculez d'une période à l'autre en un clic sur les boutons temporels (`24 h`, `7 j`, `30 j`) avec génération du graphique correspondant.

## :bell: **Alertes de cours personnalisées (`/market` & `!market alert`)**

Tu peux désormais programmer jusqu'à **5 alertes de prix** pour être notifié en message privé dès que le Rootium franchit tes objectifs :
- **Sens au choix** : surveillance à la hausse (`above`, ≥) ou à la baisse (`below`, ≤).
- **Configuration intuitive** : saisie du seuil et du sens via un formulaire interactif accessible depuis le bouton **Alertes** du terminal de marché.
- **Anti-spam & réarmement** : délai de rappel paramétrable (défaut 60 min, minimum 15 min) et réarmement automatique dès que le cours repasse de l'autre côté du seuil.
- **Gestion complète** : consultation, activation/désactivation et suppression de tes alertes directement dans l'interface Discord.

## :zap: **Ventes automatiques de Rootium (`/market` & `!market autosell`)**

Automatise la prise de profit sur tes gains de minage avec des règles de vente intelligentes :
- **Règles configurables (jusqu'à 3 par joueur)** : déclenchement selon un seuil en USD (`above` à la hausse ou `below` à la baisse).
- **Montant fixe ou pourcentage du solde** : choisis de vendre une quantité précise (ex: `100 RTM`) ou une part de ton portefeuille (ex: `50 %` ou `tout`).
- **Plafond de sécurité & récurrence** : configure un plafond maximal par vente et choisis entre un ordre unique (`once`) ou récurrent (`repeat` avec intervalle de sécurité).
- **Exécution transactionnelle garantie** : chaque vente est convertie automatiquement au cours officiel validé du cycle, inscrite dans le journal `#blockchain` et confirmée par un reçu détaillé en message privé.
- *Rappel : le Rootium et ses ventes sont des mécaniques virtuelles internes au jeu sans interaction avec des marchés réels.*

# :rocket: Beta Update N°3

## :shield: **Système de dégâts critiques**

Désormais lorsqu'une attaque atteint plus de 60% des modules visés, l'attaque est stoppée et la procédure de **dégâts critiques** se déclenche.

La perte est alors plafonnée à **60% des modules de la catégorie visée**, afin d'éviter une destruction trop importante. 

Suite à ce déclenchement, l'infrastructure de la cible est **verrouillée pendant 48h** et le joueur ne peut plus attaquer, être attaqué ou lancer de scan pendant cette durée.

## :robot: **Système de macros (`/macro` & `!macro`)**

Ajout d'un système de macro qui permet d'exécuter plusieurs commandes en une seule. Pour cela, il faut créer vos propres macros avec la commande `/macro-create` ou `!macro create`.

Il est possible de créer jusqu'à **3 macros par joueur**, contenant chacune **1 à 5 étapes**.

L'exécution se fait avec `/macro nom:<nom>` ou `!macro <nom>` et le mode détaillé reste disponible avec `!macro <nom> d`.

## :office: **Les Firewalls deviennent des Infrastructures (`/upgrade`)**

Les Firewalls sont remplacés par les **Infrastructures de contrôle**. Cette évolution change les intitulés dans le bot et introduit six niveaux d’infrastructure :

**Smartphone bricolé → PC assemblé → Station de travail → Serveur dédié → Salle des serveurs → Datacenter**

Les multiplicateurs de récompenses sur les events, le `/hourly` et les contrats ont été augmentés et passent de ×1 au niveau 0 à ×15 au niveau 5 :

**×1, ×1.75, ×3, ×5.25, ×9 et ×15.**


## :desktop: **Refonte graphique complète du `/network` et des autres commandes**

## :briefcase: **Refonte des contrats (`/contract`)**

Le système de contrats bénéficie d'une **refonte de son interface**, avec des offres plus lisibles et une présentation inspirée d'un tableau de missions réel.

Les contrats sont désormais présentés sous forme de cartes avec leur entreprise, leur durée et leur rémunération.

Les **4 contrats proposés** sont tirés dynamiquement parmi différentes entreprises.

## :gear: **Équilibrage de la compilation de point d'ATK (`/compile`)**

Les trois méthodes de compilation ont été rééquilibrées afin de proposer des choix plus distincts, les prix ont été réduits légèrement afin de permettre que toutes les méthodes de compilation soient utiles. 