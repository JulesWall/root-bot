# Changelog — Mises à jour Root OS

## [Graphismes & Interface] — Cohérence visuelle & Emojis personnalisés Root OS

- **Suppression des embeds superflus** : Les messages qui n'étaient pas des embeds (erreurs de jeu, annulations de devis, messages d'information simples) sont désormais envoyés sous forme de texte clair et élégant, évitant l'encombrement visuel des embeds répétitifs.
- **Remplacement complet des emojis vanilla** : Fin des emojis standards génériques. Toutes les commandes et notifications affichent désormais les 17 emojis personnalisés créés pour Root OS (terminal animé, alerte animée, récolte animée, radar de scan animé, retour animé, ainsi que les icônes dédiées de ferme, puissance, production, mémoire, bilan, matériel, etc.).
- **Cohérence esthétique globale** : Harmonisation de la typographie, de la hiérarchie visuelle et de la ponctuation entre tous les messages et écrans du bot.

## [Poste de Commande V2] — `/network`

- **Interface Discord Components V2** : Tableau de bord central unifié avec conteneurs interactifs et barre latérale d'état.
- **Illustration panoramique au sommet** : La scène d'infrastructure correspondant au niveau actuel du joueur est affichée en tête de carte via MediaGallery.
- **Boutons intégrés directement dans la carte** :
  - **Récolte dynamique** : Bouton vert actif dès qu'il y a du Rootium en mémoire tampon, ou grisé si vide.
  - **Matériel** : Bascule instantanément vers l'inventaire complet des modules par tier.
  - **Actualiser** : Rafraîchit les statistiques et débits en temps réel avec l'icône de temps Root OS.
- **Navigation fluide** : Déplacement interactif entre les vues Accueil, Matériel et Opérations sans quitter le message initial.
