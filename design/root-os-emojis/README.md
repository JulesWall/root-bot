# Emojis Root OS

17 PNG transparents en 128 x 128, adaptes au theme sombre de la maquette.

## Fichiers

- `png/` : images a importer dans Discord. Un fichier par emoji.
- `apercu.png` : planche de presentation, avec un exemple a 32 pixels pour chaque symbole.
- `manifest.json` : noms, usages, couleurs, dimensions, poids et sources.
- `sources-svg/` : vecteurs Lucide originaux, pour regenerer d'autres tailles.
- `LICENSE-LUCIDE.txt` : licence et attribution a conserver lors du partage du pack.

## Import

Dans les parametres de ton serveur Discord, ouvre la rubrique des emojis et importe les fichiers de `png/`. Conserve les noms de fichiers comme noms d'emojis, par exemple `root_firewall`.

Pour les utiliser dans les textes du bot, la syntaxe est `<:root_firewall:ID_DISCORD>` : Discord fournit l'identifiant apres import. Les boutons utilisent le meme emoji personnalise via leur propriete `emoji`. Les fichiers locaux seuls ne suffisent pas : il faut d'abord les importer. Aucun import et aucune modification du bot n'ont ete effectues par ce pack.

## Direction visuelle

Turquoise `#54E2D1` pour les informations du reseau, blanc `#EEF1F5` pour les actions, ambre `#FFC15A` pour les alertes. Les formes sont des pictogrammes Lucide recolores, et non des dessins originaux generes par IA. Les icones de la maquette etaient indicatives : ce pack fournit leurs equivalents coherents et reproductibles.

Sources : [Lucide](https://lucide.dev), version 0.468.0 ; [contraintes Discord](https://support.discord.com/hc/en-us/articles/360041139231-How-to-Add-Emojis-on-Discord).
