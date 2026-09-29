# Changelog

## 2026-09-29

- Ajustement du plan PvP pour une implementation directe sur une branche de developpement, sans feature flags ni double fonctionnement V1/V2.
- Ajout du plan d'implementation par etapes du PvP logiciel, avec lots successifs, tests et validations humaines obligatoires. Aucun changement du gameplay.
- PvP V2 Etape 0 : creation de design/PVP_V2_DECISIONS.md avec les 20 decisions de game design, exemples chiffres et cas limites. Aucun code modifie.
- PvP V2 Etape 1 : ajout de la section pvp_v2 dans data/math.json (empreintes, familles, tiers, couts de developpement par tier T1-T6, durees d'installation, ralentissement defensif, Hostile Miner, Ransomware, Vol de monnaie, Saturation, Scan, Marche). Ajout de 13 accesseurs types et de validate_pvp_v2_config() dans game/math_config.py. Ajout de 27 tests de configuration dans test_suite.py. Suite complete : 450 tests, 14 echecs preexistants inchanges, 0 nouveau echec.
- PvP V2 Etape 2 : schema relationnel cible des 9 tables valide et integre dans root.sql. Script de migration idempotent dans migration.sql. Creation des 6 modules de depots specialises sous game/db/ (pvp_v2_research.py, pvp_v2_software.py, pvp_v2_patches.py, pvp_v2_dev_jobs.py, pvp_v2_operations.py, pvp_v2_reports.py, pvp_v2_market.py). Ajout de tests unitaires complets et tests de concurrence logique dans tests/test_pvp_v2_db.py. Suite complete : 458 tests, 14 echecs preexistants inchanges, 0 nouveau echec.

## 2026-09-28

- Game design PvP : sept familles de logiciels, empreintes uniques et infrastructures de controle. Les modules de defense ralentissent les installations hostiles tout en developpant les correctifs en parallele. Document de conception uniquement.
- Ajout de six illustrations des infrastructures de controle, du smartphone au datacenter, avec renovation progressive du bureau initial. Aucun changement du bot.
- Ajout de embed.md : specification des panneaux Discord Root OS, des emojis et des interactions pour leur integration au bot.
- Demo Root OS : panneau public, emojis du serveur (versions animees prioritaires), vues materiel et logiciels, diagnostic puis isolation d'une connexion fictive. Aucun effet sur le jeu.
- Ajout d'un pack visuel de cinq emojis animes pour Discord : alerte, terminal, recolte, scan et retour. Aucun changement du gameplay.

