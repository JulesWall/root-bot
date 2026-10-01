# Changelog — Mises à jour Root OS

## [Graphismes & Interface] — Cohérence visuelle & Emojis personnalisés Root OS

- **Suppression des embeds superflus** : Les messages qui n'étaient pas des embeds (erreurs de jeu, annulations de devis, messages d'information simples) sont désormais envoyés sous forme de texte clair et élégant, évitant l'encombrement visuel des embeds répétitifs.
- **Remplacement complet des emojis vanilla** : Fin des emojis standards génériques. Toutes les commandes et notifications affichent désormais les 17 emojis personnalisés créés pour Root OS (terminal animé, alerte animée, récolte animée, radar de scan animé, retour animé, ainsi que les icônes dédiées de ferme, puissance, production, mémoire, bilan, matériel, etc.).
- **Cohérence esthétique globale** : Harmonisation de la typographie, de la hiérarchie visuelle et de la ponctuation entre tous les messages et écrans du bot.

## [Poste de Commande V2] — `/network`

- **4 Vues Complètes Disponibles** :
  - **Accueil** : Vue d'ensemble du réseau, identité, statistiques clés, infrastructure et progression.
  - **Ferme** : Débits de minage en temps réel, jauge mémoire vive, détail des mineurs par tier et automatisation.
  - **Matériel** : Inventaire exhaustif des baies (Minage, Attaque, Défense) regroupé par tier et accès boutique.
  - **Opérations** : Stock offensif, statut de compilation/scans, attaques en cours et droits de représailles.
- **Interface Discord Components V2** : Rendu visuel soigné dans un conteneur unifié avec bordure d'accentuation (turquoise/ambrée).
- **Illustration panoramique au sommet** : La scène d'infrastructure du joueur est intégrée en tête de conteneur via MediaGallery.
- **Barre d'actions à 2 rangées intégrée dans le conteneur** :
  - **Rangée 1 (Onglets de navigation)** : 3 boutons permettant de basculer instantanément vers les autres vues depuis n'importe quel onglet.
  - **Rangée 2 (Actions rapides)** : Bouton *Récolter* dynamique (vert avec solde prêt ou grisé si vide) et bouton *Actualiser* opérationnels depuis toutes les vues.

## [Cohérence & Esthétique des Messages]

- **Suppression des embeds superflus** :
  - Les actions instantanées comme la récolte (`/claim`) et la prime horaire (`/hourly`) s'affichent sous forme de messages directs et aérés avec boutons intégrés plutôt que d'embeds encombrants.
  - Les erreurs de jeu, annulations de confirmation et expirations restent en messages textuels épurés.
- **Harmonisation stricte des messages de délai** :
  - Structure symétrique et identique pour tous les messages de cooldown et d'attente (prime horaire `/hourly`, récolte `/claim`, réputation `/rep`, contrats `/contract`, mini-jeux) :
    `> {root_temps} **Délai insuffisant** · [Raison concise]. Reviens dans **[durée]**.`
  - Alignement des styles, de la ponctuation et du tutoiement sur l'ensemble des commandes.
- **Remplacement exhaustif des emojis vanilla & gestion des sélecteurs de variante** :
  - Prise en charge universelle des variations Unicode (avec et sans variation selector `\ufe0f`), éradiquant les emojis standards résiduels.
  - Toutes les commandes et panneaux de secours (`/network`, `/top`) utilisent désormais exclusivement les 17 emojis personnalisés de Root OS.
  - Boutons interactifs du classement `/top` équipés des icônes Root OS dédiées.

## [Refonte des Embeds — Style Cyber Terminal]

- **En-tête Auteur Unifié** : Chaque embed affiche désormais en en-tête `ROOT OS // <PSEUDO>` accompagné de l'avatar du joueur (ou de l'icône système), conférant à toutes les commandes la signature visuelle du poste de commande `/network`.
- **Titres Stylisés avec Emojis Root OS** : Les titres d'embeds sont dynamiquement préfixés par l'icône animée ou statique dédiée à l'action (`root_materiel`, `root_firewall`, `root_operations`, `root_scan`, `root_bilan`, `root_puissance`, `root_terminal`).
- **Harmonisation Chromatique Cyberpunk** : Remplacement des couleurs génériques par la palette officielle de Root OS : Turquoise cyber (`#54E2D1`), Ambre d'alerte/devis (`#FFC15A`) et Rouge d'intrusion/perte (`#F06A6A`).
- **Nettoyage et Filtrage Intégrés** : Le corps des embeds et les devis interactifs filtrent et convertissent automatiquement tout emoji résiduel vers les emojis Root OS.

## [Système de Rappels & Temporisateurs] — `/rmd` & Notifications

- **Correction de la double délivrance** : Suppression de l'envoi simultané du texte brut et de l'embed redondant lors de la réception des rappels en message privé (MP) ou sur le salon de repli.
- **Icônes Thématiques Root OS** : Les rappels et temporisateurs utilisent désormais l'icône de temporisation dédiée `root_temps` (`⏱️`) plutôt que des icônes d'alerte rouge (`🔔`) ou de minage (`✅`).
- **Correction du mappage de validation** : Les coches de confirmation (`✅`, `✓`, `🟢`) sont désormais associées au curseur de terminal Root OS (`root_terminal`) au lieu du sac de récolte de minage.
- **Harmonisation des Libellés** : Alignement des messages de confirmation et de consultation (`/rmd auto`, `/rmd timer`, `/rmd list`, `/rmd cancel`) sur la charte visuelle épurée de Root OS.

