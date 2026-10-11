# Plan de développement — cours dynamique du RTM

## But

Faire évoluer le taux fixe RTM → USD du jeu en un cours qui change toutes les 15 minutes selon la moyenne simple des variations de Bitcoin, Ethereum et Solana. Ajouter une commande de consultation avec un graphique de cours esthétique, des périodes 24 h / 7 j / 30 j, puis des alertes et une vente automatique optionnelle.

Le RTM reste une monnaie interne au jeu. Les cotations externes ne servent qu'à calculer son cours fictif : aucune transaction ne doit être envoyée à un exchange réel.

Ce document est une spécification de conception. Les choix de limite de variation, de rétention et de comportement au démarrage doivent être validés pendant l’implémentation et la simulation d’équilibrage.

## Contexte du dépôt à respecter

- `graphique.md` définit la charte ROOT OS : lisible sur mobile, hiérarchie claire, chiffres et unités explicites, palette par état, pied de page `ROOT OS · Rubrique` et emojis sémantiques existants.
- Le fichier réellement utilisé pour les formules est `data/math.json` (et non `mat.json`). `game/math_config.py` le charge, valide les formules via AST et travaille déjà avec `Decimal`.
- Le taux fixe actuel est `conversion.rtm_to_usd` dans `data/math.json`, actuellement `43567`.
- `MathConfig.rtm_to_usd_rate()` et `MathConfig.convert_rtm_to_usd()` alimentent la vente RTM→USD dans `game/db/players.py` et la commande `commands/game/convert.py`.
- Le calcul du seuil de dégâts PvP dans `game/math_config.py` utilise également le taux RTM→USD. Le passage au cours variable modifiera donc aussi cette formule et potentiellement l’équilibrage PvP.
- Les migrations SQL doivent être inscrites dans `migration.sql`. Une modification livrée doit être résumée dans `CHANGELOG.md`.
- Les commandes de jeu sont généralement exposées en slash et en préfixe, traduites en français et anglais, et rendues avec les helpers d’embed ROOT OS.

## Règle de marché

### Source et cadence

Utiliser la bibliothèque Python **CCXT**, en mode asynchrone (`ccxt.async_support`), pour lire un seul marché cohérent, par exemple Binance au comptant : `BTC/USDT`, `ETH/USDT`, `SOL/USDT`. Vérifier au démarrage que l’exchange prend en charge `fetch_ohlcv` et l’intervalle `15m`.

USDT sert ici de référence de marché approximative pour USD. L’interface et les logs doivent indiquer la source et la devise de cotation. La source choisie doit être configurable dans `data/math.json` afin de pouvoir changer de plateforme ou de paires sans réécrire le moteur.

Exécuter un cycle aligné sur les quarts d’heure UTC, et non une boucle qui dérive de 15 minutes après chaque exécution. Attendre une courte marge après la clôture d’une bougie. Charger suffisamment d’OHLCV pour identifier les deux dernières bougies **clôturées** correspondant à deux intervalles consécutifs. Ne jamais inclure la bougie en cours.

CCXT fournit une interface unifiée OHLCV, mais prévient que la dernière bougie retournée peut être incomplète et que les plateformes imposent des limites de débit. Conserver son rate limiter activé et filtrer explicitement les bougies clôturées. Référence : [manuel CCXT — OHLCV et rate limits](https://github.com/ccxt/ccxt/wiki/Manual).

### Formules à placer dans `data/math.json`

Représenter les variations comme des pourcentages, puis appliquer une moyenne arithmétique à poids égaux :

```text
asset_change_pct = (latest_closed_close / previous_closed_close - 1) * 100
average_change_pct = (btc_change_pct + eth_change_pct + sol_change_pct) / 3
rtm_price_next = rtm_price_current * (1 + average_change_pct / 100)
```

Exemple : BTC `+1 %`, ETH `-1 %`, SOL `0 %` donnent une moyenne de `0 %` ; le cours RTM ne bouge pas durant ce cycle.

Ajouter des clés de configuration pour l’intervalle, les symboles, la source, la devise de cotation, le cours de départ, la précision, la tolérance de retard et, si l’équilibrage le justifie, un plafond de variation par cycle. Un plafond doit être explicite, configurable et simulé avant activation, puisqu’il modifie la moyenne brute demandée.

Utiliser `Decimal` pour les taux, les prix et les calculs financiers. Les formules doivent être évaluées par `MathConfig.formula()` ou par une extension contrôlée de `MathConfig`, jamais via `eval()`.

### Résilience et cohérence

- Si un actif manque, si les bougies ne sont pas clôturées ou si une cotation est trop ancienne : ne pas recalculer le prix. Garder le dernier cours valide, marquer le flux comme retardé et réessayer au prochain cycle.
- Ne pas remplacer une cotation manquante par zéro et ne pas calculer la moyenne sur seulement deux actifs sans règle explicitement approuvée.
- Horodater les fenêtres en UTC et persister les valeurs observées, les trois variations individuelles, leur moyenne, le cours avant/après, la source et l’état du cycle.
- Rendre chaque fenêtre idempotente : une seule mise à jour pour un timestamp de marché. Si plusieurs processus du bot peuvent tourner simultanément, sérialiser le calcul avec verrou MySQL et contrainte unique.
- Au redémarrage, charger le dernier état persistant. Ne pas appliquer plusieurs fois des cycles passés et ne pas compenser le temps d’arrêt en multipliant la variation actuelle.
- Les échecs API doivent être visibles dans les logs de service, sans divulguer d’informations privées aux joueurs.

## Persistance et intégration du prix

Prévoir dans `migration.sql` une structure persistante comprenant au minimum :

1. **État courant** : identifiant singleton, cours RTM/USD, dernier timestamp de cours valide, timestamp d’observation externe, indicateur de fraîcheur.
2. **Historique marché** : un enregistrement par intervalle, avec cours RTM/USD et les variations BTC, ETH, SOL et moyenne. Ajouter une contrainte unique sur le timestamp UTC.
3. **Alertes** : joueur, seuil, sens du déclenchement, période de réarmement, état activé et date de dernière notification.
4. **Ventes automatiques** (phase ultérieure) : joueur, seuil et sens, quantité fixe ou règle de solde, état activé, limites et dernière exécution. Ajouter une clé d’idempotence d’exécution.

La rétention doit couvrir au moins les graphiques mensuels et les alertes. Les 30 jours représentent 2 880 points à 15 minutes, volume raisonnable ; fixer une rétention supérieure (par exemple 90 jours) puis purger les données plus anciennes selon une tâche planifiée. Les historiques plus longs ne sont pas requis pour la première version.

Adapter `MathConfig.rtm_to_usd_rate()` pour retourner le cours courant persistant, avec un comportement défini en cas de base indisponible. Conserver `data/math.json` comme source des paramètres et formules, et une valeur d’amorçage pour initialiser la nouvelle table à `43567` pendant la migration ou le premier lancement.

Vérifier explicitement les conséquences sur :

- `commands/game/convert.py` et `PlayerData.convert()` : le devis doit afficher le cours utilisé ; la confirmation doit refuser le devis si le cours a changé depuis sa création, ou appliquer une politique de verrouillage du devis avec durée d’expiration.
- Le seuil PvP qui dépend du taux de conversion : décider si l’équilibrage PvP suit le cours courant ou s’il doit rester référencé à un taux de base indépendant.
- Tous les autres affichages de conversion et les traductions FR/EN.

## Graphique : architecture sans rendu à chaque consultation

Séparer strictement quatre opérations : collecte du marché, calcul et stockage du cours, préparation des séries graphiques, envoi ou édition du message Discord. Une interaction avec `/market` ou un bouton de période ne doit **jamais** rappeler l’API crypto.

### Niveau 1 — aperçu léger, affiché sans fichier image

Afficher dans l’embed principal un cours actuel, la variation choisie et un mini-sparkline en caractères Unicode (par exemple blocs `▁▂▃▄▅▆▇`). Ce résumé n’a pas besoin de PNG, évite le rendu graphique et ne transfère aucune image. Réduire les séries longues à une largeur fixe d’environ 24 à 40 points pour ce sparkline.

Ce premier écran doit déjà avoir une identité visuelle ROOT OS : « terminal de marché », statut du flux, nom de la période, dernière mise à jour et source. Prévoir une version textuelle de la tendance qui reste compréhensible si les glyphes ne s’affichent pas bien sur un appareil.

### Niveau 2 — graphique détaillé sur demande

Ne créer l’image détaillée que lorsque le joueur ouvre le graphique ou demande une période. Générer à partir de l’historique MySQL, jamais en récupérant de nouvelles données externes. Mettre le résultat en cache sur disque avec une clé comprenant : période, timestamp du dernier point inclus, version du thème, dimensions et format.

Pour une même clé, une génération au maximum. Les demandes concurrentes pour la même clé doivent attendre la même génération. La période mensuelle peut être réduite à environ 700–1 000 points pour un rendu de 1 000 pixels de large, à l’aide d’un algorithme de préservation de forme (LTTB ou enveloppe min/max par tranche) : cela limite le poids visuel tout en gardant les pics importants.

**Nuance de coût à garder en tête :** mettre un PNG en cache supprime son recalcul, mais si le fichier est joint à chaque réponse Discord, les octets sont quand même transférés. La version initiale doit donc limiter les images envoyées : aperçu sparkline sans image par défaut, PNG seulement sur action explicite de l’utilisateur, image compressée et dimensions raisonnables. Mesurer la taille réelle avant de choisir une limite. Ne pas annoncer que le cache disque supprime le trafic Discord.

Les interactions de période doivent répondre vite depuis l’historique et le cache. Les sélecteurs Discord permettent de modifier l’interface, mais les boutons d’un message public ont un état partagé : ne pas laisser un joueur modifier silencieusement la période affichée à tout le serveur. Utiliser une réponse éphémère pour le graphique personnel ou un message personnel distinct.

### Stratégie d’évolution si le trafic devient important

Instrumenter le nombre de rendus cache-hit/cache-miss, le temps de rendu, la taille médiane des fichiers envoyés et le nombre d’interactions graphiques. Si les uploads deviennent coûteux, choisir ensuite l’un de ces modèles après mesure :

- panneau public partagé, mis à jour seulement à chaque nouveau cours, avec un aperçu 24 h fixe et commande séparée pour consulter les périodes longues ;
- assets de graphiques hébergés par un service web contrôlé et référencés par URL, si un hébergement stable et accessible est déjà disponible ;
- conserver l’aperçu texte comme affichage par défaut et n’envoyer une image que sur demande.

Ne pas réutiliser un URL CDN d’une pièce jointe Discord comme stockage permanent sans vérifier sa durée de validité et le comportement de cache de Discord. Le cache de fichiers applicatif est le choix fiable pour le premier lancement.

## Direction artistique du graphique détaillé

L’image doit ressembler à un écran premium de ROOT OS, plutôt qu’à un graphique financier par défaut.

### Composition proposée

- Format paysage autour de 1 000 × 560 px, haute résolution pour lecture mobile, export PNG optimisé. Le format doit être ajusté après aperçu dans l’embed Discord réel.
- Fond charbon/bleu-noir inspiré de Discord, avec panneau visuel sobre ; pas de fond blanc ni de boîte graphique Matplotlib standard.
- En-tête court : `ROOT OS / MARCHÉ`, cours actuel RTM/USD clairement dominant, variation de la période et petit état du flux (`ACTIF` ou `RETARD`).
- Graphique principal : une ligne turquoise ROOT OS nette, marqueur sur le dernier point, zone sous la courbe très subtile, grille horizontale discrète et axes peu nombreux. Garder la série réellement mesurée : ne pas lisser les données d’une façon qui masquerait les variations.
- Résumé compact sous la courbe : rendements BTC, ETH et SOL sur le dernier cycle, pour expliquer le mouvement du RTM sans superposer leurs prix incomparables à l’échelle du graphique.
- Pied de visuel : période affichée, source de prix, horodatage UTC ou heure locale clairement identifiée.

La palette ROOT OS est prioritaire : turquoise `#54E2D1` pour le cours, ambre `#FFC15A` pour un flux retardé ou un signal d’attention, rouge `#F06A6A` uniquement pour une erreur bloquante et blanc cassé `#EEF1F5` pour les libellés. Toujours écrire le signe et la valeur (`+0,42 %`) : la couleur ne doit pas être le seul moyen de comprendre la tendance.

### Échelles et lisibilité

- X : 24 h avec heures, 7 j avec jours, 30 j avec dates ; limiter à 4–6 repères lisibles.
- Y : prix en USD/RTM avec format français dans l’interface ; préserver une échelle adaptative avec marge, mais afficher les valeurs d’axes pour ne pas exagérer visuellement les mouvements.
- En-tête de l’embed : variation totale de la période, calculée entre le premier et le dernier point réellement affiché, avec formule identique quelle que soit la période.
- Si une période contient des trous de données, laisser un espace ou indiquer le flux incomplet au lieu de relier les points comme s’il s’agissait de données continues.
- La ligne principale représente uniquement RTM. Les trois cryptoactifs de référence apparaissent en valeurs de variation séparées, jamais sur la même échelle de prix.

Matplotlib convient pour ce PNG et permet de contrôler les styles, les dates, les grilles et les zones remplies. Éviter d’appliquer `dark_background` sans personnalisation : définir explicitement chaque couleur ROOT OS. Exemples de référence : [styles Matplotlib](https://matplotlib.org/stable/api/style_api.html), [galerie Matplotlib](https://matplotlib.org/stable/gallery/) et [formatage des axes temporels](https://matplotlib.org/stable/gallery/ticks/date_concise_formatter.html).

Effectuer le rendu hors de la boucle événementielle Discord (par exemple `asyncio.to_thread`) ou le préchauffer en tâche de fond sur cache-miss. Fermer la figure après export et optimiser les PNG. Ne jamais exécuter un rendu Matplotlib lourd dans le callback synchrone d’un bouton.

## Interface Discord proposée

Ajouter `/market` (et l’équivalent préfixé selon les conventions du projet), avec :

1. **Vue par défaut** : embed ROOT OS de consultation, cours courant, variation 15 min, mini-sparkline texte, contributions BTC/ETH/SOL, fraîcheur, boutons `24 h`, `7 j`, `30 j`, `Graphique` et `Alertes`.
2. **Sélection de période** : met à jour la réponse propre au joueur et peut afficher le détail en PNG depuis le cache. Ne pas envoyer de message public nouveau à chaque clic.
3. **Graphique détaillé** : image PNG sur demande, accompagnée d’un résumé textuel du premier/dernier prix, de la variation et de l’heure des données.
4. **Alertes** : modal pour saisir le seuil ; choix du sens et activation/désactivation par composants. Vérifier les limites et empêcher les alertes identiques en doublon.
5. **Erreurs** : message d’état compréhensible, couleur ambre si données retardées, aucune fausse indication de prix « temps réel ».

Pycord 2.8 documente les sélecteurs, boutons, modals et Components V2. Les Components V2 permettent des layouts plus immersifs avec `DesignerView`, `Container`, `Section`, `TextDisplay`, séparateurs et composants média. Ils ne doivent pas être mélangés à un embed classique dans un même message. Recommandation : première version en embed + `discord.ui.View`, afin de réutiliser le système visuel actuel et de garder l’image attachée ; évaluer séparément un écran Components V2 après validation du premier parcours. Références : [Pycord UI Kit 2.8](https://docs.pycord.dev/en/v2.8.0/api/ui_kit.html) et [Interactions Discord](https://github.com/discord/discord-api-docs/blob/main/developers/platform/interactions.mdx).

## Alertes et vente automatique

### Alertes (phase après le graphique)

Les alertes doivent être persistantes, indépendantes des vues temporaires Discord et évaluées juste après l’enregistrement d’un nouveau cours. Prévoir un sens (au-dessus/en dessous), un seuil, un cooldown/réarmement et un verrou idempotent. Envoyer un DM si possible ; si les DM sont fermés, garder l’alerte consultable depuis `/market`. Éviter le spam à chaque quart d’heure tant que le seuil reste franchi.

### Vente automatique (phase séparée et explicitement activée)

Réutiliser le service métier de `PlayerData.convert()` plutôt que créer une seconde logique de débit/crédit. Permettre une quantité fixe ou un pourcentage/solde maximum, une limite par exécution, un cooldown, la désactivation immédiate, un reçu après vente et une exécution atomique exactement une fois. Le déclenchement peut être une seule fois par seuil ; le réarmement et les ventes répétées doivent être des choix visibles.

Ne jamais vendre à un taux ancien : au moment du déclenchement, lire le dernier cours valide et enregistrer ce taux dans la transaction. Définir explicitement le comportement si le flux est retardé ou si le cours évolue pendant le traitement. Conserver la distinction entre cette conversion virtuelle de jeu et un ordre réel sur un exchange.

## Découpage de livraison

1. **Socle économique** : paramètres et formules `data/math.json`, service CCXT, tâche 15 min, état/historique SQL, logs et reprise au démarrage.
2. **Conversion** : branchement du cours persistant sur les devis et ventes, affichage du taux utilisé, garde contre un devis périmé ; revue du calcul PvP.
3. **Marché visuel v1** : `/market`, vue d’embed conforme à `graphique.md`, sparkline Unicode sans fichier par défaut, sélection de période et image détaillée mise en cache sur demande.
4. **Alertes** : stockage, UI de configuration, notifications et cooldown.
5. **Vente automatique** : règles explicites, limites, exécution transactionnelle idempotente et historique des exécutions.
6. À chaque livraison visible par l’utilisateur : traductions FR/EN et entrée dans `CHANGELOG.md`. Toute migration SQL est inscrite dans `migration.sql`.

## Conditions d’acceptation à vérifier pendant l’implémentation

- Les variations sont calculées uniquement avec trois paires, trois fenêtres clôturées et une moyenne à poids égal.
- Une moyenne nulle ne change pas le cours ; le cours compose chaque variation avec le cours précédent.
- Une erreur ou une donnée périmée ne change pas le cours et ne produit pas de prix fictif.
- Un cycle UTC ne peut être appliqué qu’une fois, y compris après redémarrage ou avec plusieurs processus.
- Les graphiques 24 h / 7 j / 30 j utilisent l’historique du jeu et n’interrogent pas l’exchange depuis les callbacks Discord.
- Une même version de graphique/période n’est rendue qu’une seule fois par instance/cache ; les autres consultations utilisent le cache.
- La vue par défaut n’envoie pas de fichier image. Un graphique détaillé est envoyé seulement après action du joueur.
- Le changement de période n’interfère pas avec la période choisie par un autre joueur.
- Le graphique reste lisible dans l’embed sur mobile, affiche source/période/fraîcheur et respecte les couleurs et le footer de `graphique.md`.
- Le devis et la confirmation de vente affichent le cours réellement appliqué ; toute décision de changement de cours pendant un devis est cohérente et explicite.
- Les alertes et ventes automatiques ne peuvent pas être déclenchées deux fois pour le même événement.

## Décisions à confirmer pendant le développement

- Limite maximale autorisée par cycle (ou aucune limite) après simulation économique.
- Cours variable appliqué au calcul PvP ou taux de référence PvP indépendant.
- Source de référence Binance/USDT définitive et éventuelle source de secours. Ne pas mélanger silencieusement les sources.
- Politique de devis lors d’un changement de cours entre préparation et confirmation.
- Rétention exacte de l’historique et emplacement du cache d’images selon l’environnement de production.
- Comportement de vente automatique quand le flux de marché est considéré comme retardé.
