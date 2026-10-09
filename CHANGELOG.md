# :rocket: Beta Update N°4

## :chart_with_upwards_trend: **Cours dynamique du Rootium (`/convert`)**

Le taux **RTM → USD** n'est plus fixe : il évolue désormais **toutes les 15 minutes** selon la moyenne des variations de **Bitcoin, Ethereum et Solana**. Si les trois cryptos montent en moyenne de 1 %, le Rootium monte de 1 % ; si la moyenne est nulle, le cours ne bouge pas.

Le devis de `/convert` affiche le **cours appliqué** et l'heure de sa dernière actualisation. Si le cours change entre ton devis et ta confirmation, la vente est refusée et il faut relancer la commande pour obtenir un devis au nouveau cours. Si le flux de marché est interrompu, le dernier cours valide reste utilisé et le devis t'avertit que le cours n'est plus actualisé.

Le Rootium reste une monnaie interne au jeu : le cours est inspiré du marché, aucune transaction réelle n'est effectuée. L'équilibrage des combats (`/hack`) reste calculé sur un taux de référence stable.

## :bar_chart: **Terminal de marché & Graphiques (`/market` & `!market`)**

Un nouveau terminal interactif permet de suivre le cours du Rootium en temps réel :
- **Vue instantanée** : cours courant, tendance avec sparkline Unicode, variation sur la période (24 h, 7 j, 30 j) et contributions respectives de BTC, ETH et SOL.
- **Graphiques haute résolution** : génération à la demande d'un graphique détaillé adapté aux mobiles et ordinateurs, avec courbe d'évolution et repères temporels.

## :bell: **Alertes de cours personnalisées (`/market` & `!market alert`)**

Tu peux désormais programmer jusqu'à **5 alertes de prix** pour être notifié en message privé dès que le Rootium franchit tes objectifs :
- **Sens au choix** : surveillance à la hausse (`above`, ≥) ou à la baisse (`below`, ≤).
- **Configuration intuitive** : saisie du seuil et du sens via un formulaire interactif accessible depuis le bouton **Alertes** du terminal de marché.
- **Anti-spam & réarmement** : délai de rappel paramétrable (défaut 60 min, minimum 15 min) et réarmement automatique dès que le cours repasse de l'autre côté du seuil.
- **Gestion complète** : consultation, activation/désactivation et suppression de tes alertes directement dans l'interface Discord.

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