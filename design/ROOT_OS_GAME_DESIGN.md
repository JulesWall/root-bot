# Root OS — Proposition courte

Version 2 · Cette version remplace le précédent dossier.

**On garde le jeu actuel, mais on transforme le PvP en opérations logicielles et `/network` en véritable poste de commande. Le nombre de mineurs est illimité : aucun emplacement, aucun achat d'extension et aucune montée de niveau imposée par leur quantité.**

## 1. Ce qui reste familier

- Les dollars, le RTM, la conversion, les H/s et les tiers de mineurs.
- Le firewall comme niveau de progression et règle d'accès aux tiers.
- Les achats de mineurs sans limite de quantité, leur mémoire et la récolte actuelle.
- Les contrats, les événements, la réputation et leurs récompenses actuelles.
- Les commandes habituelles : `/network`, `/buy`, `/claim`, `/upgrade`, `/scan`, `/compile`, `/hack`.
- Les cibles de niveau équivalent ou supérieur ; les représailles pendant 72 heures restent l'exception.

Je retire de la première proposition les châssis à acheter, les rangs supplémentaires, le stockage de huit heures, les quotas quotidiens de récompenses et la suppression du bonus de réputation. La refonte porte sur le PvP et sa présentation.

Le PC représente **le poste qui pilote la ferme**, pas une boîte dans laquelle chaque mineur doit rentrer. Dix ou dix mille modules sont regroupés par tier à l'écran. Le niveau du firewall fait évoluer l'illustration du poste et du réseau, sans créer une nouvelle progression mécanique.

## 2. Le nouveau rôle du matériel

**Minage : produire.** Les modules continuent d'ajouter leurs H/s et leur mémoire comme aujourd'hui.

**Attaque : développer.** Les modules existants deviennent des modules de calcul. Leur débit actuel en bits/s sert à rechercher une faille et compiler ses logiciels. `/compile` prépare désormais un logiciel réutilisable, plutôt qu'une réserve de points à envoyer contre un mur de défense. Une seule recherche ou compilation tourne à la fois ; les contrats restent indépendants.

**Défense : surveiller.** Les modules de défense sont conservés, mais une attaque ne les détruit plus. Ils accélèrent le contrôle automatique du réseau. Le propriétaire voit directement « prochain contrôle dans 42 min », sans devoir interpréter une nouvelle statistique.

Réglage initial : un contrôle toutes les quatre heures sans modules de défense, jusqu'à une heure avec une défense importante. Un diagnostic manuel reste gratuit et dure cinq minutes. Pour le calibrage, l'intervalle en minutes est `max(60, 240 / (1 + D/F))`, avec D la puissance des modules de défense et F la défense de base du firewall, au minimum 100. À D = F, le contrôle revient toutes les deux heures. Ces intervalles désignent la fin des contrôles.

**La surveillance détecte une intrusion ; le patch empêche son retour.** Les deux dépenses ont donc un rôle différent.

## 3. Une faille devient une affaire

Exemple : je lance une recherche sur les mineurs T3. Elle aboutit à **Écho**, une faille commune aux mineurs T3 non corrigés. Je peux alors :

- Compiler le logiciel qui l'exploite et attaquer.
- Vendre un logiciel prêt à utiliser.
- Vendre le dossier complet, permettant à l'acheteur de fabriquer ses propres logiciels.
- Fabriquer le patch, le vendre ou le publier gratuitement.

Un logiciel acheté reste utilisable ; chaque opération a néanmoins un coût en RTM. Une licence ne donne pas le droit de copier le dossier du vendeur. Acheter le dossier complet donne ce droit. Les offres sont vérifiées par le jeu : pas de faux correctifs.

Un patch protège **tous mes mineurs du tier concerné contre cette faille précise**, y compris mes achats futurs. Il est permanent, sans frais par mineur. Je peux installer tous mes patchs, sans limite ni incompatibilité artificielle.

La recherche peut retrouver une faille déjà découverte par quelqu'un d'autre : aucun monopole absolu. Pour éviter une avalanche de maintenance, chaque famille et tier comporte au plus trois failles sans correctif public ; une nouvelle faille distincte apparaît au plus toutes les six heures, uniquement à l'issue d'une recherche de joueur. Une recherche sans résultat disponible ne peut pas être lancée ni facturée.

Les patchs publics s'installent automatiquement sur les réseaux qui ont activé cette option, au plus tard six heures après publication. L'option est active par défaut. Une installation manuelle prend cinq minutes. Un patch privé peut donc se vendre pour gagner du temps, et sa publication ne protège pas instantanément tout le monde.

## 4. Deux attaques pour commencer

### Siphonnage discret

Après les **45 minutes de préparation** familières, le logiciel détourne **5 % du minage ciblé pendant quatre heures maximum**. Le revenu reçu baisse, mais aucun message ne dit immédiatement « tu es piraté ».

Un diagnostic, un contrôle automatique ou le bon patch retire le logiciel. L'attaquant conserve le RTM déjà acquis. La victime garde tous ses mineurs.

### Extraction visible

Même préparation de 45 minutes, mais la cible est avertie dès le lancement. Si la faille reste ouverte à l'arrivée, l'opérateur détourne **15 % du minage ciblé pendant deux heures maximum**.

Le défenseur peut patcher avant l'arrivée. Après intrusion, il peut également restaurer le service : cinq minutes de préparation, puis trente minutes de fonctionnement local à 80 % du débit, sans accès extérieur. Le patch bloque durablement la faille ; restaurer retire seulement l'intrusion.

Les taux et durées sont des valeurs de départ à tester. Les ransomware et sabotages d'atelier restent pour une extension : les deux premières attaques suffisent à valider la boucle.

### Les règles communes

- `/scan` donne une photographie horodatée de la cible, pas une garantie sur son état futur.
- Le devis montre le coût complet, le débit ciblé et le gain maximal. Les frais augmentent avec le volume engagé ; une ferme immense n'est pas attaquée au prix d'un petit mineur.
- Une faille compatible et non patchée fonctionne ; acheter plus de puissance ne traverse jamais son patch.
- Une seule opération offensive active par joueur, tous serveurs confondus. Le minage et le développement continuent pendant celle-ci.
- Tous attaquants confondus : au plus 5 % du flux en siphonnage discret et 15 % au total. En cas de dépassement, les gains sont réduits proportionnellement, sans priorité au premier arrivé.
- Le portefeuille déjà encaissé, les commandes et le matériel restent hors d'atteinte.

Les frais exacts de recherche, compilation, scan et lancement doivent être recalibrés ensemble : conserver les anciens coûts d'attaque avec de petits prélèvements reproduirait le problème actuel. Le bilan sépare le coût du logiciel réutilisable et celui de chaque opération.

**Attention à la mémoire actuelle :** quatre mineurs T3, hors bonus, produisent 0,015 RTM/h et remplissent leur mémoire en 35 minutes. Un siphonnage de 5 % rapporte donc au plus 0,0004375 RTM avant saturation si personne ne récolte, même s'il peut durer quatre heures. Le devis utilise la place réellement disponible. Les unités détournées laissent des reçus en mémoire jusqu'à la récolte : attaquer un compte complice ne prolonge pas son autonomie.

Une grosse ferme au même niveau peut rester plus riche qu'une petite : je conserve ce choix du jeu actuel. Les limites portent sur les effets des attaques, jamais sur le nombre de mineurs.

## 5. Discord devient le poste de commande

### Une forme reconnaissable

Un message principal compact : **une illustration du poste, l'état du réseau, le travail en cours et les actions utiles**. Les boutons changent la vue dans ce message, sans remplir le salon de panneaux successifs.

L'illustration montre du matériel identifiable : écran, tour, serveur, puis ferme distante. Elle évolue avec le firewall et l'ampleur de l'installation. Les modules sont regroupés visuellement, jamais dessinés un par un. Un service isolé ou un stockage plein change son état visuel ; une intrusion encore inconnue n'allume pas un voyant « piraté ».

Direction visuelle : illustration pixel art détaillée mais nette, intégrée à un message Discord sobre. Texte normal et lisible sur mobile ; monospace réservé aux petits journaux. Vert pour une activité normale, ambre pour une anomalie, rouge pour une menace confirmée. Pas de pluie de code ni d'animation qui retarde les commandes.

### Écran 1 — Je retrouve mon installation

> **ROOT OS · Poste de Nox**
> Firewall 3 · Réseau personnel
>
> **Ferme** · 4 mineurs T3 · 2 500 H/s
> **Mémoire** · 0,005 / 0,00875 RTM
> **Production** · 0,015 RTM/h
> **Développement** · Patch Écho · encore 18 min
>
> Dernier événement : un correctif public a été installé.

Boutons : **Récolter · Matériel · Logiciels · Opérations · Journal**. Le marché s'ouvre depuis Logiciels ; les commandes directes restent disponibles.

Les montants de cet exemple sont hors bonus. En jeu, l'écran utilise toujours les valeurs réelles du compte. Le détail Matériel regroupe les quantités par tier, même quand elles deviennent très grandes.

### Écran 2 — Quelque chose ne tourne pas rond

> **Ferme T3 · Rendement inhabituel**
>
> Production attendue : 0,015 RTM/h
> Production reçue : 0,01425 RTM/h
> Écart : -5 %
>
> Une connexion reste à identifier.

Boutons : **Diagnostiquer · Voir les connexions · Retour**.

Après les cinq minutes de diagnostic, cette même vue devient :

> **Intrusion identifiée · Écho**
> Siphonnage interrompu.
> Faille concernée : mineurs T3.
> Correctif public : aucun disponible.

Boutons : **Développer un patch · Chercher au marché · Analyser la trace**.

Analyser la trace prend quinze minutes, gratuitement, et identifie l'attaquant dans le jeu. La victime peut alors exercer ses représailles pendant 72 heures. La discrétion retarde l'identification, sans rendre l'opérateur intouchable.

### Écran 3 — Mon opération devient une histoire

> **Écho · Connexion à K-4821**
>
> 14 h 00 · Opération engagée.
> 14 h 45 · Accès obtenu aux mineurs T3.
> 15 h 05 · Connexion fermée par le réseau distant.
>
> Activité réelle : 20 min
> RTM récupéré : 0,00025
> Résultat : interruption par un contrôle.

Boutons : **Voir le bilan · Ouvrir le logiciel · Retour**.

Cet exemple correspond au flux de quatre mineurs T3, sans contention ni saturation avant l'interruption. Le bilan ajoute les frais effectivement payés et le résultat net ; il ne confond pas butin brut et bénéfice.

Ces lignes apparaissent dans le journal, sans envoyer un message toutes les minutes. Le logiciel reste dans ma bibliothèque : je peux le réutiliser, vendre une licence ou développer sa protection.

### Les détails qui font l'immersion

- Je nomme mon poste et ma ferme ; ces noms reviennent dans les rapports.
- Un logiciel porte le nom et la signature de son auteur joueur.
- Un incident explique une variation réelle de mon réseau.
- Les vues sensibles sont privées ; je choisis les bilans que je partage publiquement.
- Les délais continuent quand je ferme Discord. Les événements restent dans le Journal si mes messages privés sont fermés.
- Un ancien bouton recharge un devis à jour. Un panneau disparu se retrouve avec `/network`.

**La direction retenue : garder les achats et la croissance illimitée que les joueurs connaissent, puis leur donner un ordinateur identifiable, des logiciels signés et des opérations dont ils comprennent les conséquences.**

---

Note de conception : les exemples de minage reprennent les paramètres locaux actuels de `data/math.json`, hors bonus de réputation. Les règles PvP décrites sont une proposition, pas des modifications déjà développées. Les soldes et équipements existants sont conservés ; le stock ATK retiré nécessitera un barème de reconversion explicite avant migration.
