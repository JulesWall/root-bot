# Changelog

## 2026-09-30

- **Manuel de Jeu & Documentation** :
  - Création du guide complet [`tutoriel.md`](file:///c:/Users/Juels/Desktop/root%20bot/tutoriel.md) détaillant pas-à-pas la reconnaissance (`/scan`), le cycle de développement (`/dev`, `/library`), les 6 familles offensives (`/hack`), les contre-mesures (`/diag`, `/trace`, `/pay`) et le fonctionnement du marché souterrain (`/market`).

- **Livraison Intégrale PvP V2 — Écosystème Logiciel, Marché Souterrain, Analyse de Trace & Cyberguerre :**
  - **Marché Souterrain (`/market` et `!market`, alias `!mkt`)** :
    - Bourse sécurisée entre joueurs pour l'achat, la vente et l'échange de logiciels compilés, de correctifs défensifs non installés et de dossiers de recherche offensifs.
    - Commission de place de 5% prélevée sur chaque transaction au bénéfice du réseau.
    - Réservation atomique de l'actif lors de la publication d'une annonce pour empêcher toute duplication ou usage concurrent.
    - Plafond de 5 annonces simultanées par joueur, protection anti-auto-achat et interdiction stricte de revente pour les copies volées ou correctifs déjà appliqués.
    - Sous-commandes : `/market list [type]`, `/market mine`, `/market sell <type> <id> <prix>`, `/market buy <id>`, `/market cancel <id>`.
  - **Analyse de Trace Réseau (`/hack trace`, `!hack trace` et raccourci `/trace`)** :
    - Permet d'analyser le trafic hostile en tâche de fond pour remonter la source des malwares actifs sur son réseau.
    - Révèle l'identité de l'attaquant si ce dernier n'a pas patché son propre système.
    - Ouvre instantanément une fenêtre de représailles légitimes de **72 heures** contre l'attaquant identifié, contournant l'écart de niveau d'infrastructure.
  - **Déploiement complet des 6 familles de malwares dans `/hack`** :
    - **Hostile Miner** : Siphonnage passif de 15% de la production brute de la baie ciblée vers la RAM de l'attaquant (plafonné à 40% tous attaquants cumulés).
    - **Ransomware** : Chiffrement du système adverse et blocage complet des commandes économiques (`buy`, `upgrade`, `compile`, `convert`, `trade`, `hourly`, `contract`). Rançon fixée par l'attaquant et payable en RTM via `/pay` ou `/hack pay`.
    - **Vol de Devises (`currency_theft`)** : Dérobement direct de 25% de la réserve USD de la cible (plancher de sécurité de 50$ préservé, 5% de frais de transaction).
    - **Saturation RAM (`saturation`)** : Réduction de 30% de la puissance de calcul du canal de recherche offensif adverse pendant 6 heures (plafonné à 60% cumulés).
    - **Espionnage Réseau (`espionage`)** : Cartographie complète style *directory* de l'inventaire logiciel, dossiers de recherche et patches adverses.
    - **Vol de Logiciel (`software_theft`)** : Duplication d'un logiciel compilé adverse sous forme de copie volée non revendable (`resellable=0`).
  - **Conversion des points d'attaque (Décision 17)** :
    - Taux de conversion fixé à 1 ATK = 20 USD pour la migration finale.
  - **Refonte et immersion graphique Root OS** :
    - Intégration de la charte chromatique thématique dans `RootEmbed` (Turquoise `#54E2D1`, Rouge offensif `#E74C3C`, Vert marché `#2ECC71`).
    - Nouveaux messages de notification privés stylisés pour les résolutions d'opérations, alertes de rançon et ventes au marché.
  - **Validation & Intégrité** :
    - 540 tests unitaires passés avec succès (540/540 OK, 0 échec).

- Hotfix /hack & Résolution des opérations offensives (Étape 6) :
  - Correction de l'erreur `KeyError: 'hack'` lors de la génération de devis d'opération offensive (`commands/game/hack.py`) : ajout de l'émote `hack` (`⚔️`) dans le catalogue et sécurisation automatique de tous les accès d'émojis via `EmojiDict`.
  - Correction de l'exception SQL `Champ 'resolves_at' inconnu dans where clause` lors de la livraison des opérations par `check_operations_loop` : utilisation transparente de la colonne existante `installed_at` pour stocker la date d'échéance de l'installation, garantissant le fonctionnement immédiat sans nécessiter d'`ALTER TABLE` sur la base de données de production.
  - Alignement de la suite de tests unitaires : 70/70 tests PvP V2 validés avec succès.

- PvP V2 Étape 6 : Première boucle offensive complète (Hostile Miner & Siphonnage persistant).
  - Préservation intégrale de la commande `/hack` (et `!hack`, alias `!hk`) conformément au souhait utilisateur : permet de cibler directement un joueur pour déployer une copie logicielle de malware (Hostile Miner T1 à T6).
  - Ajout des sous-actions et commandes de diagnostic d'intégrité réseau : `/hack diag`, `!hack diag` et raccourci `/diag` pour analyser les flux de minage, détecter les malwares actifs et révéler leurs empreintes `[ABCD]`.
  - Intégration du ralentissement défensif passif (Décision 13) : la défense de la cible augmente la durée d'installation selon `durée_effective = durée_base × (1 + défense / 500)`, plafonnée à ×10.
  - Cycle de vie complet des opérations offensives :
    - `installing` : installation furtive et silencieuse en tâche de fond (aucune alerte reçue par la victime).
    - `active` : infection persistante et activation du siphonnage passif continu.
    - Résolution automatique par un worker persistant `check_operations_loop` avec rattrapage au démarrage.
    - Envoi d'un message privé à l'attaquant lors de l'activation réussie ou de l'échec (si un patch a été posé pendant l'installation).
  - Mécanique de siphonnage passif intégrée à la source unique de vérité du minage (`MathConfig.compute_mining_progress` et `_settle_mining`) :
    - Dérivation passive de 15 % de la production brute de la baie ciblée vers la mémoire vive de l'attaquant.
    - Plafonnement cumulatif de siphonnage à 40 % par tier face à plusieurs attaquants.
    - Respect strict du plafond de capacité RAM de l'attaquant (surplus ignoré).
    - Invariant de saturation : si la RAM de la victime est saturée à 100 %, la production et le siphon se figent jusqu'au `/claim`.
    - Neutralisation définitive de l'infection par l'installation du correctif (patch) correspondant à l'empreinte via `/library` ou `/dev`.
  - 21 tests unitaires exhaustifs dans `tests/test_pvp_v2_operations.py` (21/21 OK). Total des 4 suites PvP V2 : 54/54 tests validés avec succès.

- PvP V2 Étape 5 : Scan réseau direct & rapport de reconnaissance enrichi.
  - Réactivation et refonte intégrale des commandes `/scan` et `!scan` sans concept d'ATK V1 ni tirage aléatoire de secret_id.
  - Sondage réseau déterministe (0.005 RTM, durée 90s) avec éligibilité stricte (Infrastructure >= 1, cible >= attaquant sauf si représailles actives sous 72h).
  - Devis interactif Two-Phase Commit avec composant `Confirmation` unifié (✅ Confirmer / ❌ Annuler), Embed Turquoise Root OS (`#54E2D1`) et emotes Root OS officielles.
  - Simplification d'architecture : suppression de l'archivage en base (`pvp_v2_scan_reports`) et de la sous-commande `view` pour éviter le stockage inutile. La photographie live est capturée à t=résolution et délivrée directement en MP au scanner.
  - Rendu visuel hautement enrichi du rapport de reconnaissance en MP :
    - Embed Root OS Turquoise (`#54E2D1`) avec avatar officiel et horodatage UTC.
    - Jauge ASCII de niveau d'infrastructure/pare-feu (`▰▰▰▰▱` 4/5).
    - Puissance de calcul et hashrate formaté (`H/s` et estimation `RTM/h`).
    - Jauge ASCII de saturation du tampon RAM (`▰▰▰▰▰▱▱▱▱▱` avec ratio et montants précis en RTM).
    - Modules matériels regroupés par Baie (Tier).
    - Logiciels compilés et correctifs déployés avec leurs familles et empreintes `[ABCD]`.
    - Détection de l'activité de recherche & développement en cours.
  - Worker de livraison persistant avec envoi du rapport en MP au scanner et alertes pare-feu pour la cible (Niv. 3 anonyme, Niv. 4 avec identité du scanner).
  - Correction de l'accès au niveau d'infrastructure du joueur en base (résolution de l'alias `firewall_level` en `infrastructure_level`).
  - 16 tests unitaires dédiés dans `tests/test_pvp_v2_scan.py` (16/16 OK). Suite globale : 511 tests, 0 erreur, 9 échecs historiques inchangés.
- Commande préfixe `!dev` : affiche désormais un lexique détaillé et complet de la syntaxe de développement (canaux `offense` / `defense`, 4 types de jobs, sous-commandes et exemples) au lieu d'ouvrir directement la bibliothèque. Également accessible via `!dev help` et `/dev help`.
- Harmonisation complète du système de confirmation pour les devis de développement logiciel : utilisation du composant unifié `Confirmation` (boutons Valider / Annuler standards et protection anti-spam), avec intégration systématique du registre des emotes Root OS (`root_*` animées prioritaires, avec replis Unicode) via `utils/emojis.py`.
- Résolution des clés d'erreurs métier Discord (`g_error_channel_busy`, `g_error_research_already_completed`, `g_error_research_folder_required`, etc.) et harmonisation globale des retours visuels (formatage avec préfixe quote `> `, émoticônes thématiques, syntaxes d'usage).
- Ajout de tests unitaires pour la commande préfixe et le lexique dans `tests/test_pvp_v2_dev.py` (25 tests passés avec succès). Suite globale : 491 tests, 0 erreur, 14 échecs historiques inchangés.

## 2026-09-29

- Ajustement du plan PvP pour une implementation directe sur une branche de developpement, sans feature flags ni double fonctionnement V1/V2.
- Ajout du plan d'implementation par etapes du PvP logiciel, avec lots successifs, tests et validations humaines obligatoires. Aucun changement du gameplay.
- PvP V2 Etape 0 : creation de design/PVP_V2_DECISIONS.md avec les 20 decisions de game design, exemples chiffres et cas limites. Aucun code modifie.
- PvP V2 Etape 1 : ajout de la section pvp_v2 dans data/math.json (empreintes, familles, tiers, couts de developpement par tier T1-T6, durees d'installation, ralentissement defensif, Hostile Miner, Ransomware, Vol de monnaie, Saturation, Scan, Marche). Ajout de 13 accesseurs types et de validate_pvp_v2_config() dans game/math_config.py. Ajout de 27 tests de configuration dans test_suite.py. Suite complete : 450 tests, 14 echecs preexistants inchanges, 0 nouveau echec.
- PvP V2 Etape 2 : schema relationnel cible des 9 tables valide et integre dans root.sql. Script de migration idempotent dans migration.sql. Creation des 6 modules de depots specialises sous game/db/ (pvp_v2_research.py, pvp_v2_software.py, pvp_v2_patches.py, pvp_v2_dev_jobs.py, pvp_v2_operations.py, pvp_v2_reports.py, pvp_v2_market.py). Ajout de tests unitaires complets et tests de concurrence logique dans tests/test_pvp_v2_db.py. Suite complete : 458 tests, 14 echecs preexistants inchanges, 0 nouveau echec.
- PvP V2 Etape 3 : refonte du panneau /network sous Root OS V2. Integration des infrastructures de controle du niveau 0 au niveau 5 avec illustrations dediees, sous-vues Materiel et Logiciels, jauges dynamiques et restrictions d'interaction reservees au proprietaire. Ajout de 8 tests unitaires dans tests/test_network_v2.py. Suite complete : 466 tests, 14 echecs preexistants inchanges, 0 nouveau echec.
- PvP V2 Etape 4 : cycle logiciel complet, bibliotheque et correctifs PvP V2.
  - Ajout des commandes /dev (start, status, cancel) pour la recherche et la compilation offensives et defensives, gerant deux canaux independants (offense consommant attack_t*, defense consommant bay_defense_t*).
  - Ajout de la commande /library et integration interactive au bouton "Logiciels" de /network pour inspecter dossiers de recherche, copies logicielles, correctifs et lancer l'installation de patchs.
  - Generation serveur d'empreintes uniques a 4 caracteres garanties par famille, persistance a travers les copies.
  - Algorithme pur de calcul du ralentissement passif defensif (plafonnement conforme a math.json).
  - Worker d'echeance persistant check_dev_loop avec livraison unique, notifications en message prive et rattrapage automatique au redemarrage.
  - Depreciation de l'ancienne commande /compile au profit de /dev, et mise en veille de maintenance des anciennes commandes /scan et /hack en attente de leurs etapes V2 respectives.
  - Harmonisation des embeds de devis de developpement logiciel et de bibliotheque via le composant standard Confirmation (boutons valider/annuler) et integration systematique du registre d'emotes Root OS (utils/emojis.py).
  - Ajout de 22 tests unitaires dans tests/test_pvp_v2_dev.py. Suite complete : 488 tests, 14 echecs preexistants inchanges, 0 erreur.

## 2026-09-28

- Game design PvP : sept familles de logiciels, empreintes uniques et infrastructures de controle. Les modules de defense ralentissent les installations hostiles tout en developpant les correctifs en parallele. Document de conception uniquement.
- Ajout de six illustrations des infrastructures de controle, du smartphone au datacenter, avec renovation progressive du bureau initial. Aucun changement du bot.
- Ajout de embed.md : specification des panneaux Discord Root OS, des emojis et des interactions pour leur integration au bot.
- Demo Root OS : panneau public, emojis du serveur (versions animees prioritaires), vues materiel et logiciels, diagnostic puis isolation d'une connexion fictive. Aucun effet sur le jeu.
- Ajout d'un pack visuel de cinq emojis animes pour Discord : alerte, terminal, recolte, scan et retour. Aucun changement du gameplay.

