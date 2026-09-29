# Root OS — Proposition courte

Version 3 · Mise à jour des infrastructures et des familles de logiciels PvP.

**Statut :** les intentions de jeu ci-dessous sont retenues pour la réflexion. Les paramètres indiqués « à définir » ne sont pas des règles validées. Ce document ne demande aucune implémentation immédiate.

**On garde le jeu actuel, mais on transforme le PvP en opérations logicielles et `/network` en véritable poste de commande. Le nombre de mineurs est illimité : aucun emplacement, aucun achat d'extension et aucune montée de niveau imposée par leur quantité.**

## 1. Ce qui reste familier

- Les dollars, le RTM, la conversion, les H/s et les tiers de mineurs.
- Les six niveaux de progression et l'accès aux tiers ; l'infrastructure de contrôle remplace leur présentation en niveaux de firewall.
- Les achats de mineurs sans limite de quantité, leur mémoire et la récolte actuelle.
- Les contrats, les événements, la réputation et leurs récompenses actuelles.
- Les commandes habituelles : `/network`, `/buy`, `/claim`, `/upgrade`, `/scan`, `/compile`, `/hack`.
- Les cibles de niveau équivalent ou supérieur ; les représailles pendant 72 heures restent l'exception.

L'infrastructure représente **le poste qui pilote la ferme**, pas une boîte dans laquelle chaque mineur doit rentrer. Dix ou dix mille modules sont regroupés par tier à l'écran. Aucun niveau ne crée d'emplacements de minage.

Progression visuelle : **0 — Smartphone bricolé ; 1 — PC assemblé ; 2 — Station de travail ; 3 — Serveur dédié ; 4 — Salle des serveurs ; 5 — Datacenter.** Les trois premiers niveaux conservent le même bureau et la même fenêtre, progressivement rénovés. À partir du serveur dédié, on change de lieu. Illustrations : `design/infrastructures-controle/`.

## 2. Le nouveau rôle du matériel

**Minage : produire.** Les modules continuent d'ajouter leurs H/s et leur mémoire comme aujourd'hui.

**Attaque : développer.** Les modules existants deviennent des modules de calcul. Leur débit en bits/s sert aux recherches et compilations. Le joueur choisit d'abord une intention : siphonner, espionner, bloquer, voler ou ralentir. Il recherche ensuite une vulnérabilité compatible avec la cible choisie et compile son logiciel. Une seule recherche ou compilation tourne à la fois ; les contrats restent indépendants.

**Défense : gagner du temps et fabriquer les correctifs.** Les modules de défense remplissent simultanément deux fonctions :

- Ils fournissent une capacité de développement défensif réservée à la recherche et à la compilation des patchs. Un correctif peut ainsi être préparé en parallèle du logiciel offensif en cours, sans interrompre ce dernier.
- Ils ralentissent passivement l'installation des logiciels hostiles sur le réseau.

## 3. Des logiciels identifiables et échangeables

Exemple : je veux détourner du minage. Je lance le développement de **Hostile Miner**, ciblant les mineurs T3. Ma découverte reçoit une empreinte et permet de compiler **Hostile Miner · K7M2**.

- **Famille : Hostile Miner.** Elle décrit l'intention et l'effet du logiciel.
- **Empreinte : K7M2.** Identifiant court unique attribué par le jeu, pas une version ni un niveau de puissance.
- **Cible : mineurs T3.** Elle précise la compatibilité de la vulnérabilité exploitée.

Les copies et reventes conservent l'empreinte. Renommer ou recompiler ne crée pas une nouvelle faille et ne contourne jamais un correctif. 

Avec ma découverte, je peux :

- Compiler le logiciel qui l'exploite et attaquer.
- Vendre un logiciel prêt à utiliser.
- Fabriquer le patch, le vendre ou le publier gratuitement.

Un logiciel acheté reste utilisable ; chaque opération a néanmoins un coût en RTM. Une copie utilisable ne donne pas accès au dossier complet de recherche. Acheter le dossier permet de fabriquer ses propres copies. Le vol de logiciel est une autre manière d'obtenir une copie, pas automatiquement son dossier. Les offres sont vérifiées par le jeu : pas de faux correctifs.

Les découvertes sont fréquentes et provoquées par les recherches des joueurs. Leur cadence exacte et les règles de redécouverte restent à définir pour éviter une maintenance incessante. 

**Chaque joueur doit patcher son propre réseau.** Publier un correctif, même gratuitement, ne protège pas automatiquement les autres. Chacun l'obtient puis l'installe. 

## 4. Sept familles retenues

Siphonnage de puissance — Hostile Miner
Le logiciel s'installe sur le réseau et détourne un pourcentage de la puissance de minage concernée au profit de l'attaquant. Exemple de travail : **15 % de 15 kH/s = 2,25 kH/s détournés**. L'installation persiste jusqu'à identification et application du correctif adéquat. La simple détection ne coupe pas le siphon.
### Espionnage préventif
Observer les logiciels que l'adversaire prépare pour pouvoir développer et installer leurs correctifs avant leur compilation ou utilisation. 
### Blocage contre rançon
Bloquer une commande précise et proposer un déblocage contre paiement. La victime choisit de payer ou de rechercher et installer un patch. 
### Vol de monnaie
Une fraude logicielle permet de dérober directement de l'argent, 
### Saturation du calcul
Consommer une partie de la capacité de développement adverse pour ralentir recherches et compilations. 
### Scan complet du réseau
Obtenir une photographie horodatée de l'infrastructure, des mineurs, de la puissance, de la production, des réserves, des logiciels installés et des connexions de la cible. Le rapport ne se met pas à jour automatiquement.
### Vol de logiciel
Exfiltrer un logiciel ou une faille chez l'adversaire 

### Les règles communes

- Le devis montre le coût complet, l'effet, la cible et les conditions d'arrêt. Un siphon sans durée fixe n'a pas de gain maximal connu : afficher une estimation conditionnelle, jamais une promesse de bénéfice.
- Une faille compatible et non patchée fonctionne ; acheter plus de puissance ne traverse jamais son patch.
- Le nombre d'opérations simultanées, leurs délais et leurs coûts doivent être revus pour ces sept familles. Ne pas transposer automatiquement les 45 minutes ou la limite d'une opération de l'ancienne proposition.
- Définir des plafonds d'effets cumulés, tous attaquants confondus, notamment sur le minage, les pertes monétaires et le ralentissement. Les anciens plafonds de 5 % et 15 % ne sont plus validés.
- Une combinaison d'attaques ne doit jamais supprimer toutes les possibilités de défense. Paiement, recherche et installation d'un correctif doivent former de vrais choix.
- Les mineurs ne sont ni volés ni détruits par ces familles. Certaines commandes et réserves monétaires deviennent ciblables, dans des limites encore à définir.

Les frais exacts de recherche, compilation, scan et lancement doivent être recalibrés ensemble : conserver les anciens coûts d'attaque avec de petits prélèvements reproduirait le problème actuel. Le bilan sépare le coût du logiciel réutilisable et celui de chaque opération.

**Attention à la mémoire actuelle :** quatre mineurs T3, hors bonus, produisent 0,015 RTM/h et remplissent leur mémoire en 35 minutes. Il faut décider où est stockée la production détournée et ce qui arrive quand la mémoire de l'un des comptes est pleine. Un siphon persistant ne signifie pas un revenu infini. Vérifier qu'un compte complice ne permet pas de contourner la récolte ou les limites de stockage.

Une grosse ferme au même niveau peut rester plus riche qu'une petite : je conserve ce choix du jeu actuel. Les limites portent sur les effets des attaques, jamais sur le nombre de mineurs.

## 5. Discord devient le poste de commande

### Une forme reconnaissable

Un message principal compact : **une illustration du poste, l'état du réseau, le travail en cours et les actions utiles**. Les boutons changent la vue dans ce message, sans remplir le salon de panneaux successifs.

L'illustration montre l'infrastructure de contrôle du niveau 0 à 5. Les mineurs sont regroupés visuellement, jamais dessinés un par un. Un stockage plein change son état visuel ; une intrusion encore inconnue n'allume pas un voyant « piraté ».

Direction visuelle : pixel art détaillé, texte lisible sur mobile et emojis personnalisés `root_*`. Turquoise pour l'état normal, ambre pour l'anomalie, sans compter sur la couleur seule. La forme technique, les composants V2 et les interactions sont décrits dans `../embed.md`. Pas de pluie de code ni d'animation qui retarde les commandes.

La démo reste une référence esthétique, pas une autorité sur les règles PvP : son bouton d'isolation ne valide pas une autre façon d'arrêter Hostile Miner sans patch.

### Écran 1 — Je retrouve mon installation

> **ROOT OS · Poste de Nox**
> Serveur dédié · Infrastructure 3 · Réseau personnel
>
> **Ferme** · 4 mineurs T3 · 2 500 H/s
> **Mémoire** · 0,005 / 0,00875 RTM
> **Production** · 0,015 RTM/h
> **Développement** · Correctif Hostile Miner / K7M2 · encore 18 min
>
> Dernier événement : un correctif public a été installé.

Boutons : **Récolter · Matériel · Logiciels · Opérations · Journal**. Le marché s'ouvre depuis Logiciels ; les commandes directes restent disponibles.

Les montants de cet exemple sont hors bonus. En jeu, l'écran utilise toujours les valeurs réelles du compte. Le détail Matériel regroupe les quantités par tier, même quand elles deviennent très grandes.

### Écran 2 — Quelque chose ne tourne pas rond

> **Ferme T3 · Rendement inhabituel**
>
> Production attendue : 0,015 RTM/h
> Production reçue : 0,01275 RTM/h
> Écart : -15 %
>
> Une connexion reste à identifier.

Boutons : **Diagnostiquer · Voir les connexions · Retour**.

Après le diagnostic, dont la durée reste à définir, cette même vue devient :

> **Intrusion identifiée · Hostile Miner / K7M2**
> Siphonnage toujours actif · Correctif nécessaire.
> Faille concernée : mineurs T3.
> Correctif public : aucun disponible.

Boutons : **Développer un patch · Chercher au marché · Analyser la trace**.

L'analyse de la trace doit permettre d'identifier l'attaquant pour les représailles ; délai et coût restent à définir. La discrétion retarde l'identification, sans rendre l'opérateur intouchable. Une fois le bon patch installé, la vue confirme l'arrêt du siphonnage et le rétablissement du débit.

### Écran 3 — Mon opération devient une histoire

> **Hostile Miner / K7M2 · Connexion à K-4821**
>
> 14 h 00 · Opération engagée.
> 14 h 45 · Accès obtenu aux mineurs T3.
> 15 h 05 · Correctif installé par le réseau distant.
>
> Activité réelle : 20 min
> RTM récupéré : 0,00075
> Résultat : arrêt par correctif.

Boutons : **Voir le bilan · Ouvrir le logiciel · Retour**.

Cet exemple illustre un prélèvement de 15 % sur 0,015 RTM/h pendant vingt minutes, sans contention ni saturation. Les horaires ne fixent pas le délai de préparation. Le bilan ajoute les frais effectivement payés et le résultat net ; il ne confond pas butin brut et bénéfice.

Ces lignes apparaissent dans le journal, sans envoyer un message toutes les minutes. Le logiciel reste dans ma bibliothèque : je peux le réutiliser, vendre une licence ou développer sa protection.

### Les détails qui font l'immersion

- Je nomme mon poste et ma ferme ; ces noms reviennent dans les rapports.
- Un logiciel porte sa famille, son empreinte et la signature de son auteur joueur.
- Un incident explique une variation réelle de mon réseau.
- Les panneaux du parcours sont publics, comme dans la démo ; cela n'autorise pas les autres à agir sur mon compte. La diffusion des renseignements volés ou scannés reste à trancher avant leur intégration.
- Les délais continuent quand je ferme Discord. Les événements restent dans le Journal si mes messages privés sont fermés.
- Un ancien bouton recharge un devis à jour. Un panneau disparu se retrouve avec `/network`.

**La direction retenue : garder les achats et la croissance illimitée que les joueurs connaissent, puis leur donner un ordinateur identifiable, des logiciels signés et des opérations dont ils comprennent les conséquences.**

---

Note de conception : les exemples de minage reprennent les paramètres locaux actuels de `data/math.json`, hors bonus de réputation. Les règles PvP décrites sont une proposition, pas des modifications déjà développées. Les soldes et équipements existants sont conservés ; le stock ATK retiré nécessitera un barème de reconversion explicite avant migration.
