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
  - Les actions simples comme la récolte (`/claim`) s'affichent sous forme de messages directs et aérés plutôt que d'embeds encombrants.
  - Les erreurs de jeu, annulations de confirmation et expirations restent en messages textuels épurés.
- **Harmonisation stricte des messages de délai** :
  - Structure symétrique et identique pour tous les messages de cooldown et d'attente (prime horaire `/hourly`, récolte `/claim`, réputation `/rep`) :
    `> {root_temps} **Délai insuffisant** · [Raison concise]. Reviens dans / Prochaine récolte dans **[durée]**.`
- **Remplacement exhaustif des emojis vanilla** :
  - Toutes les commandes utilisent désormais exclusivement les 17 emojis personnalisés de Root OS.
  - Couverture étendue incluant les indicateurs de statut, progression, alertes, débits et mémoires.
