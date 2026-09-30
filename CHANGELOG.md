# Changelog

## 2026-09-30

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

