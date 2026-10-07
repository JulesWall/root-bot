# Plan d’implémentation — macros joueur

## Objectif

Permettre à chaque joueur d’enregistrer jusqu’à trois macros personnelles. Une macro contient une à cinq commandes, exécutées dans l’ordre à son lancement. Toutes les commandes du jeu sont admissibles sauf les commandes d’événements et les commandes de gestion des macros elles-mêmes.

## Commandes et expérience joueur

### Préfixe

- `!macro create` : ouvre un assistant de création.
- `!macro <nom>` : lance directement la macro correspondante.
- `!macro delete <nom>` : supprime la macro. Pour la modifier, le joueur la supprime puis la recrée.

`create` et `delete` sont des mots réservés et ne peuvent pas être utilisés comme noms de macros.

### Slash

- `/macro nom:<nom>` : lance la macro. Ajouter l’autocomplétion pour proposer uniquement les macros du joueur appelant.
- `/macro-create` : ouvre le même assistant de création.
- `/macro-delete nom:<nom>` : supprime la macro choisie.

Discord ne permet pas d’enregistrer automatiquement une slash command pour chaque nom de macro personnalisé. L’option `nom` avec autocomplétion conserve donc un lancement court et compatible avec les noms créés par les joueurs.

Les commandes slash et préfixées doivent appeler la même logique métier afin que les règles et les résultats soient identiques.

## Création d’une macro

L’assistant doit éviter une commande de création à rallonge :

1. Demander un nom, puis vérifier qu’il est valide, disponible et non réservé.
2. Faire choisir une commande dans le catalogue admissible.
3. Présenter ses paramètres avec leurs types et choix possibles, puis demander leurs valeurs. Ne pas demander au joueur de ressaisir le préfixe ou le nom de commande.
4. Afficher l’étape configurée et proposer `Ajouter une étape` ou `Enregistrer`, jusqu’à cinq étapes.
5. Afficher un récapitulatif ordonné et demander la confirmation finale avant l’enregistrement.

La même interface interactive peut être ouverte depuis les deux syntaxes. Le catalogue des commandes et les métadonnées de leurs arguments doivent être partagés avec l’exécuteur pour éviter qu’une macro enregistrée ne soit interprétée différemment de la commande normale.

## Stockage

Ajouter une migration SQL pour deux entités :

- **Macros** : identifiant, identifiant Discord du propriétaire, nom normalisé, date de création et de modification. Ajouter une contrainte d’unicité sur le couple propriétaire/nom.
- **Étapes de macro** : identifiant de macro, position de 1 à 5, identifiant canonique de la commande et arguments typés sérialisés (JSON).

Les accès en lecture, modification et suppression doivent toujours inclure l’identifiant du propriétaire. Une macro ne peut jamais être lancée, consultée ou supprimée par un autre joueur.

## Exécution

Créer un exécuteur partagé qui :

1. Résout la macro par son nom et vérifie son propriétaire.
2. Vérifie les limites par joueur et réserve atomiquement le lancement.
3. Exécute les étapes séquentiellement avec l’identité du joueur et le contexte serveur d’origine.
4. Pour chaque étape, revalide les arguments, permissions, prérequis et conditions métier habituels.
5. S’arrête à la première erreur et indique l’étape concernée. Les étapes déjà réussies ne sont pas annulées : une macro n’est pas une transaction globale.
6. Renvoie un résumé compact plutôt que de publier un message distinct pour chaque commande.

L’exécuteur doit appeler les fonctions métier/services du jeu, pas simuler une saisie de message, rappeler le parseur de commandes ou réutiliser un contexte Discord artificiel. Les commandes ayant une confirmation explicite doivent conserver ce paramètre dans les arguments enregistrés. Les traitements actuellement indissociables d’une interface interactive devront être adaptés pour exposer une opération métier appelable.

Refuser l’ajout des commandes d’événements et de toute commande `macro` (création, suppression ou lancement) afin d’exclure les événements et d’empêcher la récursion.

## Limites par joueur

- **3 macros maximum par joueur**, tous noms confondus.
- **Cooldown de 15 secondes par joueur**, partagé entre toutes ses macros.
- **60 lancements maximum par joueur sur une fenêtre glissante d’une heure**, toutes macros confondues.

Compter chaque tentative de lancement, même si une étape échoue. Vérifier et réserver le cooldown et le quota de manière atomique, avec un verrou ou une transaction par joueur, afin que plusieurs requêtes simultanées ne contournent pas les limites. Les joueurs ont des compteurs indépendants.

## Erreurs et retour utilisateur

Prévoir des réponses localisées pour : macro introuvable, macro appartenant à un autre joueur, limite de trois atteinte, nom invalide/réservé, macro vide, limite de cinq étapes atteinte, commande exclue, arguments invalides, cooldown actif, quota horaire atteint et échec d’une étape. En cas d’échec pendant l’exécution, préciser le numéro et le nom de la commande fautive.

## Ordre de réalisation

1. Recenser les commandes et leurs arguments ; identifier les commandes d’événements, les confirmations et les opérations qui nécessitent une adaptation.
2. Définir les métadonnées d’arguments et extraire les appels métier nécessaires à l’exécution partagée.
3. Ajouter les tables et contraintes SQL ainsi que les fonctions de gestion des macros.
4. Implémenter l’assistant interactif de création et l’autocomplétion des noms en slash.
5. Ajouter l’exécuteur séquentiel, les contrôles d’accès et les réponses d’erreur.
6. Ajouter les limites atomiques par joueur et brancher les commandes slash et préfixées sur les mêmes services.
