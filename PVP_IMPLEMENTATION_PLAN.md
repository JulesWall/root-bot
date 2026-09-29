# ROOT OS - Plan d'implementation du PvP logiciel

Ce document est une consigne de travail pour l'agent IA charge d'implementer la refonte. Il doit etre lu avec :

- `instruction_for_agent.md`
- `design/ROOT_OS_GAME_DESIGN.md`
- `embed.md`
- `data/math.json`
- `root.sql` et `migration.sql`

Le game design definit l'intention. Ce plan definit l'ordre de construction et les controles. En cas de contradiction, ne pas improviser : signaler le point au responsable humain et attendre sa decision.

## Regle d'execution pour Claude

1. Ne realiser qu'une seule etape a la fois.
2. Commencer par relire les fichiers cites ci-dessus et inspecter le code concerne.
3. Avant toute modification, annoncer les fichiers vises et le comportement attendu.
4. Ne jamais anticiper une etape suivante, meme si son infrastructure semble facile a ajouter.
5. A la fin de l'etape, executer tous les tests demandes, mettre a jour `changelog.md`, puis fournir le protocole de verification humaine.
6. S'arreter apres le compte rendu. Attendre une validation humaine explicite avant l'etape suivante.
7. Une etape n'est terminee que si les fonctions hors de son perimetre et les fonctions deja livrees restent operationnelles.
8. Ne pas utiliser Git dans ce projet.

Compte rendu obligatoire apres chaque etape :

- comportement livre ;
- fichiers modifies ;
- SQL ajoute a `migration.sql` ;
- parametres ajoutes ou modifies dans `data/math.json` ;
- tests lances et resultats ;
- verification manuelle a effectuer ;
- risques, limites et decisions encore ouvertes ;
- corrections a apporter si la verification humaine echoue.

## Contraintes architecturales non negociables

- Les Cogs Discord n'accedent jamais directement a MySQL. Toute action passe par `RootService.execute()`.
- Les transactions et verrous restent geres par `game/db/database.py`. Toute action entre plusieurs comptes verrouille leurs identifiants dans l'ordre croissant.
- La logique SQL va dans des classes dediees sous `game/db/`. Ne pas continuer a grossir `game/db/players.py` avec tout le PvP V2.
- Les calculs purs du nouveau PvP vont dans un module metier dedie, par exemple `game/pvp_rules.py`. Ils ne dependent ni de Discord ni de MySQL.
- Tous les nombres d'equilibrage, matrices par tier, durees, plafonds, couts et taux sont dans `data/math.json`. Aucun nombre de gameplay ne doit etre duplique dans Python ou dans les textes.
- `game/math_config.py` expose des accesseurs types et valide la nouvelle configuration. Un parametre absent ou invalide doit faire echouer clairement le demarrage ou les tests, pas activer un repli silencieux dangereux.
- Tous les textes visibles sont dans `lang/game_fr.py` et `lang/game_en.py`. Les descriptions et options de commandes sont dans `lang/descslash.py`. Les cles et placeholders FR/EN restent strictement symetriques.
- Les interfaces Discord Components V2 suivent `embed.md` et utilisent les emojis `root_*`. Les panneaux peuvent etre publics, mais une interaction verifie toujours l'identite et les droits du compte concerne.
- Chaque changement de schema est present dans le schema cible `root.sql` et dans la migration incrementale `migration.sql`. La migration doit preserver les donnees existantes et etre executable une seule fois sur l'installation cible.
- Les jobs longs sont persistants en base avec des dates UTC. Ne pas utiliser de long `asyncio.sleep`. Une reprise du bot ne doit ni perdre ni executer deux fois un job.
- Tous les montants economiques utilisent `Decimal` et les precisions de `math.json`. Aucun solde ne peut devenir negatif.
- Chaque devis est recalcule et revalide dans la transaction de confirmation. Utiliser le mecanisme `quote_changed` lorsqu'une valeur determinante a change.
- Les nouvelles notifications doivent etre idempotentes : un redemarrage ne doit pas envoyer deux fois la meme livraison ou recompense.
- Un champ ou une table remplace ne peut etre retire qu'apres migration de ses donnees, remplacement de tous ses usages et validation humaine de l'etape concernee.

## Strategie de livraison

Le travail est realise directement sur une branche de developpement qui n'est pas en production. Il n'y a donc ni double implementation V1/V2, ni feature flags, ni ancien affichage de secours. Quand une fonction est traitee dans une etape, elle remplace directement son equivalent historique sur la branche.

Ajouter dans `data/math.json` une section unique `pvp_v2` comprenant au minimum :

- les regles d'eligibilite et de represailles ;
- les matrices de recherche, compilation, installation et defense ;
- les plafonds de cumul et limites d'operations ;
- les regles de migration de l'ancien stock ATK.

Ne pas ajouter de mecanisme temporaire d'activation dans le code ou dans `math.json`. Une etape incomplete ne doit simplement pas etre exposee dans les commandes. Si une ancienne commande est retiree avant l'arrivee de son remplacement, elle repond avec un message localise indiquant que cette action n'est pas disponible sur la branche de developpement ; elle ne doit jamais executer silencieusement l'ancienne mecanique.

Ne pas reutiliser la table `hack` pour plusieurs nouveaux concepts. La migration finale devra traiter les jobs `compile` et `scan` encore presents au moment du deploiement. Ne pas transformer en place `pvp_attacks` en table V2 : ses donnees ont une semantique differente.

Conserver initialement les colonnes suivantes pour eviter une migration risquee :

- `firewall_level` devient, dans le domaine et l'interface, `infrastructure_level` ; le renommage SQL n'est pas necessaire a la premiere version ;
- `attack_t1..t6` deviennent le materiel de calcul offensif ;
- `bay_defense_t1..t6` deviennent le materiel de calcul defensif ;
- `attack_points` reste une donnee a convertir selon la decision approuvee avant son retrait ;
- `network_defense` reste disponible jusqu'au remplacement de tous ses lecteurs, puis peut etre retire par migration explicite.

## Etape 0 - Figer les decisions de game design

### Objectif

Supprimer les ambiguïtes qui changeraient le schema, les calculs ou l'economie. Aucun code de production ni SQL a cette etape.

Creer `design/PVP_V2_DECISIONS.md` et obtenir une reponse explicite pour chaque point :

1. Perimetre d'une vulnerabilite : un tier precis ou tous les tiers du systeme cible.
2. Generation de l'empreinte courte : alphabet, longueur, unicite, gestion des collisions et caractere public ou secret.
3. Recherche : probabilite ou resultat garanti, redécouverte d'une vulnerabilite connue, nombre de recherches simultanees et cout d'un echec.
4. Difference exacte entre dossier de recherche, logiciel compile, copie volee, licence, patch et patch installe.
5. Droits de copie et de revente pour chaque type de possession.
6. Hostile Miner : taux, assiette brute ou nette, stockage du gain, effet d'une memoire pleine, cumul de plusieurs attaquants et fin de l'infection.
7. Espionnage preventif : informations revelees, duree, moment ou un correctif peut commencer et possibilite de rester discret.
8. Ransomware : commandes eligibles, commandes qui restent toujours accessibles, calcul de la rancon, duree maximale, paiement et immunite temporaire apres resolution.
9. Vol de monnaie : devise ciblee, reserve exposee, montant maximal, protection du solde minimum et frequence.
10. Saturation : ressource ralentie, taux, duree, cumul et plancher de capacite defensive.
11. Scan complet : liste exacte des donnees visibles et duree de validite du rapport.
12. Vol de logiciel : selection de la cible, visibilite prealable, conservation de l'original, revente et acces ou non au dossier source.
13. Modules de defense : formule de ralentissement, plafond, puissance de recherche defensive par tier et cout des correctifs.
14. Operations simultanees par attaquant et par victime, puis limites d'effets cumules.
15. Detection, diagnostic, analyse de trace, identification de l'auteur et debut des 72 heures de represailles.
16. Publication et installation d'un patch public : cout, duree et comportement hors ligne.
17. Conversion ou remboursement du stock `attack_points` existant.
18. Commandes finales et nouvelle fonction de `/compile`, `/scan` et `/hack`, ou noms qui les remplacent. Aucune compatibilite de comportement avec l'ancien PvP n'est exigee.
19. Visibilite publique ou privee des scans, bibliotheques, rapports et operations.
20. Regles initiales du marche : prix libre ou encadre, taxes, annulation, offres simultanees et prevention de l'auto-achat.

Pour chaque decision, noter : choix retenu, raison, exemple chiffre et cas limite. Reporter ensuite les valeurs approuvees dans `design/ROOT_OS_GAME_DESIGN.md` avant de commencer l'etape 1.

### Verification humaine 0

- Lire uniquement les decisions et les exemples, sans code.
- Simuler sur papier trois profils : nouveau joueur, joueur specialise attaque, joueur specialise defense.
- Verifier qu'aucun compte ne peut etre rendu injouable et qu'un joueur hors ligne conserve une voie de recuperation.
- Valider explicitement : `ETAPE 0 VALIDEE`.

## Etape 1 - Filet de securite et nouvelle configuration

### Objectif

Preparer une base mesurable sans changer le jeu visible.

### Travaux

- Executer la suite complete avant modification et conserver le resultat dans le compte rendu.
- Ajouter la section `pvp_v2` complete dans `data/math.json`, sans feature flags.
- Ajouter dans `game/math_config.py` des accesseurs et une validation stricte des types, matrices par tier, pourcentages et bornes.
- Ajouter des tests de configuration : six niveaux 0 a 5, tiers materiels existants, taux entre 0 et 1, durees positives, plafonds coherents et familles connues uniquement.
- Ajouter un test qui garantit que le chargement de la nouvelle configuration ne modifie pas encore les resultats de `/network`, `/buy`, `/upgrade`, `/compile`, `/scan` et `/hack`.
- Documenter la structure de configuration dans le fichier de conception, sans exposer de texte technique aux joueurs.

### Tests automatiques

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v
```

La suite complete doit etre verte avant et apres. Un test ne peut etre retire que lorsqu'une etape remplace explicitement le comportement qu'il couvre ; son remplacement V2 doit etre ajoute dans la meme modification.

### Verification humaine 1

- Sur le serveur de test, utiliser `/network`, acheter un module de chaque type, lancer un devis d'upgrade, une compilation, un scan et une attaque historiques.
- Comparer montants, delais et textes avec la version de reference.
- Redemarrer le bot et verifier la livraison d'un job historique.
- Valider explicitement : `ETAPE 1 VALIDEE`.

## Etape 2 - Schema V2 et depots

### Objectif

Installer la persistance du nouveau systeme sans commande publique et sans modifier les comptes.

### Modele minimal a faire approuver avant SQL

Produire d'abord un schema relationnel commente couvrant ces responsabilites :

- vulnerabilites et empreintes ;
- connaissances ou dossiers detenus par joueur ;
- logiciels compiles et leur proprietaire ;
- correctifs connus et correctifs installes ;
- jobs de developpement avec deux canaux `offense` et `defense` ;
- operations en preparation, actives, terminees ou annulees ;
- infections persistantes et effets actifs ;
- rapports de scan horodates ;
- journal d'operation immuable ;
- futures annonces de marche et transactions.

Normaliser les identifiants, proprietaires, etats et montants. Un champ JSON est acceptable pour une photographie de rapport variable, pas pour cacher les soldes, proprietaires, etats, vulnerabilites ou montants indispensables aux contraintes SQL.

### Travaux apres validation du schema

- Ajouter les tables au schema cible `root.sql`.
- Ajouter le SQL incremental equivalent dans `migration.sql`. Les suppressions devenues necessaires restent reservees a l'etape 13, apres migration de leurs donnees.
- Creer des depots specialises sous `game/db/`, par exemple `software.py`, `development.py`, `operations.py` et `patches.py`.
- Ajouter des contraintes d'unicite pour empecher une double empreinte, une double installation du meme patch et plusieurs jobs sur un meme canal lorsqu'ils sont interdits.
- Ajouter des index pour les jobs echus, operations par joueur, infections par victime et possessions de logiciels.
- Tester chaque depot avec la transaction factice existante ou une fixture dediee qui imite exactement MySQL.
- Ajouter un test de concurrence logique : deux confirmations identiques ne creent qu'une seule ressource facturable.

### Verification humaine 2

- Examiner `migration.sql` ligne par ligne avant execution.
- Faire une sauvegarde de la base de test, appliquer la migration, puis relancer la suite complete.
- Verifier avec `SHOW CREATE TABLE` les contraintes, index, types monetaires et cles etrangeres.
- Demarrer le bot : aucune commande ou valeur visible ne doit encore changer.
- Redemarrer une seconde fois pour verifier qu'aucune initialisation applicative ne duplique les donnees.
- Valider explicitement : `ETAPE 2 VALIDEE`.

## Etape 3 - Infrastructure de controle et interface `/network`

### Objectif

Remplacer la presentation du pare-feu par les six infrastructures sans changer les regles de progression ou les inventaires.

### Travaux

- Introduire dans le domaine l'appellation `infrastructure_level` tout en lisant encore `players.firewall_level`.
- Afficher les niveaux : smartphone bricole, PC assemble, station de travail, serveur dedie, salle des serveurs, datacenter.
- Utiliser les images de `design/infrastructures-controle/` et la structure Components V2 de `embed.md`.
- Conserver un regroupement par tier et un nombre illimite de mineurs.
- Integrer les emojis du serveur par leur nom, avec repli Unicode et priorite aux versions animees.
- Deplacer tous les nouveaux textes dans les fichiers FR/EN et garder les placeholders identiques.
- Remplacer directement l'ancienne interface `/network` sur la branche.
- Ne pas modifier encore `/upgrade`, ses prix, ses bonus ou les regles d'eligibilite PvP.

### Verification humaine 3

- Tester les niveaux 0 a 5 sur ordinateur et mobile.
- Verifier la bonne image, le nom de l'infrastructure, la production, la memoire, les tres grands nombres de mineurs et les jobs historiques.
- Tester emojis animes, emojis statiques, emoji manquant et banniere manquante.
- Verifier que tout le monde voit le panneau mais que seul le proprietaire peut effectuer une action sur son compte.
- Valider explicitement : `ETAPE 3 VALIDEE`.

## Etape 4 - Bibliotheque, developpement et correctifs

### Objectif

Livrer le cycle logiciel sans permettre encore d'attaquer un autre joueur.

### Travaux

- Ajouter les actions de service necessaires a la recherche offensive, la compilation d'un logiciel, la recherche defensive, la compilation et l'installation d'un patch.
- Ajouter ces actions a `RootService.ACTIONS`, au dispatcher et a `_locks_for`.
- Garder la logique dans les nouveaux modules metier et depots, pas dans les callbacks Discord.
- Le canal offensif consomme la puissance `attack_t*`. Le canal defensif consomme `bay_defense_t*`. Les deux jobs peuvent progresser simultanement.
- Une seule recherche ou compilation par canal selon les decisions de l'etape 0.
- Generer l'empreinte cote serveur dans la transaction et garantir son unicite en base.
- Conserver l'empreinte lors d'une copie ou compilation d'un meme dossier.
- Installer un patch de facon idempotente ; les futurs materiels du tier concerne en beneficient automatiquement.
- Implementer le calcul pur du ralentissement passif des installations hostiles, avec le plafond approuve. Ne pas encore l'appliquer a une attaque.
- Ajouter directement la bibliotheque et les vues de progression dans l'interface.
- Remplacer l'ancienne production d'ATK par le nouveau cycle de developpement. A partir de cette etape, aucune commande ne doit encore creer de nouveaux `attack_points`.
- Tant que leurs remplacements ne sont pas livres, `/scan` et `/hack` affichent un message localise d'indisponibilite sur la branche et n'executent plus l'ancien PvP.
- Le worker de jobs doit reprendre apres redemarrage et livrer une seule fois.

### Verification humaine 4

- Compte A : lancer une recherche offensive puis compiler deux copies successives ; verifier la meme empreinte.
- Compte A : lancer simultanement un developpement offensif et un correctif defensif ; verifier que les deux horloges avancent independamment.
- Redemarrer le bot pendant chaque type de job et verifier une livraison unique.
- Tenter une double confirmation, un solde insuffisant et une installation du meme patch deux fois.
- Verifier que personne ne peut encore deployer un logiciel contre un autre compte.
- Valider explicitement : `ETAPE 4 VALIDEE`.

## Etape 5 - Scan complet du reseau

### Objectif

Livrer la premiere operation V2, informative et sans effet economique sur la cible.

### Travaux

- Reutiliser les regles de cible : niveau equivalent ou superieur, sauf droit de represailles.
- Remplacer directement le scan historique base sur le `secret_id` par une photographie conforme aux decisions de l'etape 0.
- Capturer les donnees au moment de la resolution du scan, pas au moment du devis.
- Stocker le rapport avec sa date et ses valeurs figees. L'affichage ne relit pas silencieusement l'etat actuel de la cible.
- Ne jamais inclure une donnee non approuvee, un identifiant Discord brut inutile ou un secret de configuration.
- Appliquer cout, duree, puissance et probabilite depuis `math.json`.
- Donner un droit de represailles selon la regle approuvee, sans dupliquer les lignes existantes.

### Verification humaine 5

- Trois comptes : A peut scanner B de niveau egal ou superieur ; A ne peut pas scanner C de niveau inferieur sans represailles.
- Modifier le reseau de B apres le scan et verifier que l'ancien rapport ne change pas.
- Tester echec, succes, cible supprimee, cible sans materiel, redemarrage avant resolution et deux clics de confirmation.
- Comparer chaque champ visible au compte B et verifier qu'aucune information supplementaire ne fuit.
- Valider explicitement : `ETAPE 5 VALIDEE`.

## Etape 6 - Hostile Miner, premiere boucle PvP complete

### Objectif

Valider toute la chaine sur une seule famille avant d'ajouter les autres : dossier, logiciel, devis, installation ralentie, infection persistante, siphonnage, diagnostic et patch.

### Travaux

- Le devis indique cible, tier, cout, duree d'installation apres defense et effet attendu. Il n'annonce pas un gain total impossible a connaitre.
- Recalculer a la confirmation l'eligibilite, la possession du logiciel, le patch de la cible, la puissance defensive et les limites de cumul.
- Le ralentissement des modules de defense modifie la duree d'installation selon `math.json`, sans reveler l'attaque a la victime.
- Si le patch est installe avant la fin de l'installation, l'operation echoue proprement selon la regle economique approuvee.
- Une infection active persiste en base. Son rendement est calcule par intervalles temporels, avec `Decimal`, de maniere idempotente et sans boucle par seconde.
- Integrer le siphon a la mise a jour du minage dans un point unique. Toute lecture ou recolte doit d'abord solder le minage et les siphons au meme instant `tx.now`.
- Respecter la decision sur la memoire, le stockage du butin et la saturation. Conserver l'invariant : production victime + production attaquant + pertes explicites = production totale attendue.
- Le diagnostic identifie l'infection mais ne l'arrete pas. Seule l'installation du bon patch met fin a l'effet et interdit le retour de la meme empreinte.
- Creer un journal horodate pour l'attaquant et la victime sans message a chaque tick.
- Ajouter les compteurs economiques necessaires aux rapports d'administration.
- Remplacer directement l'ancienne attaque destructive de `/hack`. Aucun chemin utilisateur ne doit encore detruire ou voler un module physique.

### Tests automatiques specifiques

- integration sur 0 seconde, une duree partielle, plusieurs recoltes et une longue periode hors ligne ;
- arrondis RTM aux limites de precision ;
- memoire victime pleine, stockage attaquant plein et comptes sans mineur cible ;
- deux attaquants, plafond global et repartition approuvee ;
- patch avant installation, pendant infection et deja installe ;
- lecture repetee du meme instant sans double credit ;
- redemarrage et resolution concurrente ;
- suppression d'un compte implique dans l'operation ;
- droit de represailles et regle de niveau.

### Verification humaine 6

- Compte A attaque B sans defense, puis B avec forte defense : comparer uniquement la duree d'installation, pas une probabilite cachee.
- Verifier qu'aucune alerte precise n'apparait avant diagnostic.
- Constater la baisse de production, diagnostiquer, installer le patch et verifier le retour exact au debit normal.
- Racheter un mineur du meme tier chez B et verifier qu'il est deja protege par le patch.
- Tenter de redeployer la meme empreinte et constater son blocage.
- Comparer sur une heure les valeurs attendues, recues et siphonnees avec un calcul manuel.
- Valider explicitement : `ETAPE 6 VALIDEE`.

## Etape 7 - Espionnage preventif

### Objectif

Permettre de decouvrir ce qu'un adversaire prepare, sans dupliquer le scan complet.

### Travaux

- Cibler uniquement les jobs de developpement approuves et ne jamais reveler les donnees generales du reseau.
- Produire un renseignement persistant ou temporaire selon la decision de design.
- Autoriser la recherche defensive anticipee, mais exiger son cout et son temps normaux.
- Verifier la course : espionnage termine, patch lance, logiciel ennemi compile puis deploye.
- Ne jamais modifier ou annuler directement le job espionne.

### Verification humaine 7

- Comparer cote a cote un rapport de scan et un rapport d'espionnage : aucun chevauchement ambigu.
- Tester un job qui se termine ou est annule pendant l'espionnage.
- Verifier qu'un patch termine a temps bloque l'installation et qu'un patch en retard ne l'arrete qu'apres installation.
- Valider explicitement : `ETAPE 7 VALIDEE`.

## Etape 8 - Saturation du calcul

### Objectif

Ajouter un ralentissement offensif sans jamais supprimer la capacite de defense.

### Travaux

- Representer la saturation comme un effet actif date, plafonne et auditable.
- Recalculer les nouveaux jobs avec la capacite disponible approuvee. Definir a l'etape 0 si les jobs deja lances changent de date ou conservent leur devis.
- Garantir le plancher defensif et la possibilite d'installer un patch.
- Appliquer la regle de cumul de plusieurs saturations depuis `math.json`.
- Ne jamais stocker uniquement une date modifiee sans journal permettant d'expliquer le changement.

### Verification humaine 8

- Mesurer les memes recherches avec zero, une et plusieurs saturations.
- Tester le plafond, l'expiration, le redemarrage et la pose d'un patch sous saturation maximale.
- Verifier qu'aucune duree devient negative, infinie ou differente entre devis et confirmation sans `quote_changed`.
- Valider explicitement : `ETAPE 8 VALIDEE`.

## Etape 9 - Blocage contre rancon

### Objectif

Ajouter une attaque de controle avec deux voies de sortie reelles : payer ou patcher.

### Travaux

- Centraliser le controle des commandes bloquees dans la couche service, pas dans chaque bouton Discord.
- Maintenir une liste positive des actions blocables dans `math.json`. Les commandes de diagnostic, de patch, d'aide et de paiement restent toujours accessibles.
- Creer un enregistrement de rancon avec montant, devise, echeance et etat transactionnel.
- Le paiement transfere exactement le montant approuve, leve le blocage atomiquement et ne peut etre execute deux fois.
- Le patch leve le blocage sans paiement et protege de la meme empreinte.
- Appliquer l'immunite temporaire et les plafonds approuves.

### Verification humaine 9

- Pour chaque commande eligible, verifier blocage, message et absence d'effet metier.
- Payer avec solde suffisant puis insuffisant ; tester deux clics concurrents.
- Patcher au meme moment qu'un paiement et verifier qu'une seule resolution gagne sans perte d'argent.
- Verifier que le joueur peut toujours se connecter, comprendre la situation et se defendre.
- Valider explicitement : `ETAPE 9 VALIDEE`.

## Etape 10 - Vol de monnaie

### Objectif

Ajouter un transfert economique direct borne et explicable.

### Travaux

- Utiliser uniquement la devise, la reserve exposee, la formule et le plafond approuves.
- Calculer sur le solde verrouille au moment de la resolution et ne jamais produire de solde negatif.
- Enregistrer montant brut, frais, montant net et soldes avant/apres dans le journal economique.
- Integrer les compteurs d'administration et les alertes anti-abus existantes.
- Tester les arrondis `Decimal`, les petits soldes, le plafond quotidien et les comptes complices.

### Verification humaine 10

- Calculer manuellement plusieurs vols aux seuils minimum et maximum.
- Tester un solde qui change entre devis et resolution.
- Verifier la conservation totale de monnaie, frais explicitement exceptes.
- Verifier l'affichage du montant vole et du resultat net des deux cotes.
- Valider explicitement : `ETAPE 10 VALIDEE`.

## Etape 11 - Vol de logiciel

### Objectif

Copier un logiciel compile en conservant son empreinte et ses protections.

### Travaux

- Selectionner uniquement un logiciel que l'attaquant est autorise a connaitre ou cibler selon les decisions.
- Copier la possession, pas supprimer l'original et pas accorder le dossier de recherche.
- Conserver vulnerabilite, empreinte, auteur d'origine et droits de revente approuves.
- Empecher qu'une copie ou un renommage contourne un patch existant.
- Journaliser l'origine de la copie sans exposer inutilement l'identite aux autres joueurs.

### Verification humaine 11

- Voler une copie, deployer original et copie contre un reseau patche, puis verifier le meme blocage.
- Verifier que la victime conserve son logiciel et que le voleur n'obtient pas le dossier.
- Tester bibliotheque vide, logiciel non eligible, double resolution et revente interdite.
- Valider explicitement : `ETAPE 11 VALIDEE`.

## Etape 12 - Marche des joueurs

### Objectif

Permettre l'echange de copies, dossiers et correctifs avec des droits distincts.

### Travaux

- Modeliser explicitement le type vendu, la quantite, les droits transmis, le prix, la devise, les frais et l'expiration.
- Verrouiller vendeur, acheteur et annonce dans une transaction unique.
- A la creation, reserver l'actif vendu si necessaire pour interdire la double vente.
- A l'achat, revalider proprietaire, disponibilite, prix, solde et compatibilite.
- Interdire l'auto-achat et les prix hors bornes approuvees.
- Un patch public gratuit reste une publication, pas une installation automatique chez les autres joueurs.
- Ajouter historique et moderation sans permettre l'edition retroactive d'une vente terminee.

### Verification humaine 12

- Tester chaque type d'actif et verifier exactement les droits recus.
- Deux acheteurs tentent la derniere copie simultanement : un seul achat reussit.
- Tester annulation, expiration, fonds insuffisants, patch deja possede et annonce dupliquee.
- Verifier les frais et la conservation des monnaies.
- Valider explicitement : `ETAPE 12 VALIDEE`.

## Etape 13 - Nettoyage historique et preparation du deploiement

### Objectif

Retirer le code mort de l'ancien PvP, finaliser la migration des donnees existantes et prouver que la branche peut remplacer la version de production en une seule mise en service controlee.

### Preconditions

- Toutes les etapes precedentes sont validees.
- Les simulations economiques et le test de charge sont approuves.
- Une politique explicite existe pour chaque ancien job `hack.type='compile'`, `hack.type='scan'` ou `pvp_attacks` susceptible d'etre present dans une copie de production.
- Une sauvegarde restauree sur un environnement vierge a ete testee.

### Travaux

- Supprimer les derniers chemins capables de creer ou resoudre des jobs PvP historiques.
- Convertir `attack_points` avec le bareme valide, dans une migration auditable et relancable sans double credit.
- Conserver les quantites de modules d'attaque et de defense ; seule leur fonction change.
- Mettre a jour aide, onboarding, `/buy`, `/upgrade`, `/network`, commandes Slash et commandes prefixees en FR et EN.
- Mettre a jour les statistiques economiques, la moderation et les rapports.
- Supprimer le code mort, les textes et tests de l'ancien PvP. Une suppression SQL n'est acceptee que si les donnees ont ete migrees et si la restauration d'une sauvegarde a ete testee.
- Tester le deploiement complet sur une copie recente de la base de production, sans phase de double fonctionnement.

### Verification humaine 13

- Executer un parcours complet de nouveau joueur jusqu'a une premiere operation et un premier patch.
- Executer les sept familles avec deux joueurs de meme niveau, une cible superieure et une represaille contre une cible inferieure.
- Redemarrer le bot avec des jobs de chaque type en cours.
- Tester mobile et ordinateur, FR et EN, Slash et prefixe.
- Comparer les totaux economiques avant/apres migration sur une copie de production.
- Surveiller erreurs SQL, temps de transaction, verrous, doubles notifications et ecarts monetaires.
- Valider explicitement : `PVP V2 PRET A DEPLOYER`.

## Tests transversaux a conserver a chaque etape

La suite complete reste obligatoire :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v
```

Ajouter progressivement des tests couvrant :

- symetrie des cles et placeholders FR/EN ;
- validation exhaustive de `data/math.json` ;
- devis sans mutation puis confirmation atomique ;
- verrous de comptes tries et absence de deadlock evident ;
- redemarrage et idempotence des workers ;
- precision `Decimal` et conservation des monnaies ;
- regles de niveau et represailles ;
- plafonds de cumul multi-attaquants ;
- patch permanent pour les achats futurs du tier ;
- aucune action d'un tiers depuis un panneau public ;
- payloads Components V2 dans les limites Discord ;
- migration explicite de tous les jobs et stocks historiques lors du deploiement.

Ne pas remplacer les tests de service par des tests de callbacks Discord. La majorite des regles doit etre prouvee sans connexion a Discord.

## Test humain standard a trois comptes

Reutiliser le meme protocole a chaque validation :

- Compte A : attaquant au niveau d'infrastructure 3, materiel offensif et RTM suffisants.
- Compte B : cible au niveau 3, modules defensifs, non patchee au debut.
- Compte C : cible au niveau 2, utilisee pour verifier la protection de niveau et les represailles.

Pour chaque action : noter les soldes, inventaires, jobs, productions et patchs avant ; executer ; redemarrer si pertinent ; noter les memes valeurs apres. Toute difference non expliquee bloque l'etape suivante.

## Criteres generaux de refus

Refuser une etape et ne pas poursuivre si l'un des cas suivants apparait :

- une valeur d'equilibrage est codee en dur hors `data/math.json` ;
- un texte joueur est code en dur hors `lang/` ;
- un Cog execute du SQL ;
- une migration perd ou reinterprete silencieusement un actif joueur ;
- un callback public agit sur un autre compte sans controle ;
- une attaque peut supprimer toute possibilite de diagnostic ou de patch ;
- un redemarrage du bot change deux fois un solde ou un inventaire ;
- une monnaie, une puissance ou une duree devient negative ;
- les langues FR et EN divergent ;
- un comportement hors du perimetre de l'etape regresse ou un test est retire sans remplacement justifie ;
- l'agent a pris une decision de game design non validee.

## Message initial a donner a Claude

> Tu travailles directement sur une branche de developpement non deployee du projet Root Bot. Lis integralement `instruction_for_agent.md`, `PVP_IMPLEMENTATION_PLAN.md`, `design/ROOT_OS_GAME_DESIGN.md` et `embed.md`. N'implemente que l'etape que je t'indique. Il n'y a ni feature flags ni double fonctionnement V1/V2 : lorsqu'une etape remplace une fonction, modifie directement son implementation. Respecte l'architecture existante : commandes Discord sans SQL, logique transactionnelle via `RootService`, depots sous `game/db`, tous les nombres dans `data/math.json`, tous les textes dans les fichiers FR/EN, schema cible dans `root.sql` et migration incrementale dans `migration.sql`. Ne prends aucune decision de game design manquante. Termine l'etape avec la suite complete, le changelog et une checklist de verification humaine, puis arrete-toi pour obtenir ma validation.

Premiere instruction recommandee :

> Execute uniquement l'etape 0. Ne modifie aucun code, aucune base de donnees et aucun parametre d'equilibrage. Transforme les vingt decisions ouvertes en un document court, concret et validable avec des exemples chiffres. Arrete-toi ensuite.
