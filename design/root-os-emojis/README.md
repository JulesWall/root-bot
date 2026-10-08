# Emojis Root OS

19 PNG transparents en 128 x 128, adaptés à la charte ROOT OS et lisibles en petit dans Discord.

## Fichiers

- `png/` : images à importer dans Discord. Un fichier par emoji.
- `apercu.png` : planche de presentation, avec un exemple a 32 pixels pour chaque symbole.
- `manifest.json` : noms, usages, couleurs, dimensions, poids et sources.
- `sources-svg/` : sources vectorielles pour régénérer les pictogrammes.
- `build_custom_emojis.py` : régénère les deux nouveaux emojis ROOT OS, leurs PNG, le manifeste et l’aperçu.
- `LICENSE-LUCIDE.txt` : licence et attribution a conserver lors du partage du pack.

## Import

Dans les parametres de ton serveur Discord, ouvre la rubrique des emojis et importe les fichiers de `png/`. Conserve les noms de fichiers comme noms d'emojis, par exemple `root_firewall`.

Pour les utiliser dans les textes du bot, la syntaxe est `<:root_firewall:ID_DISCORD>` : Discord fournit l'identifiant apres import. Les boutons utilisent le meme emoji personnalise via leur propriete `emoji`. Les fichiers locaux seuls ne suffisent pas : il faut d'abord les importer. Aucun import et aucune modification du bot n'ont ete effectues par ce pack.

## Nouveaux pictogrammes ROOT OS

- `root_verrou` : profil protégé par un bouclier et un cadenas ; violet réservé aux dégâts critiques.
- `root_usd` : pièce avec symbole dollar pour les rémunérations en USD.

Ces deux nouveaux dessins sont des sources vectorielles originales, réalisées dans la même grammaire de traits que le pack existant. Exécuter `build_custom_emojis.py` avec Pillow disponible pour recréer les images et la planche d’aperçu.

## Direction visuelle

Turquoise `#54E2D1` pour les informations du réseau, blanc `#EEF1F5` pour les actions, ambre `#FFC15A` pour les alertes et violet `#B66DFF` pour le verrouillage critique. Les 17 icônes initiales sont des pictogrammes Lucide recolorés ; les deux ajouts sont des dessins ROOT OS originaux cohérents avec ce style.

Sources : [Lucide](https://lucide.dev), version 0.468.0 ; [contraintes Discord](https://support.discord.com/hc/en-us/articles/360041139231-How-to-Add-Emojis-on-Discord).
