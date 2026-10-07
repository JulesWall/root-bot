-- ====================================================================
-- Root Bot - Schéma de Base de Données Relationnelle (MySQL 8.0+)
-- Schéma cible pour nouvelles installations (nettoyé)
-- ====================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- 1. Table des Joueurs
CREATE TABLE IF NOT EXISTS players (
    -- Identifiant Discord unique du joueur
    discord_id          BIGINT UNSIGNED NOT NULL,
    created_at          DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    -- Économie & Monnaies
    dollars             DECIMAL(30, 2)  NOT NULL DEFAULT 0.00,
    rootium             DECIMAL(30, 5)  NOT NULL DEFAULT 0.00000,

    -- Défenses & Progression
    firewall_level      TINYINT UNSIGNED NOT NULL DEFAULT 0,
    reputation          BIGINT UNSIGNED  NOT NULL DEFAULT 0,
    next_reputation_at  DATETIME(6)      NULL     DEFAULT NULL,

    -- Modules de Minage (Tiers 1 à 6)
    mining_t1           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    mining_t2           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    mining_t3           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    mining_t4           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    mining_t5           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    mining_t6           BIGINT UNSIGNED NOT NULL DEFAULT 0,

    -- Modules d'Attaque (Tiers 1 à 6)
    attack_t1           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    attack_t2           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    attack_t3           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    attack_t4           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    attack_t5           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    attack_t6           BIGINT UNSIGNED NOT NULL DEFAULT 0,

    -- Modules de Défense de Baie (Tiers 1 à 6)
    bay_defense_t1      BIGINT UNSIGNED NOT NULL DEFAULT 0,
    bay_defense_t2      BIGINT UNSIGNED NOT NULL DEFAULT 0,
    bay_defense_t3      BIGINT UNSIGNED NOT NULL DEFAULT 0,
    bay_defense_t4      BIGINT UNSIGNED NOT NULL DEFAULT 0,
    bay_defense_t5      BIGINT UNSIGNED NOT NULL DEFAULT 0,
    bay_defense_t6      BIGINT UNSIGNED NOT NULL DEFAULT 0,

    -- Défense globale du réseau
    network_defense     BIGINT UNSIGNED NOT NULL DEFAULT 0,

    -- Stock de points d'attaque produits par /compile
    attack_points       BIGINT UNSIGNED NOT NULL DEFAULT 0,

    -- Minage : tampon de Rootium miné en attente de /claim et horodatage de dernière mise à jour
    mining_buffer       DECIMAL(30, 5)  NOT NULL DEFAULT 0.00000,
    mining_last_update_at DATETIME(6)    NULL     DEFAULT NULL,
    -- Horodatage du dernier /claim réussi (pour mesurer le temps écoulé entre deux récoltes)
    mining_last_claim_at DATETIME(6)     NULL     DEFAULT NULL,

    -- Statistiques globales
    events_won          BIGINT UNSIGNED NOT NULL DEFAULT 0,

    -- Préférence de langue du joueur (NULL = auto-détection)
    lang                VARCHAR(2)       NULL     DEFAULT NULL,

    -- Identifiant secret 6 chiffres (rotation globale 12 h UTC)
    secret_id           CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NULL DEFAULT NULL,

    -- Autoclaim : crédits possédés et nombre de récoltes automatiques programmées
    autoclaim_credits   INT UNSIGNED    NOT NULL DEFAULT 0,
    autoclaim_active    INT UNSIGNED    NOT NULL DEFAULT 0,

    -- Récompense horaire (/hourly) & Système de Combo
    hourly_last_at      DATETIME(6)     NULL     DEFAULT NULL,
    hourly_combo_bonus  DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    hourly_streak       INT UNSIGNED    NOT NULL DEFAULT 0,
    hourly_lost_streak  INT UNSIGNED    NOT NULL DEFAULT 0,
    hourly_lost_bonus   DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    combo_saver_credits INT UNSIGNED    NOT NULL DEFAULT 0,

    -- Système de Contrats (/contract)
    contract_fidelity   INT UNSIGNED    NOT NULL DEFAULT 0,
    contracts_completed INT UNSIGNED    NOT NULL DEFAULT 0,
    contract_grace_until DATETIME(6)    NULL     DEFAULT NULL,

    -- Contraintes d'intégrité
    PRIMARY KEY (discord_id),
    UNIQUE KEY uq_players_secret_id (secret_id),
    INDEX idx_players_autoclaim_active (autoclaim_active),
    CHECK (dollars >= 0),
    CHECK (rootium >= 0),
    CHECK (firewall_level <= 5),
    CHECK (reputation >= 0),
    CHECK (attack_points >= 0),
    CHECK (autoclaim_credits >= 0),
    CHECK (autoclaim_active >= 0),
    CHECK (hourly_combo_bonus >= 0),
    CHECK (hourly_streak >= 0),
    CHECK (combo_saver_credits >= 0),
    CHECK (contract_fidelity >= 0),
    CHECK (contracts_completed >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Table des Préfixes par Serveur
CREATE TABLE IF NOT EXISTS guild_prefixes (
    guild_id   BIGINT UNSIGNED NOT NULL,
    prefix     VARCHAR(32)     NOT NULL,
    PRIMARY KEY (guild_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2b. Table des Préfixes Personnels par Utilisateur (MP)
CREATE TABLE IF NOT EXISTS user_prefixes (
    user_id    BIGINT UNSIGNED NOT NULL,
    prefix     VARCHAR(32)     NOT NULL,
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Table des Améliorations en cours (différées)
CREATE TABLE IF NOT EXISTS upgrades (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id    BIGINT UNSIGNED NOT NULL,
    item_type     VARCHAR(32)     NOT NULL DEFAULT 'firewall',
    target_level  TINYINT UNSIGNED NOT NULL,
    started_at    DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    expires_at    DATETIME(6)     NOT NULL,
    INDEX idx_upgrades_expires (expires_at),
    INDEX idx_upgrades_discord (discord_id),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Table des productions d'ATK et scans en cours (/compile, /scan)
CREATE TABLE IF NOT EXISTS hack (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id    BIGINT UNSIGNED NOT NULL,
    type          ENUM('compile', 'scan') NOT NULL DEFAULT 'compile',
    target_id     BIGINT UNSIGNED NULL DEFAULT NULL,
    method        VARCHAR(16)     NOT NULL,
    bits_per_s    BIGINT UNSIGNED NOT NULL DEFAULT 0,
    atk_yield     BIGINT UNSIGNED NOT NULL DEFAULT 0,
    rtm_paid      DECIMAL(30, 5)  NOT NULL,
    boost_rtm     DECIMAL(30, 5)  NOT NULL DEFAULT 0.00000,
    started_at    DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    expires_at    DATETIME(6)     NOT NULL,
    UNIQUE KEY uq_hack_discord_type (discord_id, type),
    INDEX idx_hack_expires (expires_at),
    INDEX idx_hack_target (target_id),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE,
    FOREIGN KEY (target_id)  REFERENCES players(discord_id) ON DELETE CASCADE,
    CHECK (method IN ('unskilled', 'skilled', 'ai', 'scan')),
    CHECK (atk_yield >= 0),
    CHECK (rtm_paid >= 0),
    CHECK (boost_rtm >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4bis. Table des Contrats de Travail en cours (/contract)
CREATE TABLE IF NOT EXISTS contracts (
    discord_id       BIGINT UNSIGNED NOT NULL,
    duration_type    VARCHAR(32)     NOT NULL,
    title            VARCHAR(255)    NOT NULL,
    reward_usd       DECIMAL(30, 2)  NOT NULL,
    is_special       TINYINT(1)      NOT NULL DEFAULT 0,
    started_at       DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    expires_at       DATETIME(6)     NOT NULL,
    notified         TINYINT(1)      NOT NULL DEFAULT 0,
    PRIMARY KEY (discord_id),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE,
    CHECK (reward_usd >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 5. Table des Événements du Système (ex: Hash Challenge)
CREATE TABLE IF NOT EXISTS events (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event          VARCHAR(32)     NOT NULL,
    next_at        DATETIME(6)     NOT NULL,
    last_found_by  BIGINT UNSIGNED NULL     DEFAULT NULL,
    last_found_on  VARCHAR(128)    NULL     DEFAULT NULL,
    last_reward    DECIMAL(30, 2)  NOT NULL DEFAULT 0.00,
    UNIQUE KEY uq_events_event (event)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Table des Statistiques d'Événements Journalières (Modération 24h & Anti-Triche, Rétention 48h)
CREATE TABLE IF NOT EXISTS daily_event_stats (
    discord_id          BIGINT UNSIGNED NOT NULL,
    date_key            DATE            NOT NULL DEFAULT (CURRENT_DATE),
    events_won          INT UNSIGNED    NOT NULL DEFAULT 0,
    events_participated INT UNSIGNED    NOT NULL DEFAULT 0,
    PRIMARY KEY (discord_id, date_key),
    INDEX idx_event_stats_date (date_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Table des droits de représailles PvP (scan / hack)
CREATE TABLE IF NOT EXISTS consequence (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    victim_id   BIGINT UNSIGNED NOT NULL,
    attacker_id BIGINT UNSIGNED NOT NULL,
    delete_at   DATETIME(6)     NOT NULL,
    INDEX idx_consequence_victim    (victim_id),
    INDEX idx_consequence_delete_at (delete_at),
    FOREIGN KEY (victim_id)   REFERENCES players(discord_id) ON DELETE CASCADE,
    FOREIGN KEY (attacker_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Table des attaques PvP en cours (/hack)
CREATE TABLE IF NOT EXISTS pvp_attacks (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    attacker_id    BIGINT UNSIGNED NOT NULL,
    victim_id      BIGINT UNSIGNED NOT NULL,
    attack_points  BIGINT UNSIGNED NOT NULL,
    target         ENUM('mining', 'attack') NOT NULL,
    started_at     DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    resolves_at    DATETIME(6)     NOT NULL,
    UNIQUE KEY uq_pvp_attacks_victim (victim_id),
    INDEX idx_pvp_attacks_resolves   (resolves_at),
    INDEX idx_pvp_attacks_attacker   (attacker_id),
    FOREIGN KEY (attacker_id) REFERENCES players(discord_id) ON DELETE CASCADE,
    FOREIGN KEY (victim_id)   REFERENCES players(discord_id) ON DELETE CASCADE,
    CHECK (attack_points > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================================================
-- MIGRATION (installations existantes) : ajout des colonnes de minage.
-- MySQL 8.0 ne supporte pas ADD COLUMN IF NOT EXISTS : exécuter ces
-- instructions une seule fois sur une base déjà déployée (ignorer si
-- l'erreur "Duplicate column name" apparaît, la colonne existe déjà).
--   ALTER TABLE players
--     ADD COLUMN mining_buffer DECIMAL(30, 5) NOT NULL DEFAULT 0.00000 AFTER network_defense,
--     ADD COLUMN mining_last_update_at DATETIME(6) NULL DEFAULT NULL AFTER mining_buffer,
--     ADD COLUMN mining_last_claim_at DATETIME(6) NULL DEFAULT NULL AFTER mining_last_update_at;
-- ====================================================================
-- MIGRATION (installations existantes) : identifiant secret joueur.
-- MySQL 8.0 ne supporte pas ADD COLUMN IF NOT EXISTS : exécuter ces
-- instructions une seule fois sur une base déjà déployée (ignorer si
-- l'erreur "Duplicate column name" / "Duplicate key name" apparaît).
--   ALTER TABLE players
--     ADD COLUMN secret_id CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NULL DEFAULT NULL AFTER lang,
--     ADD UNIQUE KEY uq_players_secret_id (secret_id);
-- ====================================================================
-- MIGRATION (installations existantes) : stock ATK + table hack.
--   ALTER TABLE players
--     ADD COLUMN attack_points BIGINT UNSIGNED NOT NULL DEFAULT 0 AFTER network_defense;
--   CREATE TABLE IF NOT EXISTS hack (
--     id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
--     discord_id BIGINT UNSIGNED NOT NULL,
--     method VARCHAR(16) NOT NULL,
--     bits_per_s BIGINT UNSIGNED NOT NULL DEFAULT 0,
--     atk_yield BIGINT UNSIGNED NOT NULL,
--     rtm_paid DECIMAL(30, 5) NOT NULL,
--     started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
--     expires_at DATETIME(6) NOT NULL,
--     UNIQUE KEY uq_hack_discord (discord_id),
--     INDEX idx_hack_expires (expires_at),
--     FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
--   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
-- Si bits_per_s existe déjà SANS DEFAULT (errno 1364 à l'INSERT) :
--   ALTER TABLE hack MODIFY bits_per_s BIGINT UNSIGNED NOT NULL DEFAULT 0;
-- Si bits_per_s a déjà été droppée :
--   ALTER TABLE hack ADD COLUMN bits_per_s BIGINT UNSIGNED NOT NULL DEFAULT 0 AFTER method;
-- Si t1..t5 existent encore :
--   ALTER TABLE hack
--     DROP COLUMN t1, DROP COLUMN t2, DROP COLUMN t3, DROP COLUMN t4, DROP COLUMN t5;
-- ====================================================================
-- MIGRATION (installations existantes) : adaptation hack pour /scan + consequence.
--   ALTER TABLE hack
--     ADD COLUMN type ENUM('compile','scan') NOT NULL DEFAULT 'compile' AFTER discord_id,
--     ADD COLUMN target_id BIGINT UNSIGNED NULL DEFAULT NULL AFTER type,
--     ADD COLUMN boost_rtm DECIMAL(30, 5) NOT NULL DEFAULT 0.00000 AFTER rtm_paid,
--     ADD INDEX idx_hack_target (target_id),
--     DROP INDEX uq_hack_discord,
--     ADD UNIQUE KEY uq_hack_discord_type (discord_id, type);
-- ====================================================================
-- MIGRATION (installations existantes) : table pvp_attacks pour /hack.
--   CREATE TABLE IF NOT EXISTS pvp_attacks (
--     id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
--     attacker_id BIGINT UNSIGNED NOT NULL,
--     victim_id BIGINT UNSIGNED NOT NULL,
--     attack_points BIGINT UNSIGNED NOT NULL,
--     target ENUM('mining', 'attack') NOT NULL,
--     started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
--     resolves_at DATETIME(6) NOT NULL,
--     UNIQUE KEY uq_pvp_attacks_victim (victim_id),
--     INDEX idx_pvp_attacks_resolves (resolves_at),
--     INDEX idx_pvp_attacks_attacker (attacker_id),
--     FOREIGN KEY (attacker_id) REFERENCES players(discord_id) ON DELETE CASCADE,
--     FOREIGN KEY (victim_id) REFERENCES players(discord_id) ON DELETE CASCADE,
--     CHECK (attack_points > 0)
--   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
-- ====================================================================


-- 9. Table des statistiques économiques agrégées par heure et par joueur
CREATE TABLE IF NOT EXISTS economy_hourly (
    bucket_start        DATETIME NOT NULL,
    player_id           BIGINT UNSIGNED NOT NULL,
    new_players         BIGINT UNSIGNED NOT NULL DEFAULT 0,
    returning_players   BIGINT UNSIGNED NOT NULL DEFAULT 0,
    claims              BIGINT UNSIGNED NOT NULL DEFAULT 0,
    full_claims         BIGINT UNSIGNED NOT NULL DEFAULT 0,
    mining_rtm          DECIMAL(38,5) NOT NULL DEFAULT 0,
    event_hash_usd      DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_pin_usd       DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_decode_usd    DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_anomaly_usd   DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_buffer_usd    DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_signal_usd    DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_packet_usd    DECIMAL(38,2) NOT NULL DEFAULT 0,
    grant_usd           DECIMAL(38,2) NOT NULL DEFAULT 0,
    miners_usd          DECIMAL(38,2) NOT NULL DEFAULT 0,
    miners_rtm          DECIMAL(38,5) NOT NULL DEFAULT 0,
    combat_usd          DECIMAL(38,2) NOT NULL DEFAULT 0,
    combat_rtm          DECIMAL(38,5) NOT NULL DEFAULT 0,
    upgrades_usd        DECIMAL(38,2) NOT NULL DEFAULT 0,
    hourly_claims       BIGINT UNSIGNED NOT NULL DEFAULT 0,
    hourly_usd          DECIMAL(38,2) NOT NULL DEFAULT 0,
    contracts_collected BIGINT UNSIGNED NOT NULL DEFAULT 0,
    contracts_usd       DECIMAL(38,2) NOT NULL DEFAULT 0,
    compile_rtm         DECIMAL(38,5) NOT NULL DEFAULT 0,
    scan_rtm            DECIMAL(38,5) NOT NULL DEFAULT 0,
    miners_t1           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    miners_t2           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    miners_t3           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    miners_t4           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    miners_t5           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    attack_bought       BIGINT UNSIGNED NOT NULL DEFAULT 0,
    defense_bought      BIGINT UNSIGNED NOT NULL DEFAULT 0,
    upgrades_started    BIGINT UNSIGNED NOT NULL DEFAULT 0,
    conversions         BIGINT UNSIGNED NOT NULL DEFAULT 0,
    converted_rtm       DECIMAL(38,5) NOT NULL DEFAULT 0,
    converted_usd       DECIMAL(38,2) NOT NULL DEFAULT 0,
    trades              BIGINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket_start, player_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Table de suivi des publications de bilans économiques (3 lignes max : 1h, 24h, 72h)
CREATE TABLE IF NOT EXISTS economy_reports (
    period_hours        SMALLINT UNSIGNED NOT NULL,
    tracking_start      DATETIME NOT NULL,
    next_start          DATETIME NOT NULL,
    pending_end         DATETIME NULL,
    pending_payload     JSON NULL,
    pending_channel_id  BIGINT UNSIGNED NULL,
    last_message_id     BIGINT UNSIGNED NULL,
    last_sent_at        DATETIME(6) NULL,
    PRIMARY KEY (period_hours)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. Table des journaux de récoltes journaliers (/claim) pour modération & anti-triche
CREATE TABLE IF NOT EXISTS daily_claim_logs (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id          BIGINT UNSIGNED NOT NULL,
    claimed_at          DATETIME(6)     NOT NULL,
    interval_seconds    INT UNSIGNED    NULL     DEFAULT NULL,
    amount              DECIMAL(30, 5)  NOT NULL DEFAULT 0.00000,
    is_auto             TINYINT(1)      NOT NULL DEFAULT 0,
    INDEX idx_daily_claims_user (discord_id, claimed_at),
    INDEX idx_daily_claims_time (claimed_at),
    INDEX idx_daily_claims_auto (is_auto),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. Table des journaux de disponibilité et de résolution des événements réseau
CREATE TABLE IF NOT EXISTS event_availability_logs (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event               VARCHAR(32)     NOT NULL,
    opened_at           DATETIME(6)     NOT NULL,
    solved_at           DATETIME(6)     NOT NULL,
    duration_seconds    INT UNSIGNED    NOT NULL,
    winner_id           BIGINT UNSIGNED NULL,
    reward              DECIMAL(30, 2)  NOT NULL DEFAULT 0.00,
    INDEX idx_event_solved (event, solved_at),
    INDEX idx_solved_at (solved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 13. Table des journaux d'exécution /hourly (surveillance, audit et anti-triche)
CREATE TABLE IF NOT EXISTS hourly_logs (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id          BIGINT UNSIGNED NOT NULL,
    claimed_at          DATETIME(6)     NOT NULL,
    interval_seconds    INT UNSIGNED    NULL     DEFAULT NULL,
    base_usd            DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    bonus_pct           DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    total_usd           DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    streak              INT UNSIGNED    NOT NULL DEFAULT 1,
    combo_lost          TINYINT(1)      NOT NULL DEFAULT 0,
    INDEX idx_hourly_logs_user (discord_id, claimed_at),
    INDEX idx_hourly_logs_time (claimed_at),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 14. Table des Rappels Personnalisés & Alertes de Jeu (/rmd)
CREATE TABLE IF NOT EXISTS reminders (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id    BIGINT UNSIGNED NOT NULL,
    channel_id    BIGINT UNSIGNED NULL DEFAULT NULL,
    guild_id      BIGINT UNSIGNED NULL DEFAULT NULL,
    reminder_type VARCHAR(32)     NOT NULL DEFAULT 'custom',
    target_event  VARCHAR(32)     NULL DEFAULT NULL,
    message       VARCHAR(255)    NOT NULL DEFAULT 'Rappel',
    created_at    DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    remind_at     DATETIME(6)     NOT NULL,
    INDEX idx_reminders_remind_at (remind_at),
    INDEX idx_reminders_discord (discord_id),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================================================
-- MIGRATION (installations existantes) : suivi économique.
-- Appliquer migrations/001_economy_reports.sql sur une base déjà déployée.
-- ====================================================================
-- MIGRATION (installations existantes) : suivi journalier des claims.
-- Appliquer migrations/002_daily_claim_logs.sql sur une base déjà déployée.
-- ====================================================================
-- MIGRATION (installations existantes) : journaux de disponibilité des événements.
-- Appliquer CREATE TABLE IF NOT EXISTS event_availability_logs (...).
-- ====================================================================
-- MIGRATION (installations existantes) : système d'autoclaim.
-- ALTER TABLE players ADD COLUMN autoclaim_credits INT UNSIGNED NOT NULL DEFAULT 0;
-- ALTER TABLE players ADD COLUMN autoclaim_active INT UNSIGNED NOT NULL DEFAULT 0;
-- ALTER TABLE players ADD INDEX idx_players_autoclaim_active (autoclaim_active);
-- ALTER TABLE daily_claim_logs ADD COLUMN is_auto TINYINT(1) NOT NULL DEFAULT 0;
-- ALTER TABLE daily_claim_logs ADD INDEX idx_daily_claims_auto (is_auto);
-- ====================================================================
-- MIGRATION (installations existantes) : récompense horaire (/hourly).
-- Appliquer migrations/003_hourly.sql sur une base déjà déployée.
-- ====================================================================
-- MIGRATION (installations existantes) : système de contrats (/contract).
-- ALTER TABLE players
--   ADD COLUMN contract_fidelity INT UNSIGNED NOT NULL DEFAULT 0 AFTER hourly_streak,
--   ADD COLUMN contracts_completed INT UNSIGNED NOT NULL DEFAULT 0 AFTER contract_fidelity;
-- CREATE TABLE IF NOT EXISTS contracts (
--   discord_id       BIGINT UNSIGNED NOT NULL,
--   duration_type    VARCHAR(16)     NOT NULL,
--   title            VARCHAR(128)    NOT NULL,
--   reward_usd       DECIMAL(30, 2)  NOT NULL,
--   is_special       TINYINT(1)      NOT NULL DEFAULT 0,
--   started_at       DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
--   expires_at       DATETIME(6)     NOT NULL,
--   notified         TINYINT(1)      NOT NULL DEFAULT 0,
--   PRIMARY KEY (discord_id),
--   FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE,
--   CHECK (duration_type IN ('short', 'medium', 'long')),
--   CHECK (reward_usd >= 0)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
-- ====================================================================
-- MIGRATION (installations existantes) : rappels et minuteurs (/rmd).
-- CREATE TABLE IF NOT EXISTS reminders (
--   id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
--   discord_id    BIGINT UNSIGNED NOT NULL,
--   channel_id    BIGINT UNSIGNED NULL DEFAULT NULL,
--   guild_id      BIGINT UNSIGNED NULL DEFAULT NULL,
--   reminder_type VARCHAR(32)     NOT NULL DEFAULT 'custom',
--   target_event  VARCHAR(32)     NULL DEFAULT NULL,
--   message       VARCHAR(255)    NOT NULL DEFAULT 'Rappel',
--   created_at    DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
--   remind_at     DATETIME(6)     NOT NULL,
--   INDEX idx_reminders_remind_at (remind_at),
--   INDEX idx_reminders_discord (discord_id),
--   FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
-- ====================================================================



