# Beta Update 2 : Hotfix #4

### Ajouts & Nouveautés
- **Calculatrice** : La commande est désormais `/maths` et `!maths` (`!math` reste un alias valide).
- **Cyberattaques PvP — Pillage multi-modules (`/hack` & `!hack`)** :
  - Lorsque l'ATK dépasse la DEF ennemie au-delà d'un seuil calculé selon ton tier de pare-feu, l'attaque capture désormais **plusieurs modules** d'un coup (1 de base + 1 par multiple du seuil dépassé), du tier le plus haut au plus bas.
  - L'attaquant reçoit un DM de debug avec le détail complet du calcul (ATK, DEF, delta, seuil V(T), modules pris).
  - La quantité de points d'attaque engagés est désormais masquée dans les annonces du salon de logs publics pour préserver le secret stratégique.
- **Achat de modules — Nouvelle syntaxe (`/buy` & `!buy`)** :
  - **Quantité** : précise un nombre pour acheter plusieurs modules en une transaction — `!buy defense 3 20 confirm` achète 20x défense T3.
  - **Mot-clé `all`** : `!buy mining 1 all confirm` (ou `/buy count:all`) achète automatiquement le **maximum de modules que tu peux te payer** avec ton solde.
