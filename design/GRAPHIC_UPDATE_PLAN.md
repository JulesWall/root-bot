# Root OS — Plan d’implémentation de la refonte graphique

Date : 1er octobre 2026. Version 3 — Quatre vues, infrastructure fusionnée avec l’accueil, détail ATK/DEF dans Opérations et illustration dans les quatre vues. Spécification de transmission à un autre développeur ou agent. Aucun changement du bot réalisé.

Ce document est autonome : son destinataire ne doit pas avoir besoin de la conversation pour implémenter. Les sections 1 à 12 exposent le cadrage ; les sections 13 à 23 donnent les décisions de référence, les contrats de données, le détail des écrans, les interventions par fichier et la recette. En cas d’ambiguïté entre une formulation générale et une prescription détaillée, appliquer la prescription détaillée. Les noms de futurs modules et méthodes sont des contrats proposés, pas des symboles déjà existants dans le dépôt.

Parcours de lecture pour l’implémenteur : section 13 pour le scope et les décisions ; sections 14–15 pour la charte et les ressources ; sections 16–18 pour les vues, données et interactions ; sections 19–20 pour chaque commande et fichier ; sections 21–23 pour la recette et la livraison. Les sections 1–12 servent de synthèse et de justification, pas de raccourci permettant d’omettre les prescriptions détaillées.

## 1. Objectif et décisions acquises

Refondre tous les affichages destinés aux joueurs pour obtenir une identité Root OS immédiatement reconnaissable : esthétique soignée, lecture claire, immersion et cohérence totale. Les documents de conception et les ressources du dossier `design/` fournissent l’identité visuelle ; les règles du code actuel fournissent le fonctionnement du jeu.

- Le PVP actuel conserve exactement ses règles, coûts, délais, probabilités, restrictions, destructions, captures, représailles, notifications et modalités de publication.
- Les niveaux de firewall deviennent, dans toute l’interface, des niveaux d’infrastructure. Les effets restent identiques, y compris défense, accès au matériel et multiplicateurs de récompenses.
- Les six illustrations sont réservées à `/network` et ses vues. Aucun autre écran de jeu ne reçoit de bannière ou d’illustration décorative. Les pictogrammes sont utilisés dans toute l’interface.
- `/network` devient un poste de commande navigable dans le même message. Les commandes directes et leurs équivalents à préfixe restent disponibles.
- Les quatre vues sont **Accueil, Ferme, Matériel et Opérations**. L’Accueil contient aussi toute la présentation de l’infrastructure et son amélioration ; aucune cinquième vue Infrastructure. Opérations détaille les modules d’attaque et de défense par tier, comme Ferme détaille les mineurs.
- L’illustration du niveau d’infrastructure courant est affichée sur chacune des quatre vues, y compris lors de leur pagination. Elle reste réservée à `/network`.
- Les emojis sont déjà importés dans Discord. Pour les cinq noms qui possèdent une version animée, utiliser les versions animées existantes.
- Aucun nom personnalisé de poste ou de ferme. L’identité du panneau utilise le nom d’affichage Discord du joueur.
- `embed.md` est perdu : reconstruire une spécification autonome à partir des ressources disponibles.
- Proposition : couvrir français et anglais ensemble, les deux langues déjà présentes dans le bot. Aucun écran ne doit rester partiellement traduit.

Les mentions de logiciels signés, vulnérabilités, patchs, rançons, siphonnage et marché logiciel dans les anciens documents PVP V2 ne font pas partie de cette mise à jour. Le plan ne prévoit aucun nouveau journal persistant.

## 2. Ce que l’inventaire du code révèle

L’interface possède plusieurs chemins de rendu indépendants :

- `utils/root_embed.py` : base commune existante, mais palette très dispersée selon les commandes et footer français fixe « Système sécurisé » qui ne décrit pas toujours l’état réel.
- `commands/game/network.py` : embed spécifique très long, regroupant économie, protection, identifiant, stock ATK, tâches, représailles et matériel ; seulement Récolter et Actualiser comme actions principales.
- `commands/game/buy.py` : boutique avec rendus et navigation propres.
- `commands/game/commandgame.py` et `main.py` : erreurs souvent envoyées en texte brut, hors de la présentation commune.
- `utils/confirmation.py` : fin de certaines confirmations par remplacement de l’embed avec du texte brut ; les états successifs perdent leur continuité visuelle.
- `utils/trade_view.py`, `commands/game/scan.py`, `commands/game/hack.py` : interactions et notifications spécifiques, dont des communications sensibles déjà encadrées par le jeu.
- `commands/game/upgrade.py`, `claim.py`, `rmd.py`, `contract.py`, `compile.py` : notifications différées à couvrir aussi.
- `commands/game/minigame_cog.py`, `game_config.py`, `game/challenge_tracker.py` : affichage des défis, tentatives, victoires et remplacement des anciens panneaux.
- `utils/logger.py` : annonces publiques et messages blockchain visibles aux joueurs, en plus des journaux internes.
- `commands/utility/`, `lang/help_fr.py`, `lang/help_en.py`, `lang/descslash.py`, `utils/presence_manager.py` : aide, onboarding, commandes utilitaires, descriptions Discord et présence du bot.

Conséquence : changer uniquement `RootEmbed` ne suffit pas. La refonte doit suivre une matrice de tous les messages, de leur audience et de leurs états successifs.

## 3. Direction artistique et règles de présentation

### Identité

Un poste de contrôle informatique tangible, sobre et chaleureux, cohérent avec les six scènes en pixel art. L’interface parle comme un système utile : elle annonce le résultat, explique les chiffres et propose une prochaine action. L’immersion vient de termes précis — infrastructure, ferme, mémoire, compilation, opération, rapport — et des visuels ; elle ne doit pas masquer les règles derrière du jargon.

### Palette

- Turquoise `#54E2D1` : consultation et fonctionnement normal.
- Ambre `#FFC15A` : attention requise, mémoire pleine, action indisponible ou échéance expirée.
- Blanc `#EEF1F5` : pictogrammes d’action et neutralité, tel que défini dans le pack.
- Rouge `#F06A6A` réservé aux échecs bloquants et conséquences critiques. Cette nuance est la valeur de référence proposée pour les nouveaux embeds ; la validation visuelle peut ajuster le contraste sans changer sa signification.

La couleur indique d’abord un état, plutôt qu’une couleur arbitraire pour chaque commande. Les boutons utilisent les styles natifs Discord ; leur couleur ne peut pas être librement recolorée. Chaque état conserve un libellé explicite, indépendamment de sa couleur.

### Grammaire commune

1. Identité : `ROOT OS · Rubrique` et joueur/cible seulement si utile.
2. Résultat ou état : une phrase lisible immédiatement.
3. Données clés : petit nombre de lignes, unités et libellés stables.
4. Détail secondaire : champs supplémentaires uniquement si nécessaires.
5. Actions : verbes concrets et position constante.
6. Footer : `ROOT OS · Rubrique`, sans affirmation automatique de sécurité ni identifiant technique inutile.

Les messages de succès, d’erreur et de notification doivent être aussi soignés que les grands écrans. Favoriser un petit embed pour les réponses ponctuelles ; conserver du texte simple uniquement si le contexte le justifie, avec les mêmes conventions rédactionnelles.

### Lisibilité

- Champs verticaux pour les données essentielles ; deux colonnes seulement pour de petits blocs testés sur mobile.
- Pas de tableaux ASCII larges, de séparateurs répétés, de cascade de citations `>` ou de majuscules sur toutes les lignes.
- Un pictogramme par section ou action suffit. Pas de duplication emoji dans le libellé et dans la propriété du bouton.
- Conserver les blocs monospace nécessaires aux puzzles, séquences et codes. Ne jamais reformater une donnée qui modifie un défi.
- USD, RTM, H/s, bits/s, ATK, DEF : terminologie constante. Réutiliser les précisions monétaires actuelles ; les vues détaillées conservent les valeurs exactes si un résumé utilise une unité abrégée.
- Production affichée principalement en RTM/h, si la conversion est une présentation exacte du débit actuel. Mémoire : pourcentage et quantité utilisée/capacité, avec les unités effectivement utilisées par le calcul actuel.
- Horaires de fin avec timestamps Discord ; les messages indiquent clairement qu’il s’agit d’une photographie actualisable.
- Les noms Discord et textes libres ne doivent pas casser la mise en page ou déclencher de mentions supplémentaires.

## 4. Trois propositions pour `/network`

### A — Poste de commande avec accueil et vues spécialisées — recommandée

Accueil structuré : joueur, type et niveau d’infrastructure, défense, accès et bonus, identifiant secret, amélioration suivante/en cours, état du minage, quantité à récolter, mémoire, soldes, réputation et synthèse des tâches. Illustration correspondant au niveau actuel dans le panneau.

Navigation par menu : **Accueil · Ferme · Matériel · Opérations**. Deux actions rapides stables : **Récolter · Actualiser**. L’amélioration de l’infrastructure est accessible depuis l’Accueil. Les vues secondaires détaillent les équipements et opérations ; chacune conserve l’illustration.

Avantages : meilleur équilibre entre immersion, lecture mobile et accès rapide ; le tableau matériel et les informations PVP restent accessibles en un choix. La profondeur augmente avec le compte sans dégrader l’écran principal.

### B — Terminal compact à onglets

Même découpage en quatre vues, mais quatre boutons de navigation visibles : **Accueil · Ferme · Matériel · Opérations**. L’infrastructure reste intégrée à l’Accueil. Récolter et Actualiser sur une deuxième ligne.

Avantages : toutes les rubriques sont visibles sans ouvrir un menu. Limite : plus de boutons, libellés plus contraints, davantage d’encombrement sur mobile. À retenir si la visibilité immédiate des onglets prime.

### C — Rapport unique avec détails dépliés par remplacement du panneau

Un accueil plus dense, avec **Détails ferme**, **Détails matériel**, **Détails opérations**, puis retour à l’accueil. L’infrastructure reste intégrée à l’Accueil. Seuls les détails sollicités remplacent le contenu principal et chaque vue conserve l’image.

Avantages : proche des habitudes actuelles, transition simple. Limite : moins de structure à long terme et écran initial plus chargé. Cette variante répond moins bien à l’objectif d’une refonte globale.

**Base de référence à implémenter : A, avec quatre vues.** B et C sont des alternatives de contrôle documentées, pas des branches à développer simultanément. L’illustration du niveau courant est obligatoire dans les quatre vues, sur demande explicite du commanditaire. Une même illustration accompagne leurs différents contenus ; ne pas la retirer des détails au nom de la compacité. Aucun dessin dynamique de la ferme ni variante visuelle d’intrusion à créer.

## 5. Contenu des vues de la proposition A

### Accueil

- En-tête : `ROOT OS · Réseau de {nom Discord}`.
- Sous-titre : `{type} · Infrastructure {niveau}/5`.
- Infrastructure intégrée à cet accueil : défense infrastructure/modules/total, accès et bonus, identifiant secret et prochaine rotation, amélioration suivante ou en cours. Le bouton Améliorer ouvre le devis actuel, puis sa confirmation.
- État : production active, mémoire pleine ou absence de matériel de minage. Ne pas afficher un diagnostic global « réseau sécurisé ».
- Récolte : montant disponible et mémoire utilisée/capacité.
- Ferme : puissance et production réelle, bonus pris en compte.
- Ressources : soldes USD/RTM et réputation.
- Tâches : amélioration, compilation et scan actifs, avec échéances ; résumé des attaques lancées seulement si les données autorisées sont ajoutées au résultat de consultation.
- Illustration du niveau ; footer discret d’actualisation.

Exemple de contenu, sans chiffres inventés :

> ROOT OS · Réseau de Nox  
> Serveur dédié · Infrastructure 3/5  
> Production active  
> À récolter : {RTM disponibles}  
> Mémoire : {utilisée} / {capacité} · {pourcentage}  
> Ferme : {H/s} · {RTM/h}  
> Ressources : {USD} · {RTM en portefeuille}  
> En cours : {tâche et échéance}

### Ferme

Quantités de mineurs regroupées par tier, puissance par tier, total, mémoire, temps avant saturation, montant récoltable, bonus de réputation, autoclaim et Combo Saver. Pas de création d’emplacements et pas de limite de quantité.

### Matériel

Minage, attaque et défense regroupés par tier ; unités distinctes H/s, bits/s et DEF. Les équipements possédés restent visibles même si leur tier n’est pas achetable au niveau actuel, notamment après une capture PVP. Accès à la boutique : parcours des catégories et devis actuels, via les mêmes validations métier. Le bouton ne doit pas acheter directement un module.

### Opérations

Stock ATK, capacité de compilation, **modules d’attaque par tier et modules de défense par tier**, compilation en cours, scan en cours, attaques lancées consultables et droits de représailles. Les modules d’attaque indiquent quantité et bits/s agrégés ; les modules de défense indiquent quantité et DEF agrégés, suivis de leurs totaux respectifs. Ce détail reprend la logique de présentation par tier de Ferme, avec les unités propres au PVP. Les scans et attaques disponibles passent par un choix explicite de cible et les devis actuels. Les règles d’identification, de publication et de visibilité restent celles du code actuel.

Ne pas ajouter un écran « Logiciels » ou « Connexions » qui implique des systèmes abandonnés. Ne pas promettre un Journal historique : les tâches actuelles et les droits de représailles ne constituent pas un historique de toutes les actions.

### Infrastructure intégrée à l’Accueil — aucune vue séparée

Dans l’Accueil, afficher niveau, type, défense fournie par l’infrastructure, défense des modules et total clairement séparés. Afficher les accès et multiplicateurs actuels, puis l’amélioration suivante : niveau et type attendus, ou amélioration en cours avec son échéance. Le coût, le délai et les gains complets figurent dans le devis ouvert par Améliorer, calculés depuis les règles existantes. Améliorer ouvre ce devis, puis une confirmation.

L’identifiant secret et sa prochaine rotation restent disponibles ici, avec la visibilité et les protections de présentation actuelles. Ne pas introduire un nouvel écran public contenant des résultats de scan privés.

### Comportement des interactions

- Navigation et actualisation modifient le même message ; une commande directe ouvre son propre message comme aujourd’hui.
- Changement de vue : charger les données courantes par le service, puis rendre la vue sélectionnée.
- Récolter : utiliser exactement l’action métier et les journaux actuels ; ensuite actualiser le panneau et afficher un retour de résultat court.
- Échanges, scans et attaques : conserver les destinataires et confirmations actuels. Un clic dans le poste de commande ne change jamais les règles du PVP.
- Réserver les contrôles au joueur propriétaire, avec les exceptions déjà prévues pour les échanges.
- Protéger les actions contre les doubles clics et revalider les devis anciens.
- À expiration, désactiver les contrôles et afficher `Session expirée · Rouvre /network` dans la langue du joueur. Conserver la durée actuelle de la vue au premier passage ; ne pas promettre de boutons permanents.
- Aucun rafraîchissement toutes les secondes : actualisation au clic et timestamps relatifs. Un panneau supprimé ou fermé se retrouve avec `/network`.
- La position de l’illustration dépend du rendu natif Discord. Pour un embed classique, éviter de promettre une bannière en tête ; vérifier le résultat réel pendant le prototype.

## 6. Remplacement du terme firewall

Correspondance fixe :

- Niveau 0 : Smartphone bricolé / Improvised smartphone.
- Niveau 1 : PC assemblé / Assembled PC.
- Niveau 2 : Station de travail / Workstation.
- Niveau 3 : Serveur dédié / Dedicated server.
- Niveau 4 : Salle des serveurs / Server room.
- Niveau 5 : Datacenter / Data center.

Lexique : `Niveau d’infrastructure`, `Défense de l’infrastructure`, `Amélioration de l’infrastructure`, `Infrastructure requise`, `Bonus d’infrastructure`. Exemple : `Cette action nécessite une infrastructure de niveau 2 minimum.`

Le niveau 0 conserve exactement son statut PVP actuel. Une amélioration en cours affiche le type actuel et le type cible, mais l’illustration et les effets ne changent qu’à la livraison effective.

**Choix technique recommandé : remplacement dans la présentation, sans migration de données.** Conserver provisoirement les champs internes `firewall_level`, clés de règles, codes d’erreur et identifiants techniques existants. Un catalogue de présentation unique associe niveau, nom traduit et illustration. Cela évite de toucher aux calculs et aux comptes pour une refonte visuelle.

Le fichier et l’emoji importé `root_firewall` peuvent rester dans les ressources historiques, mais ne sont pas utilisés dans les nouveaux affichages : leur nom peut réapparaître dans une infobulle Discord. Employer `root_connexions` pour l’infrastructure et `root_materiel` pour les modules de défense. Aucun texte visible ne doit réintroduire « firewall », « pare-feu » ou « parefeu ».

Le lexique doit être corrigé dans les embeds, devis, MP, prérequis de boutique, bannières de récompense, aide, descriptions de commandes, annonces publiques et états d’expiration. Les messages historiques déjà envoyés ne sont pas réécrits en masse.

## 7. Couverture de tous les messages joueurs

### Économie et progression

`buy`, `upgrade`, `claim`, `hourly`, `convert`, `trade`, `rep`, `top`, `attest`, `contract` : consultation, devis, validation, refus, annulation, expiration, fonds insuffisants et livraison. Les confirmations reprennent le coût et l’effet essentiels ; les réussites indiquent le résultat effectif. Les classements séparent rang, joueur et valeur sans tableau monospace large.

### PVP

`compile`, `scan`, `hack` : préparation, estimation, confirmation, attente, réussite, échec, rapport à l’attaquant, rapport à la victime, exposition publique et représailles. Même structure de rapport, vocabulaire et unités, mais contenu adapté à ce que le destinataire a réellement le droit de connaître. Une estimation de devis ne devient pas une garantie de réussite.

### Événements et mini-jeux

`event`, `hash`, `pin`, `decode`, `anomaly`, `buffer`, `signal`, `packet` : écran d’événement, consigne, état actif, récompense, entrée invalide, mauvaise réponse, cooldown, victoire et panneau devenu obsolète. Conserver les contenus exacts des énigmes et rendre les succès et expirations avec la même charte que l’écran initial.

### Notifications et interactions transversales

Rappels `rmd`, mémoire pleine, autoclaim, Combo Saver, livraisons d’amélioration/compilation/scan/contrat, invitations et conclusions d’échange. Réutiliser le rendu dans les MP et les replis en salon, tout en conservant les règles de mention et de destination propres à chaque notification.

### Utilitaires et découverte

Bienvenue et choix de langue, aide, `language`, `prefix`, `ping`, `invite`, `botinfo`, messages d’usage, permissions, commandes inconnues et erreurs globales. Conserver la précision des aides et adapter les exemples au préfixe réel. Le choix de langue doit conduire à une introduction dans la langue sélectionnée.

### Sorties publiques et présence

Annonces de victoire, activité publique PVP, messages blockchain visibles, sanctions ou réponses administratives visibles par un joueur, activité affichée dans le profil du bot. Les outils de modération et rapports strictement internes restent hors du travail graphique prioritaire, sauf s’ils produisent une sortie visible aux joueurs.

L’audit de couverture relève chaque point `send`, `respond`, `edit`, `followup` et chaque DM, avec audience, langue, template et cas d’expiration. Aucun chemin secondaire n’est considéré comme couvert uniquement parce que sa commande principale utilise `RootEmbed`.

## 8. Architecture de présentation proposée

Faire évoluer les composants actuels plutôt que créer une deuxième interface parallèle :

- `utils/root_embed.py` : charte par état, gabarits de panneau/devis/résultat/alerte/notification, identité et footer traduits ; compatibilité transitoire avec les commandes non encore converties.
- Nouveau module de présentation à nommer, par exemple `utils/root_theme.py` : palette et conventions communes.
- Nouveau catalogue `utils/infrastructure_display.py` : noms FR/EN et choix d’illustration des six niveaux ; uniquement de la présentation.
- Nouveau registre `utils/root_emojis.py` : résolution centralisée des emojis importés, prenant en charge les identifiants et le flag animé. Trouver les IDs via le bot connecté pendant l’implémentation ou les renseigner dans une configuration explicite. Ne pas inventer d’IDs et ne pas dépendre d’une simple chaîne `:root_scan:`.
- `utils/ui_components.py`, `confirmation.py`, `trade_view.py` : boutons et états terminaux cohérents ; maintien des contrôles et transactions existants.
- `commands/game/network.py` : contrôleur des vues du poste de commande, rendu séparé par rubrique et conservation de la référence du message.
- `commands/game/commandgame.py` et `main.py` : erreurs et réponses transversales sur la charte commune.
- `lang/` : textes et labels, suppression des emojis/ponctuations décoratives dupliqués et traduction complète.
- `utils/text.py` et `utils/time_format.py` : formateurs uniques, conservant les précisions et unités requises.

Les renderers utilisent les résultats du service. Ils ne doivent pas recalculer une récompense, le succès d’un scan ou une résolution d’attaque. Attention : consulter `network` matérialise déjà le minage et peut créer le compte ; ne pas réimplémenter cela dans une vue graphique.

`Player.network` fournit déjà amélioration, compilation, scan et représailles. Les attaques PVP lancées sont accessibles via `PvpDB.get_active_for_attacker`, mais absentes du résultat réseau inspecté : si elles sont affichées, ajouter une lecture autorisée au service sans changer leur cycle de vie. Ne pas révéler des attaques entrantes que l’interface actuelle ne communique pas.

Les PNG existants restent les sources. Prévoir des copies de diffusion optimisées seulement si le prototype l’exige ; charger une illustration unique correspondant au niveau, sans appel ImageGen ni envoi des six fichiers à chaque interaction. Livraison possible par pièce jointe Discord, puis conservation correcte de la pièce jointe lors des éditions. Tester en salon et après navigation.

## 9. Lots d’implémentation et ordre conseillé

### Lot 0 — Spécification et inventaire exhaustif

Livrables : matrice des messages et états, lexique FR/EN, association des emojis, choix A/B/C, captures de référence actuelles, checklist des mécaniques à préserver. Relever les destinations publiques/privées réelles. Marquer les anciens documents PVP V2 comme hors périmètre de cette mise à jour dans la nouvelle documentation, sans les supprimer.

### Lot 1 — Charte et prototypes représentatifs

Prototyper Accueil network, Matériel, devis upgrade, devis achat, erreur fonds insuffisants, résultat claim, rapport PVP, mini-jeu actif/victoire et MP de livraison. Avec et sans données abondantes, en FR et EN. Vérifier l’apparence réelle sur Discord desktop/mobile et en thème clair/sombre. Fixer la charte avant de convertir toutes les commandes.

Critère de sortie : les prototypes illustrent les quatre priorités et sont réalisables avec les composants du projet ; la navigation recommandée est choisie.

### Lot 2 — Fondations communes

Implémenter thème, emojis, catalogue des infrastructures, templates, formatage et boutons communs. Adapter les erreurs globales et les confirmations. Définir un rendu utilisable quand un emoji n’est plus disponible. Intégrer les nouvelles fondations de façon progressive, en conservant les appels existants jusqu’à leur conversion.

Critère de sortie : toutes les catégories de messages partagent un vocabulaire et des états visuels définis.

### Lot 3 — Infrastructure et nouveau `/network`

Appliquer la correspondance des six niveaux. Créer l’accueil fusionné avec l’infrastructure et les trois vues secondaires Ferme, Matériel et Opérations, avec l’illustration sur les quatre vues, navigation, Récolter, Actualiser et accès aux devis. Opérations reçoit les détails ATK/DEF par tier. Ajouter uniquement les lectures de données nécessaires aux détails. Vérifier compte neuf, niveaux 0 à 5, upgrade en cours, mémoire pleine, compte sans mineurs et matériel capturé.

Critère de sortie : toutes les informations utiles de l’ancien network sont accessibles, sans doubler les totaux ni surcharger l’accueil.

### Lot 4 — Économie, progression et contrats

Convertir boutique, achat, upgrade, récolte, hourly, conversion, échanges, réputation, attestations, top et contrats. Harmoniser tous les états et notifications associés. L’amélioration parle exclusivement d’infrastructure.

### Lot 5 — PVP actuel

Convertir compilation, scans, attaques, exposition et rapports privés/publics. Conserver chaque étape, destinataire et règle. Comparer sur les mêmes scénarios les données affichées avant/après ; les nouvelles présentations ne dévoilent pas de renseignement supplémentaire.

### Lot 6 — Mini-jeux, événements, rappels et utilitaires

Convertir les sept mini-jeux et leurs anciens messages après victoire ; harmoniser events et multiplicateurs d’infrastructure. Convertir rmd, onboarding, aide, descriptions slash, utilitaires, sorties publiques et présence. Contrôler les textes des notifications différées séparément.

### Lot 7 — Recette globale et préparation de livraison

Audit des anciens termes et rendus non convertis ; vérification des langues ; tests fonctionnels ciblés puis suite existante ; revue visuelle de tous les gabarits ; vérification des ressources Discord en production. Ajouter l’annonce finale destinée aux joueurs dans `CHANGELOG.md` seulement lors de l’implémentation terminée.

Migration SQL prévue : aucune avec l’approche recommandée. Si une décision ultérieure impose un changement de base, inscrire les commandes dans `migration.sql`, conformément aux instructions du projet. Ne pas créer une migration cosmétique pour cette refonte.

## 10. Critères d’acceptation

### Esthétique et cohérence

- Tout message joueur appartient à une famille de rendu définie, avec identité, hiérarchie et état cohérents.
- L’illustration est présente dans les quatre vues de `/network`, y compris leurs pages ; le niveau de l’image correspond au niveau effectivement livré. Aucun autre écran n’en reçoit.
- Les versions animées importées sont correctement résolues ; absence d’emoji brut non reconnu ou de doublons décoratifs.
- Aucune mention de firewall/pare-feu dans les nouveaux affichages, aides ou descriptions joueurs FR/EN.
- Les réponses ponctuelles sont courtes et soignées ; les longues listes se paginent ou se consultent dans une vue de détail.

### Lisibilité et exactitude

- Montants, bonus, mémoire, débits et échéances correspondent aux valeurs métier réelles.
- Les abréviations ne font pas disparaître des valeurs nécessaires à une décision ; les unités de mémoire correspondent au système actuel.
- Les tiers possédés au-delà de l’accès à l’achat restent visibles.
- FR et EN présentent les mêmes informations ; noms longs et grands stocks ne cassent pas les limites Discord.
- Les défis restent exactement jouables : espaces, lignes, codes et grilles utiles sont préservés.

### Interactions et confidentialité actuelle

- Accueil → chacune des vues → Accueil fonctionne dans le même message.
- Clic non autorisé, double clic, devis périmé, expiration, message supprimé et changement d’état sont traités proprement.
- Les confirmations restent nécessaires là où elles existent. Aucune transaction n’est déclenchée par une simple consultation.
- Les résultats privés, identifiants scannés, anonymat des scans et exposition volontaire conservent leurs modalités actuelles.
- Les mentions et replis de MP ont le comportement actuel, sans nouveaux pings.

### Non-régression du jeu

- Tests existants des achats, upgrades, minage, mémoire, récompenses, autoclaim, réputation, contrats, scan, compile et hack maintenus.
- Aucun changement de `data/math.json` pour obtenir un rendu plus joli.
- Résultats PVP, coûts, délais, droits de représailles et soldes identiques pour des scénarios comparables.
- Les tests d’interface qui figent les anciens emojis doivent être adaptés ; ils ne justifient aucun changement des tests métier.
- Aucun benchmark ou déploiement n’a été exécuté dans cette phase de planification.

## 11. Vérification technique et limites de cette phase

Le projet déclare `py-cord==2.8.1`. La base recommandée est celle déjà utilisée : embeds classiques et vues interactives. La réussite esthétique ne dépend pas d’une migration vers Components V2. Si une contrainte de placement d’image impose une autre approche, la décider après un prototype concret et une vérification de compatibilité.

Contraintes officielles à intégrer aux validations : titre d’embed 256 caractères, description 4 096, 25 champs, 1 024 caractères par valeur de champ, total 6 000 caractères sur les embeds du message ; libellé de bouton 80 caractères maximum. Préférer des budgets de contenu nettement inférieurs pour le confort de lecture. Sources : [Discord — Message et embeds](https://docs.discord.com/developers/resources/message#embed-object) ; [Discord — Composants et boutons](https://docs.discord.com/developers/components/reference#button).

L’inventaire présenté repose sur la lecture du dépôt et des ressources graphiques. Les identifiants des emojis importés, leur disponibilité réelle pour le bot et le rendu sur les clients Discord seront vérifiés lors de l’implémentation ; aucun accès à Discord ni test d’intégration n’a été effectué ici.

## 12. Proposition finale

Retenir le poste de commande A, la palette Root OS par état, une illustration de niveau dans `/network`, des réponses sans grandes images partout ailleurs, et un remplacement intégral du vocabulaire firewall dans l’interface. Construire d’abord les prototypes et le système de présentation commun, puis convertir les familles de messages jusqu’aux MP, aux erreurs et aux messages obsolètes.

Le résultat attendu est un seul langage visuel à travers le bot, avec la profondeur du jeu actuel accessible progressivement depuis `/network`.

## 13. Instructions de transmission et autorité des décisions

### 13.1 Ce que le commanditaire a explicitement demandé

Le commanditaire demande une grosse mise à jour graphique, et non le développement de la proposition PVP V2. Il demande davantage d’esthétique, de clarté, d’immersion et une cohérence totale entre tous les messages destinés aux joueurs. Il autorise la réorganisation des textes, de la présentation et des interactions pour atteindre ces priorités. Il confirme le principe d’un poste de commande `/network`, les infrastructures du dossier `design/`, la conservation exacte des effets actuels et l’abandon du mot firewall dans l’interface. Il refuse les noms personnalisés de ferme/poste. Il précise que les emojis sont importés et que les versions animées sont celles à utiliser pour les noms concernés.

Correction explicite de la version 3 : il demande quatre vues au total, l’ancienne vue Infrastructure fusionnée avec Accueil, le détail des modules ATK et DEF dans Opérations comme le détail des mineurs dans Ferme, et l’image dans chacune des quatre vues. Ces décisions remplacent la proposition antérieure de cinq vues avec image limitée à l’Accueil.

Cette phase livre exclusivement le plan. L’autorisation d’écrire ce document ne constitue pas un ordre d’implémenter immédiatement le bot.

### 13.2 Choix de conception proposés par ce document

Les choix suivants rendent le plan exécutable sans improvisation. Ils sont des recommandations du concepteur, pas des validations explicites distinctes du commanditaire :

- Navigation A par menu, pour les quatre vues demandées, avec deux actions rapides.
- Illustration sur chacune des quatre vues de `/network` conformément à la demande ; aucun grand visuel sur les autres commandes.
- Conversion des réponses joueurs en embeds compacts, sauf exceptions définies ci-dessous.
- Palette turquoise/ambre/rouge par état, sans une couleur différente par commande.
- Couverture des deux langues existantes FR/EN dans le même chantier.
- Conservation du stockage et des identifiants internes historiques ; pas de renommage SQL.
- Accès aux devis depuis le poste de commande, avec des messages d’action distincts du panneau principal.

Utiliser ces choix comme base de référence. Ne développer B et C que si le commanditaire choisit ensuite explicitement une autre organisation. Si un arbitrage change, mettre à jour ce document avant de développer les parcours touchés.

### 13.3 Définition de « fonctionnement identique »

Le rendu peut changer, pas les transitions métier. Garder notamment : les paramètres des commandes et alias actuels, leur validation, les restrictions de compte/niveau/maintenance, les règles de calcul, le moment des prélèvements, les montants, les arrondis transactionnels, le règlement différé, les limites de simultanéité, les mises à jour de mémoire, les récompenses, les seuils de scan, la sélection des victimes et les droits de représailles.

Ne pas utiliser une docstring ou un exemple de conception comme source de vérité d’un nombre. Certains commentaires et textes peuvent être anciens. Le résultat du service, les fonctions métier actuellement appelées et `data/math.json` définissent le comportement à préserver.

Une différence de contenu autorisée : remplacer « Pare-feu 3 » par « Serveur dédié · Infrastructure 3 » et afficher le même nombre de DEF. Une différence interdite : retirer les modules ATK/DEF, changer leur prix, modifier une probabilité de scan ou rendre l’infrastructure destructible.

## 14. Spécification des ressources graphiques et des emojis

### 14.1 Catalogue des illustrations

Créer une association unique entre niveau et fichier, relative à la racine du projet :

- `0` → `design/infrastructures-controle/niveau-0-smartphone.png`.
- `1` → `design/infrastructures-controle/niveau-1-pc-assemble.png`.
- `2` → `design/infrastructures-controle/niveau-2-station-de-travail.png`.
- `3` → `design/infrastructures-controle/niveau-3-serveur-dedie.png`.
- `4` → `design/infrastructures-controle/niveau-4-salle-des-serveurs.png`.
- `5` → `design/infrastructures-controle/niveau-5-datacenter.png`.

Les six scènes ont déjà été produites. Préserver les fichiers sources, leur cadrage panoramique, leur continuité et la lampe rouge. Ne pas remplacer une illustration de niveau par `design/root-os-banner.png` : cette dernière est une ancienne ressource générale, pas la représentation d’un niveau.

Pour la première version, envoyer le PNG du seul niveau affiché. Si une optimisation est nécessaire pour la vitesse ou le poids, créer des copies de diffusion reproductibles avec les mêmes cadrages, sans recadrage ni nouveaux dessins. Vérifier que le smartphone du niveau 0 reste identifiable à la largeur mobile. Une image n’est jamais utilisée pour contenir des statistiques : les valeurs restent du texte Discord lisible et à jour.

La gestion des pièces jointes doit respecter ce scénario : envoi d’Accueil avec une image → passage à Ferme avec la même image → passage à Matériel puis Opérations, toujours avec la même image → pagination d’Opérations avec image conservée → retour à Accueil avec image conservée → livraison d’un upgrade → Actualiser depuis n’importe laquelle des quatre vues avec l’image du nouveau niveau. Conserver la pièce jointe existante lors des changements de vue et de page ; si le niveau change, remplacer la référence et l’asset proprement. Empêcher doublons visibles, pièces jointes multiples inutiles et URLs cassées. Aucune illustration n’est jointe aux MP ni aux devis séparés.

Si le PNG du niveau est absent ou illisible, l’interface textuelle doit continuer à fonctionner. Journaliser l’erreur technique ; ne pas montrer un lien local, une erreur de chemin ou une image d’un autre niveau au joueur. Ce défaut doit néanmoins empêcher de déclarer la recette graphique terminée.

### 14.2 Registre d’emojis : résolution

Centraliser la résolution, ne pas écrire des IDs Discord en dur dans chaque commande. Le registre conserve, pour chaque nom, l’identifiant Discord réel et le caractère animé réel. Le bot peut résoudre ces valeurs dans sa liste d’emojis accessibles ou dans une configuration explicite. En cas de deux emojis du même nom, prendre l’ID explicitement configuré ; ne pas sélectionner arbitrairement le premier.

Les noms animés obligatoires sont `root_terminal`, `root_recolter`, `root_scan`, `root_retour`, `root_alerte`. Leur forme texte utilise la notation animée Discord ; les boutons utilisent un objet emoji avec le flag animé. Les autres noms utilisent leur version statique. Ne pas inventer de nouvel ID ni importer un pack une seconde fois.

Résoudre les emojis une fois au chargement, puis réutiliser les objets. Ne pas appeler Discord pour chaque ligne de message. Si un emoji devient inaccessible, le libellé seul constitue le repli : mieux vaut un bouton « Récolter » sans icône qu’une chaîne `<a:...>` ou `:root_recolter:` non rendue.

### 14.3 Affectation sémantique de référence

- `root_terminal` animé : identité de l’Accueil network et, si nécessaire, identité d’un panneau système. Un seul dans l’en-tête ; ne pas le répéter dans chaque champ.
- `root_ferme` : Ferme, mineurs, catalogue Minage.
- `root_puissance` : puissance de compilation et modules d’attaque. Le texte dit toujours « bits/s » ou « ATK » pour distinguer capacité et stock.
- `root_production` : production en RTM/h et résultats économiques.
- `root_memoire` : mémoire utilisée/capacité et réserve récoltable, dans des sections distinctement nommées.
- `root_temps` : échéances, délais et tâche en cours.
- `root_recolter` animé : bouton Récolter et notification de récolte.
- `root_materiel` : Matériel, achats, modules et contribution de défense des modules.
- `root_connexions` : Infrastructure et défense de l’infrastructure ; ne pas en déduire un écran de « connexions » PVP V2.
- `root_operations` : liste des compilations, scans, attaques et représailles.
- `root_bilan` : résumé de transaction, classement, résultat d’opération et contrat.
- `root_alerte` animé : erreur/alerte réelle, mémoire pleine ou dommage. Ne pas l’afficher sur un état normal.
- `root_scan` animé : devis et action de scan actuels, aide au scan.
- `root_retour` animé : bouton Retour uniquement.
- `root_journal` : aide et notification textuelle si le pictogramme convient ; il ne crée pas une rubrique historique absente.
- `root_logiciels` : peut rester inutilisé. Ne pas ajouter un faux catalogue logiciel pour utiliser tous les assets.
- `root_firewall` : asset historique non utilisé dans les nouveaux messages joueurs.

Ne pas chercher à utiliser tous les emojis dans chaque message. Les mini-jeux peuvent partager les pictogrammes terminal/scan/alerte/bilan ; leur titre et leur contenu exact les identifient. Conserver les drapeaux du choix de langue si c’est plus clair que les pictogrammes Root OS.

## 15. Contrat de rendu commun à toutes les commandes

### 15.1 États visuels

Définir une liste explicite d’états de présentation : consultation, devis, en cours, réussi, attention, échec critique, annulé, expiré. Ces états décrivent le rendu ; ils ne sont pas de nouveaux statuts enregistrés en base.

- Consultation, devis exécutable, en cours et réussite : turquoise. Une réussite porte un texte explicite, par exemple « Récolte effectuée », sans couleur verte supplémentaire obligatoire.
- Attention : ambre. Cela couvre fonds insuffisants, infrastructure insuffisante, cooldown, mémoire pleine, mauvais résultat d’un défi et scan sans succès.
- Échec critique : rouge. Réserver cet état à une erreur technique bloquante, une exposition publique volontaire ou un rapport de dommage subi ; un devis offensif n’est pas rouge par simple appartenance au PVP.
- Annulé : couleur normale turquoise avec « Action annulée », sans alarme.
- Expiré : ambre avec « Devis expiré » ou « Session expirée » et une indication précise pour reprendre.

Un rapport de victime est rouge s’il comporte une perte réelle, même si l’intrusion n’a pas atteint la zone ciblée. Un rapport repoussé sans dommage peut rester turquoise. Ne pas réduire le rapport à un unique booléen « gagné/perdu » qui masque les conséquences partielles.

### 15.2 Structure des gabarits

**Panneau de consultation** : titre `ROOT OS · {rubrique}` ; contexte en une ou deux lignes ; sections de données ; controls ; footer de contexte/actualisation. Illustration obligatoire pour les quatre vues network, absente des autres panneaux de consultation.

**Devis** : titre `ROOT OS · {action}` ; phrase « Vérifie le coût et l’effet avant de confirmer » ; bloc Objet/cible ; bloc Coût et solde après ; bloc Effet et délai ; éventuelles restrictions issues du service ; boutons de confirmation et annulation. Tous les champs pouvant influer sur la décision sont visibles avant le clic.

**Action lancée** : titre de l’action ; phrase « {action} en cours » ; coût réellement débité/réservé ; cible/méthode ; échéance de résolution. Ne pas écrire « terminé » lorsqu’un job vient seulement d’être enregistré.

**Résultat ponctuel** : titre de rubrique ; phrase de résultat ; deux à quatre valeurs clés ; détail conditionnel s’il existe dans le résultat métier. Pas de bloc d’aide répétitif si l’action a réussi.

**Erreur métier** : titre `ROOT OS · Action indisponible` ; cause concrète ; requis/actuel/manquant lorsqu’ils sont disponibles ; action de reprise valide. Le code d’erreur et la trace technique ne sont pas affichés. Ne pas produire un bouton qui contourne une restriction.

**Notification** : titre d’événement ; résultat ; objet concerné ; montant/échéance ; commande de reprise si nécessaire. Un MP ne suppose pas que son destinataire dispose du contexte original.

**Rapport** : résultat en premier ; participants autorisés ; données utilisées à la résolution ; conséquences ; suite possible et durée réelle des droits. Ne pas remplir un rapport avec des valeurs de la nouvelle consultation à la place du résultat résolu.

### 15.3 Budgets de contenu internes

Ces budgets sont des objectifs de lisibilité, plus stricts que les limites officielles : titre jusqu’à 80 caractères, description courte jusqu’à environ 600 caractères, résultat/erreur ponctuels idéalement sous 800 caractères au total. Accueil network fusionné avec l’infrastructure : au plus sept champs verticaux courts ; détails network : au plus six blocs lisibles. Les champs de l’Accueil visent chacun 500 caractères maximum, et un champ de détail vise 800 caractères maximum pour garder une marge aux traductions. L’ensemble respecte toujours le plafond officiel total des embeds du message ; condenser les explications générales avant de retirer une information requise ou l’image demandée.

Les puzzles et rapports utiles peuvent dépasser ces objectifs, sans dépasser les contraintes Discord. Paginer les listes, jamais les données indispensables à une confirmation. Si un devis devient trop long, condenser les explications générales et préserver objet, coût, effet, délai et solde attendu.

Pour une liste de représailles ou d’opérations trop longue, page de cinq entrées et indicateur `Page {n}/{total}`. Les totaux portent sur toute la liste, pas la page affichée. Ne pas tronquer silencieusement à trois adversaires comme le résumé actuel.

### 15.4 Formats

- Montants transactionnels : réutiliser `format_usd` et `format_rtm` et la précision existante. Afficher le symbole USD sous la forme `USD` dans les données et `USD` dans les devis, sans alterner arbitrairement `$`, « dollars » et `USD`.
- Débits : `MathConfig.format_hashrate` pour H/s et `format_bits_per_s` pour bits/s. Le stock consommable est un entier ATK ; la défense est un entier DEF.
- Production horaire : `Decimal(rate_per_min) × 60`, avant formatage. Ne pas convertir une chaîne déjà arrondie, ni reconstruire le bonus de réputation si `rate_per_min` l’inclut déjà.
- Mémoire : `memory_used_formatted / total_ram_formatted` avec unités o/Ko/Mo/etc. Le tampon RTM et la capacité RTM sont d’autres valeurs ; ne pas libeller le tampon « RAM en RTM ».
- Jauge mémoire : dix segments, remplissage borné entre 0 et 10 pour le dessin ; pourcentage affiché issu de l’état métier. Une jauge n’est jamais l’unique indication.
- Infrastructure : six niveaux 0–5, affichage `Niveau {n}/5`, sans appeler les niveaux « Tier ».
- Tier : T1–T5 pour les modules actuellement parcourus par le code. Ne pas créer un T6 à partir d’une ancienne docstring.
- Échéance : `to_utc_timestamp` puis format Discord relatif et, si utile, horaire local. Une date absente donne une information manquante neutre, pas un faux timestamp zéro ou une échéance « maintenant ».

Les formatters actuels peuvent contenir des particularités héritées. Ne pas modifier silencieusement leur comportement dans un chantier de style : si une valeur affichée paraît mathématiquement trompeuse, documenter le cas et traiter explicitement la correction de présentation sans toucher à la valeur comptable.

### 15.5 Langues et mentions

Conserver la priorité de langue existante : préférence du joueur, locale Discord supportée, repli anglais. Précharger la langue avant de construire un panneau. Pour un MP différé, récupérer la préférence du destinataire par ID ; ne pas employer celle de l’auteur de la commande ou un contexte perdu.

Les messages publics sans destinataire unique conservent leur langue/canal actuelle pendant cette refonte ; leur texte doit néanmoins appartenir aux ressources de langue, pas à une chaîne codée en dur. Une nouvelle politique de langue de serveur nécessiterait une décision distincte.

Toutes les interpolations nécessaires doivent exister dans les versions FR et EN. Garder les clés métier historiques si elles évitent une migration du code ; changer leur valeur visible. Ne pas afficher `MISSING_KEY`, une variable `{usd}` non remplie ou un libellé français dans un MP anglais.

Conserver `AllowedMentions.none()` quand il est actuellement utilisé, y compris lors des éditions et des followups. Pour les rappels avec mention prévue et autres notifications existantes, préserver exactement l’exception actuelle, sans autoriser des mentions additionnelles provenant d’un texte libre.

## 16. Spécification détaillée du poste de commande

### 16.1 Organisation des composants

Le panneau possède un menu de navigation sur la première ligne avec quatre valeurs internes stables : `overview`, `farm`, `hardware`, `operations`. Les labels sont traduits ; les valeurs internes ne le sont pas. L’option de la vue courante est sélectionnée. Il n’existe ni option, ni route, ni builder de vue `infrastructure` autonome : son contenu est intégré au builder `overview`.

Deuxième ligne : `Récolter` puis `Actualiser`, dans cet ordre, présents dans toutes les vues. Récolter est désactivé lorsque le tampon vaut zéro. Son label reste « Récolter » plutôt que d’y inclure un montant long ; le montant figure déjà dans la vue Ferme/Accueil. Actualiser conserve la rubrique et la page actuelles.

Troisième ligne uniquement si nécessaire : action contextuelle de rubrique et navigation de pagination. Pas de rangée vide ni de bouton décoratif. La vue Ferme donne les états et la syntaxe des commandes actuelles d’autoclaim ; elle n’ajoute pas de bouton de programmation dans cette version de référence. Cela garde un parcours précis sans créer un gestionnaire d’autoclaim différent.

Matériel propose `Ouvrir la boutique`. Opérations propose `Compiler`, `Scanner`, `Préparer une attaque`. Accueil propose `Améliorer`, désactivé au maximum ou pendant un upgrade en cours. Les contrôles restent consultatifs jusqu’à l’ouverture d’un devis ; ils ne consomment aucune ressource. L’image du niveau courant reste visible dans chacune des quatre vues et sur chacune de leurs pages.

### 16.2 Vue Accueil : ordre exact

1. Auteur/identité : `ROOT OS · Réseau de {display_name}` ; avatar du joueur dans le petit élément d’auteur si disponible, sans le dupliquer en thumbnail.
2. Description : `{type d’infrastructure} · Niveau {n}/5`, puis état du minage.
3. Champ `Ferme` : puissance, production horaire et réputation/bonus en une ligne courte supplémentaire si le bonus est positif.
4. Champ `Récolte et mémoire` : montant à récolter, jauge + pourcentage, mémoire utilisée/capacité ; échéance de remplissage uniquement si une production est possible et la mémoire n’est pas pleine.
5. Champ `Ressources` : USD et RTM en portefeuille. Ne pas ajouter au portefeuille le RTM encore dans la mémoire.
6. Champ `Infrastructure et protection` : défense infrastructure, défense modules, total ; accès/bonus et détection de scan actuellement acquis, exprimés en lignes courtes.
7. Champ `Identifiant réseau` : identifiant propre et prochaine rotation, avec la visibilité/protection actuelle.
8. Champ `Progression` : type/niveau cible et échéance si un upgrade est actif ; sinon type de la prochaine étape et invitation à ouvrir le devis ; au niveau 5, état maximal. Les règles exactes de ces trois champs sont détaillées en section 16.7.
9. Champ `En cours`, seulement s’il existe une compilation, un scan ou des attaques lancées : synthèse au plus une ligne par catégorie. Ne pas dupliquer l’upgrade déjà décrit dans Progression.
10. Illustration du niveau réellement acquis ; elle apparaît à l’emplacement permis par l’embed classique Discord, et reste présente dans toutes les autres vues.
11. Footer `ROOT OS · Accueil` et timestamp de dernière construction. Les sept champs maximum correspondent à Ferme, Récolte et mémoire, Ressources, Infrastructure et protection, Identifiant réseau, Progression, En cours.

États de minage : zéro mineur → « Aucun mineur installé » avec indication d’accès Matériel ; mémoire pleine → « Mémoire pleine · Récolte disponible », ambre ; sinon → « Production active ». Ne pas conclure à une anomalie ou attaque sur la seule couleur du panneau.

### 16.3 Vue Ferme : ordre exact

Description : « Production et stockage de ta ferme ». Premier bloc : H/s total, RTM/h réel, bonus de réputation si applicable. Deuxième bloc : récoltable, mémoire, temps avant saturation lorsque pertinent. Troisième bloc : une entrée par tier possédé avec quantité, H/s agrégés et mémoire apportée. Quatrième bloc : crédits autoclaim disponibles, nombre programmé et crédits Combo Saver.

Si aucun mineur : remplacer le bloc par tier par « Aucun mineur installé. Ouvre Matériel pour consulter la boutique. » Les soldes et crédits restent affichables. Si la mémoire est pleine, ne pas écrire un débit reçu garanti : préciser que la récolte libère le stockage, selon le comportement de minage actuel.

### 16.4 Vue Matériel : ordre exact

Description : « Équipements installés · Quantités regroupées par tier ». Trois champs : Minage, Attaque, Défense. Dans chacun, une ligne par tier possédé :

- Minage : `T{n} · ×{quantité} · {H/s agrégés} · {mémoire apportée}`.
- Attaque : `T{n} · ×{quantité} · {bits/s agrégés}`.
- Défense : `T{n} · ×{quantité} · {DEF agrégés}`.

Une catégorie vide affiche une ligne « Aucun module installé » dans sa propre section ; ne pas supprimer la distinction entre catégories. Quatrième bloc : totaux matériel H/s, bits/s et DEF, sans additionner des unités incompatibles. Indiquer le niveau d’accès à l’achat avec le lexique infrastructure. La défense de l’infrastructure figure dans l’Accueil et n’est pas attribuée aux modules. Cette vue conserve son récapitulatif complet ; le détail ATK/DEF est aussi consultable dans Opérations pour les décisions PVP, avec les mêmes sources de données.

Cliquer `Ouvrir la boutique` publie un panneau boutique séparé sans image, dans le même contexte de visibilité que la commande boutique actuelle. Le poste de commande reste disponible dans sa vue Matériel. Le catalogue possède ses propres controles et sa propre expiration.

### 16.5 Vue Opérations : ordre exact

1. Champ `Capacité offensive` : stock ATK disponible et puissance totale de compilation bits/s. Ne pas assimiler le stock consommable aux modules.
2. Champ `Modules d’attaque` : une ligne par tier possédé, `T{n} · ×{quantité} · {bits/s agrégés}`, suivie du total de modules et du total bits/s. Utiliser `stats.bay_details[tier].attack_count` et `attack_bits_per_s`, puis `stats.total_bits_per_s`. C’est la même présentation par tier que celle des mineurs dans Ferme, avec l’unité propre à l’attaque.
3. Champ `Modules de défense` : une ligne par tier possédé, `T{n} · ×{quantité} · {DEF agrégés}`, suivie du total de modules et DEF des modules. Utiliser `bay_defense_count`, `bay_defense_power` et `stats.total_bay_defense`. Une ligne de contexte distingue `Infrastructure : {network_defense} DEF · Total : {total_defense} DEF`, sans additionner une seconde fois les DEF d’infrastructure.
4. Champ `Préparations` : compilation actuelle puis scan actuel, s’ils existent, avec méthode/cible autorisée et échéance.
5. Champ `Attaques lancées` : cinq opérations maximum par page, données de départ et échéance.
6. Champ `Représailles` : adversaires identifiés et échéance réelle ; toutes les entrées accessibles par pagination si nécessaire.

Les deux champs de modules restent présents même lorsque leur catégorie est vide, avec « Aucun module d’attaque installé » ou « Aucun module de défense installé ». Tous les tiers possédés sont affichés, y compris ceux acquis par capture au-delà de l’accès achat actuel. Les modules ne sont pas paginés séparément tant que les cinq tiers actuels tiennent dans un champ ; la pagination des opérations/représailles conserve les deux blocs de matériel et l’illustration. Les valeurs correspondent à la même photographie réseau que les totaux de Matériel.

Une section d’opérations vide peut afficher « Aucune opération en cours » car c’est un état réel pertinent du jeu. Cette vue n’est pas un historique : une attaque résolue disparaît de la liste active selon les données actuelles. Ne pas créer de base d’archive.

L’interface ne montre pas le Secret ID obtenu par un scan privé dans une rubrique publique ; elle indique au plus le scan en cours. Ne pas afficher une attaque entrante ou l’identité de son auteur avant les notifications auxquelles le joueur a droit dans le jeu actuel.

### 16.6 Entrées des actions PVP depuis le panneau

Les formulaires sont des raccourcis vers les commandes actuelles, avec les mêmes normalisations et validations. Le panneau principal n’est pas remplacé par ces formulaires ou par leurs résultats.

**Compiler** : ouvrir une sélection des méthodes actuelles `unskilled`, `skilled`, `ai`, avec labels issus de la traduction. Après sélection, demander la quantité ATK dans un formulaire court acceptant l’entier ou le mot `all` déjà accepté. Ne pas choisir automatiquement `all` sans que le joueur voie ce choix. Soumission → appel de devis `compile` avec `confirm=False`, mêmes paramètres `mode`, `atk`, `all` que la commande ; afficher ensuite le devis compact actuel adapté à la charte. Validation → `Confirmation` conservant `quoted_rtm`, `quoted_atk` et `quoted_duration` comme aujourd’hui.

**Scanner** : demander un utilisateur du serveur via un sélecteur utilisateur si le SDK local le permet, sinon formulaire d’ID/mention passant dans le résolveur de cible actuel. Aucun scan n’est lancé à la sélection. Obtenir le devis, afficher les options d’engagement ×1/×2/×5 déjà retournées par le service ; sélectionner une option exécute la confirmation actuelle avec ses vérifications. Ne pas remplacer le mécanisme de boost par un unique coût arbitraire.

**Préparer une attaque** : demander `Identifiant secret`, `Points ATK`, `Zone ciblée` limitée à `mining` ou `attack` et traduite visuellement en Minage/Attaque. Utiliser un sélecteur ou un formulaire avec normalisation des deux valeurs actuelles. Soumission → devis `hack` non confirmé. Le devis affiche la cible effectivement résolue par le service et le stock restant. Validation → même confirmation que `HackConfirmView`, mêmes arguments et revalidation. Ne jamais générer un Secret ID à partir de l’utilisateur sélectionné ni passer outre l’exigence d’un identifiant valide.

Les messages de devis restent dans les destinations/visibilités actuelles de leur commande. Les erreurs de saisie peuvent être éphémères, mais ne modifient pas la politique de publication des résultats. Si un modal ou sélecteur n’est pas compatible avec la dépendance installée, documenter la contrainte et garder un raccourci qui affiche la syntaxe exacte de la commande ; ne pas changer la version du SDK pour cacher un problème de conception.

### 16.7 Contenu d’infrastructure fusionné dans l’Accueil

Cette section décrit les blocs intégrés à l’Accueil en section 16.2, pas une cinquième vue. Le type et le niveau restent dans l’en-tête. Champ `Infrastructure et protection` : DEF infrastructure, DEF modules, DEF total, puis accès et bonus actuels en lignes courtes : prérequis réellement débloqués, multiplicateur events réel, multiplicateurs hourly/contrats tels que calculés par leurs services actuels et capacités de détection de scan existantes. Les gains complets de la prochaine étape figurent dans le devis, afin de ne pas surcharger ce bloc. Éviter les promesses « impénétrable » ou « invulnérable » si elles ne correspondent pas à une règle effective.

Champ `Identifiant réseau` de l’Accueil : valeur présentée avec la protection de texte déjà utilisée pour l’identifiant propre au joueur et prochaine rotation. La conversion du renderer doit vérifier le format exact actuel ; ne pas rendre plus public un secret précédemment masqué.

Champ `Progression` de l’Accueil : si une amélioration est active, niveau/type cible et échéance, bouton Améliorer désactivé ; sinon si niveau <5, type cible et invitation à consulter le devis ; au niveau 5, « Infrastructure maximale atteinte », sans cible fictive niveau 6. Améliorer est une action de l’Accueil. L’ouverture ou l’actualisation de l’Accueil ne prélève pas le coût d’un devis.

La consultation peut montrer les avantages de la prochaine étape, mais ceux-ci sont calculés à partir des fonctions/configurations actuelles. Si les textes hérités codent des valeurs de défense périmées, remplacer ces nombres par paramètres issus des règles ; ne pas modifier les règles pour faire correspondre le jeu à l’ancien texte.

## 17. Contrats de données à respecter

### 17.1 Données déjà fournies par la consultation réseau

Le dictionnaire actuel expose notamment :

- `discord_id`, `dollars`, `rootium`, `firewall_level`, `reputation`, `created_at`.
- `attack_points` pour le stock consommable ATK.
- `stats.total_hashrate_hs` et `stats.total_hashrate_formatted`.
- `stats.total_bits_per_s` et `stats.total_bits_per_s_formatted`.
- `stats.total_ram_bytes`, `stats.total_ram_formatted`.
- `stats.network_defense`, `stats.total_bay_defense`, `stats.total_defense`.
- `stats.bay_details[tier]` avec `mining_count`, `mining_hashrate`, `mining_ram_formatted`, `attack_count`, `attack_bits_per_s`, `bay_defense_count`, `bay_defense_power`.
- `mining_state.buffer`, `rate_per_min`, `memory_used_formatted`, `total_ram_formatted`, `memory_pct`, `is_full`, `seconds_to_full`, `capacity_rtm`.
- `pending_upgrade` : amélioration d’infrastructure, avec niveau cible et échéance.
- `pending_hack` : dans ce résultat réseau, il s’agit du job de compilation ATK, et non de la liste des attaques PVP. Cette nomenclature historique doit être adaptée dans le modèle de présentation, sans confondre les deux.
- `pending_scan`, `retaliations`, `secret_id_display`, `secret_next_ts`.
- Crédits `autoclaim_credits`, `autoclaim_active`, `combo_saver_credits` quand présents dans la ligne joueur.

Vérifier les valeurs nulles et absentes. Le renderer peut utiliser zéro pour un compteur absent, mais pas pour une échéance, une identité de cible ou un résultat d’attaque. Une donnée de résultat privée absente n’est pas récupérée par une nouvelle requête directe depuis le renderer.

### 17.2 Extension minimale pour les attaques lancées

Ajouter au résultat de consultation une clé nouvelle, par exemple `outgoing_pvp_attacks`, issue de `PvpDB.get_active_for_attacker(tx, actor)` dans la transaction du service. Cette méthode existe déjà dans `game/db/pvp.py`. Les entrées utiles à la présentation sont l’ID d’opération, la cible, la zone, les ATK engagés, le départ et l’échéance (`resolves_at`).

Ne pas modifier la méthode de création/résolution d’attaque. Ne pas joindre les attaques reçues à ce résultat. Une liste absente avant l’adaptation donne une section non disponible en développement ; la version finale doit fournir une liste vide ou peuplée, sans fabriquer d’entrée.

### 17.3 Modèle de présentation conseillé

Isoler l’adaptation des noms historiques dans une couche de présentation légère. Par exemple, convertir `firewall_level` en `infrastructure_level`, `pending_hack` en `pending_compile` et associer le label de type via le catalogue. Garder le dictionnaire brut disponible aux handlers existants ; ne pas faire un remplacement global de chaînes dans les clés SQL ou arguments de service.

Les builders doivent pouvoir recevoir une photographie de résultat et une langue sans appeler la base. Ils peuvent calculer des formats visuels ou la production RTM/h ; toute donnée ayant un effet économique continue à provenir des méthodes métier.

Contrat conceptuel conseillé : builder réseau = données + langue + vue + page → embed + description des contrôles disponibles. Renderer de notification = données de livraison + langue destinataire → embed. L’envoi et les callbacks restent responsables du contexte Discord, des autorisations, des mentions et des transactions.

## 18. Machines d’états des interactions

### 18.1 Session réseau

État de session : propriétaire, contexte/guild, référence de message, langue, vue courante, pages courantes, verrou, état actif/expiré. Le timeout de référence est le timeout actuel du réseau, 180 secondes. Ne pas ajouter de persistance de sessions au redémarrage.

Séquence de clic : vérifier propriétaire et accès → acquitter l’interaction dans les délais Discord → verrouiller l’opération → charger les données → produire le rendu → éditer le même message → libérer le verrou. Une erreur n’efface pas le dernier panneau valide. Une notification d’échec courte permet de reprendre avec Actualiser ou `/network`.

Navigation et actualisation ne changent pas les soldes au-delà des effets habituels de consultation du service réseau, qui matérialise déjà le minage. Récolter appelle le service claim, puis recharge la consultation. Le panneau affiche la vraie récolte, éventuellement nulle si une action concurrente l’a déjà effectuée ; ne pas utiliser le montant dessiné avant le clic comme montant à créditer.

Après expiration : conserver les valeurs de la dernière photographie, désactiver menu et boutons, changer le footer avec « Session expirée · Rouvre {commande réseau} ». Ne pas actualiser les données une dernière fois pour calculer un nouveau bilan. Si le message a disparu, arrêter proprement la session sans recréer automatiquement un panneau public.

### 18.2 Devis et confirmations ordinaires

États : devis affiché → confirmation en traitement → résultat lancé/réussi ou erreur ; alternative annulation ; alternative expiration. Le timeout générique actuel est de 120 secondes.

Sur confirmation, acquérir le verrou et vérifier que la vue n’a pas déjà été traitée. L’exécution est effectuée une seule fois. Garder les paramètres de comparaison de devis déjà présents dans compile/buy et les validations métier de chaque action. Un solde modifié pendant l’attente peut entraîner un nouveau refus ; le rendu doit l’expliquer, pas employer des valeurs du devis pour forcer la transaction.

Après succès, les anciens boutons cessent d’être actifs. Si le parcours existant poste un résultat dans un followup, conserver cette architecture au premier passage : le devis initial reçoit un état final explicite avec ses contrôles retirés, et le followup porte le résultat complet. S’il édite déjà le devis sur place, conserver cette voie. L’objectif est une continuité de style, pas une réécriture générale du transport.

Annulation : remplacer le corps du devis par un résultat compact « Action annulée » de la même rubrique ; retirer les contrôles ; aucune transaction. Expiration : conserver un résumé du devis, préciser qu’il n’a pas été exécuté, désactiver les contrôles et indiquer la commande à relancer. Ne pas convertir ces états en texte brut sans identité Root OS.

### 18.3 Échange à deux participants

Conserver le timeout propre à `TradeView`, les deux validations et les droits de refus. L’affichage doit distinguer : attente des deux joueurs, premier accord reçu, second accord reçu, échange exécuté, refus, expiration, échec métier.

Afficher ce que chaque joueur envoie et reçoit sans inversion. La première validation ne déplace pas de ressources. Une seconde validation recontrôle les disponibilités avec la logique existante. Les MP de fin utilisent la langue de chacun. Le public ne reçoit pas plus de renseignements que ceux déjà publiés par le jeu.

### 18.4 Défis communautaires

Conserver tous les chemins de `MiniGameCog` : `active_info`, `too_low`, `too_high`, `wrong`, `won`, `cooldown`, `player_cooldown`, entrées invalides. La refonte ne change ni `guess_kind`, ni `shape`, ni bornes, ni `log_kwargs`.

Après victoire, les panneaux actifs suivis par `ChallengeTracker` deviennent des panneaux « Défi résolu » avec gagnant et prochaine ouverture selon les données autorisées. Enlever leurs contrôles utiles à l’ancien défi. La mise à jour du tracker doit garder l’identité du mini-jeu, la langue du message et sa référence ; ne pas reconstruire tous les messages dans la langue du gagnant.

Conserver le signalement et la journalisation de victoire une seule fois. Ne pas utiliser le message de succès graphique pour déclencher une deuxième récompense.

## 19. Cahier de rendu par commande et notification

Cette section précise les contenus minimums. Les phrases proposées sont des références rédactionnelles ; les valeurs entre accolades sont des données réelles et ne doivent jamais être laissées littéralement dans un message. Les identifiants de chaînes existants peuvent être conservés et les textes scindés en labels/champs si nécessaire.

### 19.1 Boutique et achat

**Boutique principale** : titre `ROOT OS · Boutique` ; description « Développe ton installation en choisissant une catégorie de matériel » ; trois catégories avec une seule phrase chacune : Minage produit du RTM et apporte de la mémoire ; Attaque fournit la capacité de compilation ; Défense apporte des DEF. Ne pas présenter les modules d’attaque comme un achat direct du stock ATK.

**Catégorie** : titre `ROOT OS · Matériel de minage/attaque/défense` ; solde dans la monnaie nécessaire ; niveau/type d’infrastructure ; rôle du module ; menu des tiers achetables selon les règles actuelles. Remplacer les suffixes `FW 2+` par `Infrastructure 2 minimum`. Garder les prix et les stat bonus des options exacts ; label sans emoji doublonné. Une option non achetable ne doit pas devenir achetable à cause d’un simple changement d’affichage. Quand le filtre est vide, afficher « Aucun module achetable avec ton solde et ton infrastructure actuels » plutôt qu’un menu vide.

**Devis achat** : type, tier et quantité ; prix total et devise ; solde après ; gain de puissance/capacité agrégé ; Confirmer/Annuler. Le formulaire doit conserver les quantités/all éventuellement acceptées actuellement. **Résultat** : « Matériel installé » ; quantité réellement acquise ; montant débité ; solde réel et gains. Sans illustration.

### 19.2 Amélioration d’infrastructure

**Devis** : nom actuel et cible, niveaux, prix, solde actuel/après, durée, gain DEF et DEF final, accès et bonus débloqués. Exemple : « PC assemblé → Station de travail », puis « Infrastructure 1 → 2 ». Les nombres proviennent de `upgrade_quote` et des getters/configs déjà utilisés. Si une propriété héritée est décrite par une phrase trop absolue, réécrire sa description sans modifier sa règle.

**Démarrage** : « Amélioration en cours » ; type/niveau cible ; coût réellement débité ; livraison relative. **Livraison MP** : « Nouvelle infrastructure disponible » ; type/niveau effectivement livré ; invitation à actualiser network. Ne pas joindre l’image au MP. **Maximum** : « Ton Datacenter est au niveau maximal d’infrastructure » ; aucun devis supplémentaire. **Déjà en cours** : cible et échéance, pas une confirmation de double upgrade.

### 19.3 Récolte et autoclaim

**Récolte réussie** : « Récolte effectuée » ; RTM crédité ; RTM en portefeuille ; état de la mémoire après l’action si disponible ; rappel resynchronisé seulement si le résultat le confirme. Utiliser `amount` et `new_rootium` de claim, pas le tampon de l’ancien network.

**Mémoire vide** : « Rien à récolter pour le moment » ; production réelle et temps avant remplissage s’ils existent. **Sans mineur** : « Aucun mineur installé » ; syntaxe ou accès boutique, sans calcul fictif de remplissage.

**Autoclaim programmé** : nombre activé, nombre en file, crédits restants, récolte immédiate éventuelle déjà effectuée par le service. **Annulation** : nombre remboursé et nouvelle réserve. **Livraison automatique** : somme créditée, solde et file restante, tout en conservant les logs du claim automatique et leur fréquence. Ne pas faire une seconde récolte parce que la notification vient d’être envoyée.

### 19.4 Prime horaire et Combo Saver

Un gabarit unique de prime affiche gain USD, combo courant, bonus, prochaine disponibilité et nouveau solde lorsqu’il est présent dans le résultat. La phrase distingue première prime, combo poursuivi et combo perdu.

Si le combo est perdu et récupérable, afficher le bouton de restauration existant avec coût en crédit et réserve disponible ; ne pas l’activer si le service ne l’autorise pas. Après restauration, éditer ou compléter l’embed avec combo restauré et crédits restants. Le callback actuel ajoute du texte à `interaction.message.content` : l’adapter à la présentation en embed, sinon la nouvelle version produira un contenu vide ou un résultat séparé incohérent.

### 19.5 Conversion

**Devis** : RTM vendu, taux appliqué, USD obtenu, soldes RTM et USD avant/après. Préserver `rate` transmis à la confirmation. **Succès** : « Conversion effectuée » ; RTM vendu, USD crédité, taux et soldes finaux. Les alias `sell`, `sell all` et options `all` conservent leur comportement. Le log blockchain représente la transaction réalisée une seule fois.

### 19.6 Échanges

**Proposition** : participants, bloc « {joueur A} envoie », bloc « {joueur B} envoie », puis statut explicite des deux validations. Les montants zéro peuvent être condensés sous « Aucune ressource » selon le comportement actuel, sans supprimer l’identité de la partie.

**Premier accord** : « Accord de {joueur} reçu · En attente de {autre joueur} ». **Exécution** : « Échange effectué » avec flux réels. **Refus/expiration** : résultat propre, sans contrôles actifs. **MP** : « Échange avec {partenaire} effectué », ressources reçues et envoyées dans le sens du destinataire.

### 19.7 Réputation, attestations et classement

**Réputation accordée** : destinataire, points accordés ; éventuel accès bêta et crédits de parrainage seulement si le résultat courant les attribue. **MP reçu** : donneur, points et serveur si déjà prévu. Ne pas supprimer les sous-messages de parrainage en condensant le succès.

**Attestation** : « Seuil de ressources confirmé » ou « Seuil de ressources non atteint » ; joueur, devise et montant demandé. Ne pas afficher le solde exact du joueur : cette commande atteste un seuil, elle ne devient pas une consultation de portefeuille.

**Classement** : titre avec catégorie ; lignes `rang · joueur · valeur et unité` ; rubriques déjà disponibles ; rang propre si le résultat le fournit ; pagination actuelle conservée. Ne pas remplacer une catégorie par une autre statistique pour simplifier le design. Pas de podium qui transforme la règle de classement ni de nombres inventés pour l’apparence.

### 19.8 Contrats

**Offres** : agence, fidélité actuelle/seuil, mission spéciale éventuelle, trois durées et rémunérations réelles. **Actif** : agence, mission, rémunération promise et échéance. **Prêt** : « Contrat terminé · Paiement disponible », gain et bouton d’encaissement. **Encaissé** : gain et nouveau solde, progression de fidélité si fournie. **MP d’échéance** : « Contrat terminé », agence, titre, gain disponible et syntaxe de collecte.

La notification d’échéance ne remplace pas l’encaissement manuel actuel. Ne pas créditer automatiquement le joueur pour rendre la notification plus simple. Ne pas afficher une mission spéciale quand son bonus n’est pas actif.

### 19.9 Compilation ATK

**Devis** : méthode traduite, débit de calcul bits/s, ATK attendu, coût RTM, durée. **Démarrage** : méthode, ATK en préparation, coût réellement payé, échéance. **Livraison** : ATK réellement livré et stock final si fourni. Garder le nom compilation ; ne pas appeler le résultat « logiciel », « faille » ou « recherche ».

Conserver les trois méthodes et leur coût/rendement actuels ; conserver le choix explicite d’un montant ou `all`. Les confirmations maintiennent les valeurs de devis nécessaires à la revalidation. Les notifications différées ne doivent pas annoncer le stock final avec une valeur prise au démarrage.

### 19.10 Scan

**Devis** : cible, coût de base, estimation de probabilité et durée issus de l’état courant. Options d’engagement actuelles : chacune affiche multiplicateur, coût et estimation réellement retournée. Si un label déborde, raccourcir les mots plutôt que couper le coût ou la probabilité. **Démarrage** : cible, coût, échéance.

**Succès MP** : « Scan réussi » ; cible, identifiant obtenu, prochaine rotation ; boutons Exposer/Garder secret. **Échec MP** : « Scan sans résultat » ; cible et suggestion existante, sans identifiant fabriqué. **Alerte victime** : infrastructure/niveau si utile, et uniquement l’identité autorisée par le palier/résultat actuel. Aucune identité supplémentaire dans un footer.

**Exposition** : conserver l’étape de confirmation explicite avant publication. L’avertissement dit que le Secret ID sera publié et utilisable selon les règles actuelles ; ne pas prétendre que tous les joueurs pourront ignorer les restrictions de PVP. La publication utilise la sortie dédiée et la valeur obtenue par le scan, sans transformer le panneau réseau en publication de renseignements.

### 19.11 Attaque et rapports

**Devis** : identifiant ciblé, joueur effectivement résolu, zone choisie, ATK engagés, ATK restant et échéance prévue. Bouton « Lancer l’attaque » et bouton « Annuler le devis ». Le bouton actuellement nommé « Interrompre » ne doit pas laisser croire qu’une attaque lancée peut être rappelée si le jeu ne le permet pas.

**Lancement** : « Attaque engagée » ; cible, zone, ATK réellement réservés et résolution. **Rapport attaquant** : accès obtenu/refusé ; ATK engagés ; défense à la résolution ; contribution infrastructure/modules si actuellement communiquée ; DEF endommagés ; modules détruits/capturés ou zone vide.

**Rapport victime** : résultat et pertes d’abord ; identité de l’attaquant selon la notification actuelle ; défenses endommagées et modules perdus ; « Infrastructure intacte » à la place du pare-feu ; droits de représailles et nouvelle identité réseau protégée comme aujourd’hui.

Les résultats peuvent inclure des dictionnaires `destroyed_attack_modules` et `captured_mining_modules`, avec quantités par tier. Les libeller sous forme de liste, par exemple « T3 ×2 · T2 ×1 », sans prétendre qu’un seul module est toujours concerné. Préserver les fallbacks de tier unique lorsque seuls ceux-ci sont retournés. Ne pas programmer une nouvelle limitation à un module sur la base d’un ancien exemple.

Un rapport ne promet pas un bénéfice garanti et ne change pas la résolution. Les données viennent de `_notify_and_log_resolved` et du résultat de `deliver_expired_pvp_attacks`, pas d’une nouvelle simulation.

### 19.12 Événements et sept mini-jeux

**Catalogue events** : chaque événement possède nom, disponibilité actuelle, consigne courte, récompense/règle actuelle et commande. Bonus intitulé « Bonus d’infrastructure » avec valeur issue du service. Ne pas afficher une progression de firewall résiduelle.

**Hash et PIN** : intervalle/état exact, récompense et prochaine tentative lorsque fournie ; réponse « Trop bas » ou « Trop haut » explicite. Un seul petit gabarit suffit pour les retours répétitifs ; pas d’image ou d’animation narrative qui ralentit les tentatives.

**Decode** : séquence exacte dans son bloc, consigne et syntaxe de réponse. **Anomaly** : les dix lignes et leur numérotation intactes, consigne de la ligne à donner. **Buffer** : fragments inchangés et format de code attendu. **Signal** : séquence exacte, choix de lettre et boutons existants, sans restriction au propriétaire si le défi est communautaire. **Packet** : transmission inchangée et paquet manquant à trouver.

**Mauvaise réponse** : phrase informative ambre, aucune nouvelle pénalité. **Victoire** : gagnant, récompense réelle et bonus d’infrastructure déjà appliqué ; prochaine ouverture si fournie. **Cooldown global** : délai et dernier gagnant/serveur tels qu’autorisés. **Cooldown individuel** : prochaine tentative du joueur. Ces deux cooldowns ne sont pas fusionnés.

### 19.13 Rappels

Création : type du rappel, texte utile, échéance et lieu de notification. Liste : rappels actifs avec ID nécessaire à l’annulation, type, échéance et texte ; pagination si la liste dépasse le budget. Annulation : ID/quantité effectivement annulée. Livraison : titre `ROOT OS · Rappel`, texte demandé et échéance.

`rmd` possède un repli salon quand le MP échoue : le préserver avec la mention du destinataire déjà prévue. Cela ne signifie pas qu’un MP de scan ou de hack doit lui aussi être publié lorsque les MP sont fermés. Les politiques de livraison de chaque commande restent distinctes.

### 19.14 Onboarding, aide et utilitaires

**Bienvenue** : conserver le choix de langue avant l’introduction ; après sélection, présenter brièvement Infrastructure, Ferme et premières commandes avec le préfixe effectif. Pas de nouveau pseudo à demander.

**Aide** : rubriques correspondantes à la nouvelle navigation ; syntaxe et paramètres réels ; descriptions d’infrastructure ; commandes directes accessibles sans obligation de passer par le hub. Le vocabulaire PVP reste celui du fonctionnement actuel. Ne pas retirer un alias documenté ni recopier les commandes de logiciels V2.

**Language** : langue active, confirmation de changement et labels traduits. **Prefix** : préfixe effectif et confirmation. **Ping** : latence réelle et unité. **Invite** : lien actuel, bouton natif de lien si compatible ; aucun nouvel hébergement. **Botinfo** : métriques actuelles, labels sobres, pas de compteur décoratif. **Maths** (`commands/utility/math.py`) : expression, résultat ou cause d’erreur ; ne pas toucher au calculateur AST ni aux limites de sécurité.

**Erreurs globales** : permissions, maintenance, accès bêta, compte absent, commande inconnue ou syntaxe invalide gardent leurs conditions actuelles. La nouvelle présentation indique clairement la cause et une reprise valide. Les descriptions slash et les labels d’options doivent être localisés aussi, pas seulement le résultat de la commande.

### 19.15 Annonces publiques et présence

Annonces de défi résolu, blockchain, échange et activité PVP : reprendre la charte compacte, avec les informations déjà publiques et sans ajouter de détails privés. Les adresses/IDs nécessaires à la blockchain restent présents ; ne pas les supprimer au motif que le footer ordinaire évite les IDs techniques.

Présence : harmoniser seulement les textes de statut existants et leurs noms. Les compteurs ou dates de lancement continuent à utiliser leur configuration actuelle. Ne pas supprimer une annonce de bêta active ni changer le mécanisme de rotation/rafraîchissement pour la charte.

## 20. Interventions détaillées par fichier et frontières du chantier

### 20.1 Fondations à créer

**`utils/root_theme.py`** : constants de palette, correspondance état→couleur, conventions de footer et budgets. Aucun import SQL ; aucune récupération de joueur. Les couleurs sont utilisées par les builders, pas recopiées dans chaque commande.

**`utils/root_emojis.py`** : registre des noms/IDs/flag animé, résolution au démarrage, méthodes de représentation texte et de propriété de composant. Repli sans icône, avertissement technique en cas d’asset manquant. Fournir une manière de vérifier les résolutions dans l’environnement de recette sans envoyer de message à tous les joueurs.

**`utils/infrastructure_display.py`** : six entrées, clé de traduction FR/EN, chemin relatif d’illustration ; validation du niveau attendu ; fonctions d’accès aux noms/types. Aucune copie des valeurs de défense/prix/bonus dans ce catalogue : celles-ci viennent des règles.

**Rendu réseau dédié**, par exemple `utils/network_display.py` : builders des quatre vues et adaptation de photographie métier ; blocs d’infrastructure dans le builder Accueil et détail des modules ATK/DEF dans le builder Opérations. L’application de l’illustration du niveau est commune aux quatre builders pour éviter un oubli. Ce nom est proposé pour éviter que `network.py` ne regroupe encore la totalité du rendu et des callbacks. Pas de sous-système React/HTML pour Discord, pas de génération d’images de statistiques.

### 20.2 Fondations existantes

**`utils/root_embed.py`** : faire évoluer `RootEmbed` pour un état de rendu explicite, une rubrique traduite et des champs structurés. Conserver pendant la conversion l’appel existant `RootEmbed(ctx, action, content)` ou une adaptation compatible. Une commande non encore convertie ne doit pas casser dès le lot fondations. La couleur d’une commande ne doit plus être l’unique moyen d’indiquer une erreur ou une réussite.

Les renderers de MP ne doivent pas créer un faux contexte `ctx` pour récupérer une langue hasard. Ajouter une voie prenant directement une langue/destinataire, ou un factory commun indépendant du transport, en conservant les appels existants jusqu’à conversion.

**`utils/ui_components.py`** : labels de verbes issus de `lang/`, icônes via registre, styles success/secondary/danger selon action. Annuler et Retour sont secondaires ; confirmer une opération habituelle peut rester success ; exposition de Secret ID est danger. Aucun emoji Unicode générique injecté par défaut en contradiction avec les packs personnalisés.

**`utils/confirmation.py`** : garder `lock`, `done`, `Check`, `response_context` et l’appel de service ; harmoniser erreurs, annulation, expiration et état final du devis. Retirer les edits `embed=None` qui remplacent systématiquement le panneau par une phrase brute. Vérifier la référence de message slash/préfixe et la bonne cible d’édition depuis un formulaire issu de network.

**`utils/trade_view.py`** : préserver `_execute_trade`, contrôles des deux joueurs et logs ; faire évoluer `build_embed`, `_build_status_text`, `_edit_message`, refus, timeout et MP. Chaque flux de ressources reste libellé pour le bon participant.

**`utils/text.py` / `utils/time_format.py`** : réutiliser les formateurs et helpers actuels, ajouter seulement les fonctions de présentation nécessaires. Ne pas changer la quantification des montants. Éviter les textes FR/EN construits à la main dans les callbacks.

### 20.3 Réseau et accès service

**`commands/game/network.py`** : remplacer le gros `_build_network_embed` par un appel aux builders de la vue courante. Faire évoluer `NetworkActionView` en session quatre vues, sans option Infrastructure autonome. L’Accueil porte le bouton d’amélioration ; Opérations affiche aussi les équipements d’attaque/défense par tier ; chaque édition conserve l’image du niveau actuel. Garder la création de compte, la boucle de rotation Secret ID et le choix de langue. Conserver l’appel `log_claim_events` du bouton de collecte et la journalisation actuelle.

Le `_build_compact_total_lines` historique ne doit pas survivre comme une seconde source de formats divergents ; ses données utiles sont réparties entre les builders. Ne pas effacer une donnée parce qu’elle encombre l’Accueil : la placer dans sa vue détaillée.

**`game/db/players.py` / `game/root_service.py`** : seule extension prévue : lecture des attaques sortantes autorisées ou métadonnées de consultation manquantes. Respecter l’architecture transactionnelle. La consultation règle déjà la progression minière, remet à jour des statistiques et assure l’identité réseau ; aucun nouveau callback de présentation ne remplace ces étapes par des accès SQL partiels.

**`game/db/pvp.py`** : réutiliser `get_active_for_attacker`. La refonte ne requiert pas de modifier les algorithmes de résolution. Toute modification d’un calcul de capture/destruction est hors périmètre.

### 20.4 Commandes économiques

**`commands/game/buy.py`** : `_get_purchasable_options`, `_get_shop_options`, les builders de catalogue/catégorie, `_build_quote_content_and_view`, `_send_quote_from_interaction`, `_send` et les branches de `ShopCatalogView`. Les prix, devis et paramètres de confirmation existants restent identiques. Tester les deux entrées : commande directe et raccourci network.

**`commands/game/upgrade.py`** : devis, branche `upgrade_started`, fallback succès immédiat et `_notify_delivered`. Corriger les textes « pare-feu » dans l’explication des avantages ; injecter les noms d’infrastructure actuel/cible. La boucle de livraison, son rythme et l’exécution transactionnelle ne changent pas.

**`commands/game/claim.py`** : remplacer la réponse brute `_reply` par le renderer approprié pour standard, vide, sans mineur, auto, annulation et notification. Garder `_log_blockchain`, `_log_moderation`, `_notify_and_log_autoclaim` et leurs conditions d’appel.

**`commands/game/hourly.py`** : renderer de chaque résultat et callback Combo Saver, qui doit éditer l’embed. Conserver le calcul de bonus, les états `is_first`/`combo_lost` et le service `hourly_save_combo`.

**`commands/game/convert.py`** : devis, succès et usages invalides ; garder les alias, taux de confirmation et log. **`trade.py`** : présentation initiale seulement, sans changer `parse_trade_tokens` ni l’ordre des ressources.

**`rep.py`**, **`attest.py`**, **`top.py`** : résultats, erreurs, MP de réputation et navigation du classement. La refonte n’ajoute pas de balance à l’attestation. **`contract.py`** : `_build_contract_content`, `ContractView`, transitions de collecte et MP ; rester fidèle aux agences, fidélité et missions spéciales.

### 20.5 Commandes PVP

**`compile.py`** : `_send`, `_notify_delivered`, textes d’usage, devis et notification de lancement. Garder le traitement des méthodes et valeurs `all`, les paramètres de devis, `_log_blockchain` et le rythme de livraison.

**`scan.py`** : `ScanBoostView`, `ExposeView`, `ConfirmExposeView`, `_send`, `_notify_delivered` et les alertes. Harmoniser toutes leurs erreurs/fins de session, y compris le bouton Garder secret et l’exposition publique. Garder seuils, destinations, anonymat, durée et représailles.

**`hack.py`** : `HackConfirmView`, `_send`, `_notify_and_log_resolved` et les rapports. Garder le lancement différé, les locks et les appels du service ; traiter les résumés multi-tiers. Ne pas supprimer les livraisons au démarrage du bot ni produire une seconde attaque lors d’une restauration de vue.

### 20.6 Défis et notifications

**`minigame_cog.py`** : chaque branche de status convertie vers un gabarit explicite ; `_reply_text` peut devenir un adaptateur de résultat selon la branche, mais il doit toujours retourner la référence utile au tracker. **`game_config.py`** : rendre cohérentes les consultations hash/pin avec les autres consultations ; préserver les champs qui définissent le jeu.

**`game/challenge_tracker.py`** : adapter le remplacement `msg.edit(content=..., embed=None, view=None)` pour un panneau terminal Root OS ; stocker au besoin la langue et l’identité de message en mémoire, sans table supplémentaire. **`commands/game/signal.py`** : adapter les boutons spécifiques et vérifier que leur accès communautaire ne devient pas un accès au seul créateur du message.

**`event.py`**, **`rmd.py`** et notifications de claim/upgrade/compile/scan/hack/contract : tous les chemins de MP et d’envoi différé doivent passer par la charte. Conserver les politiques de repli spécifiques.

Les managers `hash`, `pin`, `decode`, `anomaly`, `buffer`, `signal`, `packet`, `base_challenge_manager` et les règles de génération ne nécessitent pas de modification esthétique. Si un renderer dépend d’une structure qu’ils fournissent, adapter le renderer plutôt que transformer la séquence ou le puzzle.

### 20.7 Sorties transversales

**`commands/game/commandgame.py`** : `_send_error` et `_send_embed`, en préservant `_invoke` et la langue. **`main.py`** : gestionnaire d’erreurs globales uniquement dans les sorties visibles ; ne pas changer l’enregistrement des extensions ou les contrôles d’accès pour le style.

**`commands/utility/help.py`**, **`language.py`**, **`prefix.py`**, **`ping.py`**, **`invite.py`**, **`botinfo.py`**, **`math.py`** : toutes les réponses, usages et confirmations. Le calculateur et la configuration de langue/préfixe restent inchangés.

**`utils/logger.py`** : messages publics/blockchain et exposés ; pas de grand chantier de rapports de modération. Identifier chaque méthode par son canal réel avant de la classer : une méthode nommée log n’est pas nécessairement interne. **`utils/presence_manager.py`** : textes de présence, pas logique de calendrier.

**`lang/game_fr.py`, `game_en.py`, `fr.py`, `en.py`, `help_fr.py`, `help_en.py`, `descslash.py`** : retirer les wrappers graphiques hérités des chaînes quand les builders les fournissent ; traduire les nouveaux labels ; garder variables et correspondance de clés. Rechercher les mentions compactes `FW` et `Lv.` liées au firewall aussi, pas seulement le mot complet.

### 20.8 Fichiers à garder fonctionnellement stables

Pas de modification graphique justifiant un changement de `data/math.json`, schéma `root.sql`, formules de `game/math_config.py`, règles transactionnelles d’upgrades/claims/hack/contracts, tables SQL, dotation initiale, seuils d’accès bêta ou liste des joueurs autorisés. Aucune modification de secrets ou valeurs d’environnement existants sans nécessité explicite d’un mapping d’assets.

La documentation et `CHANGELOG.md` peuvent être modifiés lors de l’implémentation. `migration.sql` reste inchangé si aucune donnée n’est migrée. Garder les documents historiques PVP V2 comme archives ; ne pas les réintroduire comme spécification active.

## 21. Recette exécutable : scénarios, preuves et tests

### 21.1 Principe de comparaison

Avant de modifier les commandes, créer des photographies de données de test représentatives à partir des dictionnaires existants et capturer quelques rendus actuels dans un serveur de développement. Les données de test ne sont pas des paramètres d’équilibrage et ne doivent pas être ajoutées aux comptes de production.

Pour chaque parcours converti, comparer le résultat métier et les appels de service/log avant/après. Les captures prouvent l’apparence ; les tests prouvent l’exactitude des données et des transitions. Un embed joli ne constitue pas une preuve que la récolte n’est pas doublée ou qu’un scan est encore privé.

### 21.2 Scénarios réseau

- **NET-01 — Nouveau compte niveau 0** : `/network` crée le compte comme aujourd’hui ; image smartphone ; type et niveau corrects ; mineurs absents présentés clairement ; langue proposée ; Récolter désactivé. Aucun second compte créé par un clic.
- **NET-02 — Six niveaux** : fixture pour chaque niveau 0–5 ; nom FR/EN exact et illustration associée ; défense issue des règles ; pas d’image générique substituée.
- **NET-03 — Navigation** : Accueil → Ferme → Matériel → Opérations → Accueil ; exactement quatre options, aucune cinquième vue Infrastructure ; même ID de message ; option sélectionnée correcte ; contenu de la vue correct ; image du même niveau visible sans interruption à chaque étape et sur les pages des listes.
- **NET-04 — Actualisation** : actualiser depuis chaque vue conserve cette vue et sa pagination ; montant et timestamp deviennent ceux de la nouvelle consultation.
- **NET-05 — Récolte** : clic crédite le montant retourné par claim une fois, conserve les journaux et actualise tampon/portefeuille. Un second clic rapide ne crédite pas l’ancien montant.
- **NET-06 — Récolte concurrente** : une commande directe récolte avant le clic réseau ; le clic affiche le vrai résultat restant ou mémoire vide ; aucun crédit inventé.
- **NET-07 — Mémoire pleine** : ambre et texte explicite, tampon positif visible, mémoire utilisée/capacité exacte ; aucune « intrusion » déduite de cet état.
- **NET-08 — Sans capacité** : zéro mineur et zéro RAM ; aucune division par zéro, délai fictif ou jauge illisible ; états utiles et boutique accessibles.
- **NET-09 — Upgrade en attente** : nom/type actuel et image actuelle dans les quatre vues ; cible, échéance et bouton Améliorer désactivé dans l’Accueil ; après livraison, actualiser depuis chacune des quatre vues donne le nouveau nom/niveau et la nouvelle image, sans créer une vue Infrastructure.
- **NET-10 — Équipement capturé** : module de tier supérieur à l’accès achat visible dans Matériel ; son apport reste inclus dans les totaux.
- **NET-11 — Tâches simultanées autorisées** : compilation/scan/upgrade et attaques sortantes affichés selon les données réelles, sans confondre `pending_hack` avec une attaque.
- **NET-12 — Représailles nombreuses** : plus de cinq entrées ; toutes accessibles ; les échéances sont réelles ; pas de troncature silencieuse à trois.
- **NET-13 — Accès tiers** : autre joueur ne peut ni changer la vue ni récolter ; erreur éphémère dans sa langue ou celle définie par le parcours, sans nouveau panneau public.
- **NET-14 — Expiration/suppression** : contrôles désactivés et instruction de reprise à expiration ; disparition du message traitée sans nouvelle publication automatique.
- **NET-15 — Grands stocks et noms longs** : aucun dépassement des limites Discord, total encore accessible, rangées et labels lisibles sur mobile.
- **NET-16 — Détail ATK/DEF dans Opérations** : plusieurs tiers d’attaque et défense, dont un tier non achetable mais possédé ; quantités et bits/s/DEF par tier exacts, totaux identiques à Matériel, stock ATK séparé, défense de l’infrastructure non comptée deux fois. Les deux catégories vides sont rendues proprement et la pagination conserve le détail et l’image.
- **NET-17 — Accueil fusionné** : type/niveau, protection détaillée, bonus, identifiant/rotation et progression présents sur l’Accueil, avec économie/minage et image ; Améliorer ouvre un devis sans achat immédiat ; aucune donnée utile de l’ancienne vue Infrastructure perdue ; budget de caractères et lecture mobile validés.

### 21.3 Économie et confirmations

- **ECO-01 — Achat catalogue/direct** : même objet, coût et gains que l’ancienne voie ; les deux entrées donnent le même devis et nécessitent la confirmation.
- **ECO-02 — Devis périmé** : solde, quantité disponible ou règles de devis changés ; revalidation métier ; pas de prélèvement forcé d’un prix affiché devenu invalide.
- **ECO-03 — Annulation/expiration** : achats, upgrade, convert et compile non exécutés ; mêmes contrôles retirés/désactivés ; résultat de style commun.
- **ECO-04 — Double confirmation** : une seule exécution et un seul log économique ; le deuxième clic est traité comme déjà pris en charge.
- **ECO-05 — Conversion** : taux passé au service identique, soldes exacts, aliases conservés, log une fois.
- **ECO-06 — Autoclaim** : programmer et annuler conservent crédit immédiat éventuel, réservations, remboursements et notifications. Aucune collecte liée au simple envoi de l’embed.
- **ECO-07 — Combo Saver** : bouton disponible seulement selon le résultat, restauration réelle, crédits restants exacts, état ajouté dans l’embed sans dépendre d’un ancien contenu brut.
- **ECO-08 — Échange** : première validation ne transacte pas ; deuxième validation exécute une fois ; refus, solde devenu insuffisant, expiration et participant non autorisé correctement gérés ; MP dans la langue de chaque partie.
- **ECO-09 — Contrat** : offres, actif, prêt et encaissé ont les bons champs ; le MP « terminé » ne crédite pas automatiquement ; fidélité/mission spéciale préservées.
- **ECO-10 — Attestation** : résultat du seuil identique ; aucun solde exact ajouté ; réponse compacte cohérente.
- **ECO-11 — Réputation et bêta** : points, éventuel accès, crédits de parrainage et messages associés préservés ; pas de notification oubliée.

### 21.4 PVP

- **PVP-01 — Niveau 0** : restrictions actuelles de scan/hack conservées ; message parle d’infrastructure. Une belle interface ne rend pas le compte éligible.
- **PVP-02 — Compile** : trois méthodes, valeur/all, prix, quantité et durée actuels ; devis avant confirmation ; paramètres `quoted_*` maintenus ; livraison et log une fois.
- **PVP-03 — Boost scan** : ×1/×2/×5 avec coûts/probabilités actuels ; bon multiplicateur réellement transmis ; coût et échéance effectifs annoncés.
- **PVP-04 — Notifications scan** : succès uniquement au scanner selon le parcours actuel ; échec sans Secret ID ; victime anonyme/identifiée selon les règles ; aucune fuite via network, footer ou log commun.
- **PVP-05 — Exposition** : confirmation explicite, annulation possible avant publication, publication une fois ; garder secret ne publie rien.
- **PVP-06 — Hack** : cible résolue depuis Secret ID, zone et ATK, éligibilité et représailles actuelles ; mêmes points réservés et même délai effectif.
- **PVP-07 — Résolutions** : intrusion refusée, intrusion obtenue avec capture minage, destruction attaque, zone vide, DEF partiellement endommagés et résultat multi-modules. Comparer données transactionnelles identiques ; textes rendent les conséquences exactes.
- **PVP-08 — Infrastructure intacte** : contribution défensive conservée et indestructibilité actuelle maintenue ; aucun effet de patch, logiciel ou spécialisation V2 ajouté.
- **PVP-09 — MP fermé** : politique de chaque notification conservée ; aucune conversion automatique d’un rapport privé en rapport public.
- **PVP-10 — Reprise du bot** : les livraisons différées rattrapées utilisent les nouveaux gabarits sans double règlement ni perte des paramètres d’origine.

### 21.5 Défis, langues et sorties transversales

- **GEN-01 — Sept défis** : consulter, mauvaise réponse, victoire, cooldown individuel/global et entrée invalide pour chacun ; puzzle exact, récompense et résultat identiques.
- **GEN-02 — Signal collectif** : différents joueurs peuvent répondre selon le fonctionnement communautaire actuel ; pas de restriction propriétaire importée depuis network.
- **GEN-03 — Défi déjà résolu** : les anciens messages conservent jeu/langue et deviennent un état final cohérent, sans boutons actifs ; trace de victoire une fois.
- **GEN-04 — Deux langues** : aide, devis, erreur, confirmation, résultat et MP en FR/EN ; préférence stockée prioritaire ; aucune variable brute ni clé manquante.
- **GEN-05 — Préfixe personnalisé** : instructions de reprise et exemples utilisent le préfixe effectif ; slash utilise `/` ; alias existants toujours compris.
- **GEN-06 — Rappels** : MP réussi puis MP fermé avec repli salon et mention existante ; heure, ID et texte exacts ; aucune nouvelle publication d’un résultat PVP privé.
- **GEN-07 — Emojis** : noms résolus au bon ID, cinq versions animées utilisées ; absence d’emoji déclenche un repli propre, pas une chaîne technique visible.
- **GEN-08 — Public/blockchain** : informations actuelles conservées, pas de secret supplémentaire, mêmes montants et mentions nécessaires.
- **GEN-09 — Utilitaires** : maths, ping, invite, botinfo, language, prefix et aide conformes ; calculateur AST inchangé.
- **GEN-10 — Erreurs globales** : syntaxe, accès, compte absent, maintenance et exceptions de transport donnent une réponse cohérente ; pas de trace technique exposée.

### 21.6 Contrôles automatiques pertinents

Le fichier `tests/test_suite.py` utilise `unittest` et se lance directement. Dans l’environnement Python du projet, la commande de référence est `python tests/test_suite.py`. Sur le poste Windows actuel, si le venv est utilisable, `.venv\Scripts\python.exe tests\test_suite.py`. Adapter le chemin au poste de l’implémenteur, ne pas installer de nouveau framework uniquement pour ce plan.

Commencer par les classes proches du changement, puis exécuter la suite complète après conversion. Repères existants à inspecter : `TestRootEmbedDesign`, `TestInternationalization`, `TestNetworkQOL`, `TestBuyCatalogAndShop`, `TestRemainingBalancesInQuotes`, `TestCompile`, `TestScanFeature`, `TestPvPFeature`, `TestPvPPrefixCommand`, `TestMiningClaimAndWelcome`, `TestMiniGameSharedLayer`, `TestTradeSystem`, `TestAutoclaimFeature`, `TestHourlyAndModeration`, `TestContracts`, `TestReminders`, `TestHelpSystem` et `TestFirewallReworkHotfix`.

Ces noms sont ceux du dépôt inspecté ; le terme firewall dans une classe de tests interne ne viole pas la nouvelle terminologie joueur. Les tests fixant les anciennes couleurs, emojis ou textes doivent évoluer vers la nouvelle spécification, sans modifier les assertions de coût, état de compte, droits et résultats.

Ajouter seulement les tests qui protègent un risque réel de cette refonte : comparaison des données entre vues, quantité récoltée au clic concurrent, absence de nouvelles informations privées, expiration cohérente, traduction des notifications, validité des budgets de caractères et mapping des six images. Éviter de tester uniquement qu’une méthode appelle son helper ou de recopier chaque ligne du template attendu.

La recherche de termes hérités doit inclure `firewall`, `pare-feu`, `parefeu` et les libellés `FW` dans les chaînes de rendu. Il ne faut pas exiger leur disparition des calculs, chemins historiques ou clés SQL : le contrôle concerne le texte final destiné au joueur. La matrice des chemins de sortie doit détecter les sends bruts qui échappent encore aux gabarits.

### 21.7 Preuves visuelles à livrer

Conserver dans un dossier de recette documentaire, par exemple `design/graphic-update-qa/`, les captures réelles de référence suivantes : les six niveaux d’Accueil fusionné avec l’infrastructure, les trois détails network Ferme/Matériel/Opérations avec leur illustration, une page d’Opérations détaillant plusieurs tiers ATK/DEF, une boutique/catégorie, un devis upgrade, un devis achat, un résultat claim, une erreur, une annulation/expiration, un rapport PVP attaquant/victime, un succès scan privé, un mini-jeu actif puis résolu, un MP de livraison et une aide. La navigation complète et la conservation de l’image sur les quatre vues doivent être démontrées.

Couverture minimale : parcours complet en FR et contrôles représentatifs en EN ; Accueil/Matériel/devis/mini-jeu sur mobile ; Accueil et message d’alerte en thèmes clair et sombre. Les captures doivent identifier le scénario sans afficher de vrai Secret ID de production ou d’autres informations privées réelles.

Indiquer pour chaque capture le client testé, la langue, le scénario et l’état du compte de test. Ne pas remplacer ces preuves par la capture d’une page HTML simulant Discord. Une maquette peut guider le design, mais seule la capture native vérifie les positions, retours de lignes et animations réels.

## 22. Organisation du travail pour le futur implémenteur

### 22.1 Avant tout changement de bot

1. Lire `instruction_for_agent.md` et ce plan. Le projet indique « no git on this » ; respecter ce contexte au lieu de créer par défaut une branche ou un workflow de PR.
2. Vérifier les fichiers et signatures actuels : ils peuvent évoluer entre cette transmission et l’implémentation.
3. Consigner la baseline de tests et quelques captures actuelles. Un échec déjà présent doit être distingué d’une régression introduite par la refonte.
4. Construire la matrice de couverture des sorties joueurs ; répertorier audience, langue, template, vue, état et callback.
5. Résoudre les ressources réellement accessibles au bot de développement, sans nouvel import ou configuration de production implicite.

### 22.2 Déroulement des lots avec dépendances

**Lot 0** produit les éléments de cadrage ci-dessus et l’association effective des ressources. **Lot 1** utilise des données fixtures et les composants Discord existants pour vérifier la charte ; il ne change pas les règles ni ne lance d’opérations sur des comptes réels.

**Lot 2** crée les fondations compatibles. À sa fin, une commande non convertie doit encore fonctionner ; la nouvelle charte peut être utilisée par les prototypes et les erreurs centrales. Les helpers de présentation ne créent pas d’appel SQL caché.

**Lot 3** remplace `/network`, ajoute au besoin la lecture des attaques sortantes et installe les parcours d’action vers les devis. Vérifier tout particulièrement compte neuf, image, navigation et récolte avant de convertir le reste.

**Lot 4** convertit les commandes économiques par petits groupes, sans changer leur service. Un groupe inclut toujours son devis, résultat, erreurs et MP ; ne pas reporter indéfiniment les notifications différées après la conversion principale.

**Lot 5** convertit le PVP avec des fixtures de résolution contrôlées. Les messages d’attaquant, victime et exposition sont vérifiés séparément. Ce lot n’est pas l’occasion de résoudre l’équilibrage discuté dans les anciennes propositions.

**Lot 6** convertit les défis, tracker, rappels et utilitaires ; vérifie sorties publiques et présence. **Lot 7** reprend la matrice complète, collecte les preuves, exécute la suite, prépare le changelog et les instructions de livraison.

La numérotation donne l’ordre des dépendances, pas une estimation de jours. Fournir une estimation seulement après inventaire et prototypes, plutôt que promettre un délai sans connaître le nombre exact de chemins à convertir.

### 22.3 Éléments à renseigner lors de la réalisation

Les informations suivantes ne sont pas présentes dans le dépôt inspecté et doivent être vérifiées par l’implémenteur : IDs et accessibilité des emojis importés, serveur/canal de recette, possibilité de tester les clients mobile et thème clair, versions effectivement installées et mode de déploiement existant. Ces vérifications ne justifient pas de modifier dès maintenant la base, les secrets ou les règles du jeu.

Si un accès manque, terminer les builders, fixtures et tests indépendants, puis signaler précisément quelle vérification native reste à effectuer. Ne pas déclarer validée l’animation des emojis ou la livraison d’images simplement parce que le fichier existe.

### 22.4 Livraison et retour arrière

Le changelog explique en langage joueur le nouveau poste de commande, la progression infrastructure, les illustrations, les nouveaux styles, les notifications et la navigation. Il ne présente pas l’ancienne PVP V2 comme livrée. Le changement de terme doit être expliqué : mêmes niveaux/effets, nouvelle identité de progression.

La version livrée doit inclure les ressources de diffusion ou sources utilisées et le mapping des emojis, ainsi que les nouvelles chaînes de langue. Les pièces jointes ne doivent pas dépendre du chemin absolu `C:\Users\Juels\Desktop\root bot` : résoudre les chemins depuis la racine du projet, compatible avec l’hôte de production.

Prévoir le retour à la version précédente du code et des assets selon le mécanisme existant. L’absence de migration SQL permet de préserver les comptes sans reconversion. Ne pas promettre de réactiver d’anciens boutons : les joueurs rouvrent les commandes après redémarrage. Les jobs métier continuent selon leur livraison actuelle, quelle que soit la version des anciens embeds déjà envoyés.

La préparation des fichiers et la recette ne supposent pas une autorisation de publier automatiquement en production. La procédure de mise en ligne reste celle du projet et du commanditaire.

## 23. Checklist finale de transmission et définition de terminé

### 23.1 Ce que le concepteur transmet ici

- Objectif, scope et décisions du commanditaire explicites.
- Alternatives de navigation documentées, avec A comme référence détaillée.
- Six infrastructures et six chemins d’illustration.
- Registre sémantique de tous les emojis, distinction animé/statique et politique d’absence.
- Palette, structure et budgets des gabarits.
- Contenu/ordre des quatre vues, fusion de l’infrastructure dans l’Accueil, détail ATK/DEF dans Opérations, comportement des contrôles et entrées de devis.
- Sources de données, nomenclature historique et extension de lecture autorisée.
- États d’interaction et conditions de conservation du jeu actuel.
- Cahier de rendu par commande, MP, erreur et sortie publique.
- Responsabilités des fichiers, frontières des services et absence de migration SQL prévue.
- Scénarios de recette, références de tests et preuves visuelles à produire.

Ce document décrit le travail à réaliser. Les captures de recette, mapping Discord réel, nouveaux modules et modifications de commandes mentionnés ci-dessus n’existent pas du seul fait que ce plan les nomme.

### 23.2 Conditions toutes nécessaires pour terminer l’implémentation

- [ ] La matrice des affichages joueurs est complète ; chaque ligne a un template et un état final vérifiés.
- [ ] Aucun nouveau message joueur ne réintroduit le terme firewall/pare-feu ou un libellé compact FW.
- [ ] Les six niveaux correspondent aux bons noms et images, visibles sur les quatre vues network et leurs pages, sans illustration sur les autres commandes.
- [ ] Les quatre vues Accueil/Ferme/Matériel/Opérations sont navigables dans le même message ; aucune cinquième vue Infrastructure et toutes les données utiles historiques restent accessibles.
- [ ] L’Accueil intègre protection, accès/bonus, identifiant/rotation, progression et bouton Améliorer ; Opérations détaille les modules ATK/DEF par tier avec unités et totaux exacts.
- [ ] Récolter, boutique, upgrade, compilation, scan et attaque réutilisent les services et validations actuels.
- [ ] Les rapports actuels PVP, y compris cas partiels et multi-modules, sont exacts ; aucun mécanisme V2 ajouté.
- [ ] Devis, annulations, expirations, erreurs, MP, anciens panneaux de défi et annonces publiques suivent la même charte.
- [ ] Les quantités, devises, débits, mémoire et bonus restent corrects ; aucun double bonus ou double crédit introduit.
- [ ] Les règles de confidentialité et de mentions sont préservées dans les messages initiaux, edits, followups et replis.
- [ ] FR et EN sont cohérents et complets ; les préfixes réels et paramètres de commande sont conservés.
- [ ] Les emojis réellement utilisés sont résolus et les cinq noms concernés affichent leur version animée.
- [ ] Les limites Discord sont respectées pour grands stocks, longues traductions et nombreuses opérations.
- [ ] Les scénarios de concurrence, accès tiers, expiration et reprise du bot sont validés.
- [ ] Les tests appropriés et la suite existante ont été exécutés ; les échecs persistants sont documentés.
- [ ] Les captures natives desktop/mobile et thèmes nécessaires sont livrées et relues.
- [ ] `CHANGELOG.md`, dépendances éventuelles de ressources et instructions de livraison sont à jour.
- [ ] Aucune règle économique ou SQL n’a changé sous couvert de graphisme.

Le livrable final de l’implémenteur doit citer les fichiers modifiés, résumer ce que le joueur voit, donner les résultats des tests et les liens vers les preuves visuelles, puis nommer toute limitation restante. « Les embeds sont harmonisés » sans couverture des notifications et états secondaires n’est pas une livraison complète.
