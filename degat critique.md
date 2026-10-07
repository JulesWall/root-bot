# Plan d’implémentation — procédure de dégâts critiques PvP

## Objectif et règles

Lorsqu’une attaque PvP résolue détruirait ou volerait une part excessive des modules de la victime, déclencher une procédure de sauvegarde : limiter la perte au plafond configuré et verrouiller temporairement le profil de la victime.

Pendant le verrouillage, le joueur ne peut ni lancer ni subir de hack, et ne peut pas lancer de scan. Il conserve les autres actions, notamment compiler, acheter des modules et améliorer sa défense. Le verrouillage porte sur le profil, donc s’applique à tous les serveurs.

## Configuration

Ajouter au bloc `pvp` de `data/math.json` deux paramètres, par exemple :

```json
"critical_damage_cap_percent": 60,
"critical_lock_duration_hours": 48
```

Le premier fixe le plafond de modules perdus (valide de 0 à 100). Le second fixe la durée du verrouillage (valeur positive). Les valeurs par défaut proposées ci-dessus sont configurables ; le code doit lire ces réglages via `MathConfig`, sans les dupliquer comme constantes.

## Calcul et plafonnement des dégâts

Dans `PvpDB.resolve_single_attack` (`game/db/pvp.py`), calculer le nombre total de modules possédés dans la catégorie visée, tous tiers confondus, avant d’appliquer le payload :

- cible `attack` : modules d’attaque de la victime ;
- cible `mining` : modules de minage de la victime.

Comparer la perte calculée par l’attaque à ce total. Si la perte prévue dépasse le plafond, déclencher la procédure et limiter la perte à `floor(total_modules × plafond / 100)`. Distribuer cette perte plafonnée selon la règle existante (tiers les plus hauts d’abord). Le calcul ne concerne que les modules d’attaque détruits ou de minage transférés ; les dégâts aux modules de défense de baie ne déclenchent pas cette procédure.

Le plafond est strict : une perte égale au pourcentage configuré ne déclenche pas la procédure ; une perte supérieure la déclenche. Si l’arrondi inférieur donne zéro module autorisé, aucun module de cette catégorie ne doit être perdu lors de cette attaque critique.

## Verrouillage du profil

Ajouter une colonne nullable `critical_lock_until DATETIME(6)` à `players`, dans `root.sql` et dans la migration destinée aux bases existantes. Ajouter le champ à la liste blanche de `UpdatePlayer` dans `game/db/players.py`.

Au déclenchement, enregistrer `tx.now + durée configurée` dans cette colonne. Une date passée signifie que le joueur est à nouveau actif ; aucun nettoyage périodique n’est nécessaire.

Centraliser la vérification dans un helper commun qui renvoie la date d’expiration lorsque le verrou est actif. Ajouter les contrôles :

- dans `Player.hack`, pour refuser un attaquant verrouillé et une cible verrouillée, au devis comme à la confirmation ;
- dans `Player.scan`, pour refuser un scanner verrouillé et une cible verrouillée ;
- à la résolution différée du hack, pour éviter qu’une attaque déjà en vol n’applique des dégâts à une cible dont l’état a changé.

Les opérations déjà lancées par le joueur avant le verrouillage ne sont pas annulées : la protection bloque les nouveaux lancements et les nouvelles attaques contre le profil. Les autres commandes, dont `/compile`, `/buy` et `/upgrade`, restent disponibles.

## Journal public et notifications

Lorsqu’une procédure critique est déclenchée, ajouter un événement dédié dans le salon de logs **public**, depuis le chemin de résolution PvP dans `commands/game/hack.py` et le logger de `utils/logger.py`. Le log est envoyé une seule fois et reste volontairement concis : il annonce qu’une attaque critique a déclenché la protection, identifie la victime verrouillée et indique la durée du verrouillage, avec son heure de fin Discord. Ne pas publier le détail des dégâts, la catégorie visée, le nombre de modules, le pourcentage, l’attaquant ou le Secret ID.

Créer une couleur dédiée `COLOR_LOG_CRITICAL` dans `utils/root_theme.py`, par exemple un violet électrique (`#B66DFF`). Les autres logs publics utilisent actuellement le turquoise (`#54E2D1`), le rouge (`#F06A6A`) et l’ambre (`#FFC15A`) ; le violet tranche nettement tout en restant dans la palette graphique Root OS. Le logger réutilise le gabarit public commun avec cette couleur et un intitulé comme « Procédure de sauvegarde déclenchée ».

Les messages privés de résultat à l’attaquant et à la victime peuvent, eux, détailler les pertes effectivement plafonnées et l’expiration du verrouillage, dans la langue de chaque joueur. Ne jamais publier le Secret ID.

## Ordre d’implémentation

1. Ajouter et valider les réglages PvP dans `data/math.json` et leur lecture dans `game/math_config.py`.
2. Ajouter la colonne de verrouillage au schéma SQL, à la migration existante et à `UpdatePlayer`.
3. Modifier la résolution transactionnelle dans `game/db/pvp.py` : mesurer les modules, détecter le dépassement, plafonner la perte et persister l’expiration.
4. Protéger les chemins `hack` et `scan` dans `game/db/players.py`, avec refus au devis, à la confirmation et au moment pertinent de résolution.
5. Ajouter les messages localisés pour le verrou actif et le rapport critique.
6. Ajouter `COLOR_LOG_CRITICAL` à la palette, puis le log public concis et les détails utiles aux notifications privées.

## Points de cohérence

- Les ratios sont calculés en nombre de modules, et non en puissance ou valeur économique des tiers.
- Le compteur de modules de référence est celui de la catégorie ciblée juste avant l’application de l’attaque.
- La perte du mineur est identique à celle transférée à l’attaquant : le plafonnement doit s’appliquer avant la mise à jour des deux profils.
- Le verrouillage est persistant en base et survit aux redémarrages du bot.
- Le log public indique la victime et la durée de sa protection sans exposer les détails techniques de l’attaque.
- Le log critique utilise une couleur dédiée, distincte des couleurs d’événements, d’attaque et de scan.
