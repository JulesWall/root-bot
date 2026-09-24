-- ====================================================================
-- Root Bot - Script de Migration Idempotent (MySQL 8.0+)
-- Création individuelle de chaque colonne dans chaque table si absente
-- ====================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET time_zone = '+00:00';
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- --------------------------------------------------------------------
-- Procédures stockées temporaires pour modifications idempotentes
-- --------------------------------------------------------------------
DELIMITER 

DROP PROCEDURE IF EXISTS add_column_if_not_exists 
CREATE PROCEDURE add_column_if_not_exists(
    IN p_table_name VARCHAR(64),
    IN p_column_name VARCHAR(64),
    IN p_column_definition TEXT
)
BEGIN
    DECLARE col_exists INT DEFAULT 0;

    SELECT COUNT(*) INTO col_exists
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND COLUMN_NAME = p_column_name;

    IF col_exists = 0 THEN
        SET @sql = CONCAT('ALTER TABLE ', p_table_name, ' ADD COLUMN ', p_column_name, ' ', p_column_definition);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END 

DROP PROCEDURE IF EXISTS add_index_if_not_exists 
CREATE PROCEDURE add_index_if_not_exists(
    IN p_table_name VARCHAR(64),
    IN p_index_name VARCHAR(64),
    IN p_index_definition TEXT
)
BEGIN
    DECLARE idx_exists INT DEFAULT 0;

    SELECT COUNT(*) INTO idx_exists
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND INDEX_NAME = p_index_name;

    IF idx_exists = 0 THEN
        SET @sql = CONCAT('ALTER TABLE ', p_table_name, ' ADD ', p_index_definition);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END 

DROP PROCEDURE IF EXISTS add_foreign_key_if_not_exists 
CREATE PROCEDURE add_foreign_key_if_not_exists(
    IN p_table_name VARCHAR(64),
    IN p_constraint_name VARCHAR(64),
    IN p_fk_definition TEXT
)
BEGIN
    DECLARE fk_exists INT DEFAULT 0;

    SELECT COUNT(*) INTO fk_exists
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND CONSTRAINT_NAME = p_constraint_name
      AND CONSTRAINT_TYPE = 'FOREIGN KEY';

    IF fk_exists = 0 THEN
        SET @sql = CONCAT('ALTER TABLE ', p_table_name, ' ADD CONSTRAINT ', p_constraint_name, ' ', p_fk_definition);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END 

DELIMITER ;

-- ====================================================================
-- 1. TABLE : players
-- ====================================================================
CREATE TABLE IF NOT EXISTS players (
    discord_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (discord_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('players', 'discord_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('players', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL add_column_if_not_exists('players', 'dollars', 'DECIMAL(30, 2) NOT NULL DEFAULT 0.00');
CALL add_column_if_not_exists('players', 'rootium', 'DECIMAL(30, 5) NOT NULL DEFAULT 0.00000');
CALL add_column_if_not_exists('players', 'firewall_level', 'TINYINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'reputation', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'next_reputation_at', 'DATETIME(6) NULL DEFAULT NULL');

-- Modules de Minage (Tiers 1 à 6)
CALL add_column_if_not_exists('players', 'mining_t1', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'mining_t2', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'mining_t3', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'mining_t4', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'mining_t5', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'mining_t6', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');

-- Modules d\'Attaque (Tiers 1 à 6)
CALL add_column_if_not_exists('players', 'attack_t1', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'attack_t2', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'attack_t3', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'attack_t4', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'attack_t5', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'attack_t6', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');

-- Modules de Défense de Baie (Tiers 1 à 6)
CALL add_column_if_not_exists('players', 'bay_defense_t1', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'bay_defense_t2', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'bay_defense_t3', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'bay_defense_t4', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'bay_defense_t5', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'bay_defense_t6', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');

-- Défense globale et points d\'attaque
CALL add_column_if_not_exists('players', 'network_defense', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'attack_points', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');

-- Minage & Récoltes (/claim)
CALL add_column_if_not_exists('players', 'mining_buffer', 'DECIMAL(30, 5) NOT NULL DEFAULT 0.00000');
CALL add_column_if_not_exists('players', 'mining_last_update_at', 'DATETIME(6) NULL DEFAULT NULL');
CALL add_column_if_not_exists('players', 'mining_last_claim_at', 'DATETIME(6) NULL DEFAULT NULL');

-- Statistiques, langue et identifiant secret
CALL add_column_if_not_exists('players', 'events_won', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'lang', 'VARCHAR(2) NULL DEFAULT NULL');
CALL add_column_if_not_exists('players', 'secret_id', 'CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NULL DEFAULT NULL');

-- Autoclaim
CALL add_column_if_not_exists('players', 'autoclaim_credits', 'INT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'autoclaim_active', 'INT UNSIGNED NOT NULL DEFAULT 0');

-- Récompense horaire (/hourly)
CALL add_column_if_not_exists('players', 'hourly_last_at', 'DATETIME(6) NULL DEFAULT NULL');
CALL add_column_if_not_exists('players', 'hourly_combo_bonus', 'DECIMAL(10, 2) NOT NULL DEFAULT 0.00');
CALL add_column_if_not_exists('players', 'hourly_streak', 'INT UNSIGNED NOT NULL DEFAULT 0');

-- Contrats de travail (/contract)
CALL add_column_if_not_exists('players', 'contract_fidelity', 'INT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('players', 'contracts_completed', 'INT UNSIGNED NOT NULL DEFAULT 0');

-- Index de la table players
CALL add_index_if_not_exists('players', 'uq_players_secret_id', 'UNIQUE KEY uq_players_secret_id (secret_id)');
CALL add_index_if_not_exists('players', 'idx_players_autoclaim_active', 'INDEX idx_players_autoclaim_active (utoclaim_active)');

-- ====================================================================
-- 2. TABLE : guild_prefixes
-- ====================================================================
CREATE TABLE IF NOT EXISTS guild_prefixes (
    guild_id BIGINT UNSIGNED NOT NULL,
    prefix VARCHAR(32) NOT NULL,
    PRIMARY KEY (guild_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('guild_prefixes', 'guild_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('guild_prefixes', 'prefix', 'VARCHAR(32) NOT NULL');

-- ====================================================================
-- 3. TABLE : upgrades
-- ====================================================================
CREATE TABLE IF NOT EXISTS upgrades (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('upgrades', 'discord_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('upgrades', 'item_type', 'VARCHAR(32) NOT NULL DEFAULT \'firewall\'');
CALL add_column_if_not_exists('upgrades', 'target_level', 'TINYINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('upgrades', 'started_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL add_column_if_not_exists('upgrades', 'expires_at', 'DATETIME(6) NOT NULL');

CALL add_index_if_not_exists('upgrades', 'idx_upgrades_expires', 'INDEX idx_upgrades_expires (expires_at)');
CALL add_index_if_not_exists('upgrades', 'idx_upgrades_discord', 'INDEX idx_upgrades_discord (discord_id)');
CALL add_foreign_key_if_not_exists('upgrades', 'fk_upgrades_discord_id', 'FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE');

-- ====================================================================
-- 4. TABLE : hack
-- ====================================================================
CREATE TABLE IF NOT EXISTS hack (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('hack', 'discord_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('hack', 'type', 'ENUM(\'compile\', \'scan\') NOT NULL DEFAULT \'compile\'');
CALL add_column_if_not_exists('hack', 'target_id', 'BIGINT UNSIGNED NULL DEFAULT NULL');
CALL add_column_if_not_exists('hack', 'method', 'VARCHAR(16) NOT NULL');
CALL add_column_if_not_exists('hack', 'bits_per_s', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('hack', 'atk_yield', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('hack', 'rtm_paid', 'DECIMAL(30, 5) NOT NULL DEFAULT 0.00000');
CALL add_column_if_not_exists('hack', 'boost_rtm', 'DECIMAL(30, 5) NOT NULL DEFAULT 0.00000');
CALL add_column_if_not_exists('hack', 'started_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL add_column_if_not_exists('hack', 'expires_at', 'DATETIME(6) NOT NULL');

CALL add_index_if_not_exists('hack', 'uq_hack_discord_type', 'UNIQUE KEY uq_hack_discord_type (discord_id, 	ype)');
CALL add_index_if_not_exists('hack', 'idx_hack_expires', 'INDEX idx_hack_expires (expires_at)');
CALL add_index_if_not_exists('hack', 'idx_hack_target', 'INDEX idx_hack_target (	arget_id)');
CALL add_foreign_key_if_not_exists('hack', 'fk_hack_discord_id', 'FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE');
CALL add_foreign_key_if_not_exists('hack', 'fk_hack_target_id', 'FOREIGN KEY (	arget_id) REFERENCES players(discord_id) ON DELETE CASCADE');

-- ====================================================================
-- 5. TABLE : contracts
-- ====================================================================
CREATE TABLE IF NOT EXISTS contracts (
    discord_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (discord_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('contracts', 'discord_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('contracts', 'duration_type', 'VARCHAR(16) NOT NULL');
CALL add_column_if_not_exists('contracts', 'title', 'VARCHAR(128) NOT NULL');
CALL add_column_if_not_exists('contracts', 'reward_usd', 'DECIMAL(30, 2) NOT NULL DEFAULT 0.00');
CALL add_column_if_not_exists('contracts', 'is_special', 'TINYINT(1) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('contracts', 'started_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL add_column_if_not_exists('contracts', 'expires_at', 'DATETIME(6) NOT NULL');
CALL add_column_if_not_exists('contracts', 'notified', 'TINYINT(1) NOT NULL DEFAULT 0');

CALL add_foreign_key_if_not_exists('contracts', 'fk_contracts_discord_id', 'FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE');

-- ====================================================================
-- 6. TABLE : events
-- ====================================================================
CREATE TABLE IF NOT EXISTS events (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('events', 'event', 'VARCHAR(32) NOT NULL');
CALL add_column_if_not_exists('events', 'next_at', 'DATETIME(6) NOT NULL');
CALL add_column_if_not_exists('events', 'last_found_by', 'BIGINT UNSIGNED NULL DEFAULT NULL');
CALL add_column_if_not_exists('events', 'last_found_on', 'VARCHAR(128) NULL DEFAULT NULL');
CALL add_column_if_not_exists('events', 'last_reward', 'DECIMAL(30, 2) NOT NULL DEFAULT 0.00');

CALL add_index_if_not_exists('events', 'uq_events_event', 'UNIQUE KEY uq_events_event (event)');

-- ====================================================================
-- 7. TABLE : daily_event_stats
-- ====================================================================
CREATE TABLE IF NOT EXISTS daily_event_stats (
    discord_id BIGINT UNSIGNED NOT NULL,
    date_key DATE NOT NULL DEFAULT (CURRENT_DATE),
    PRIMARY KEY (discord_id, date_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('daily_event_stats', 'discord_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('daily_event_stats', 'date_key', 'DATE NOT NULL DEFAULT (CURRENT_DATE)');
CALL add_column_if_not_exists('daily_event_stats', 'events_won', 'INT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('daily_event_stats', 'events_participated', 'INT UNSIGNED NOT NULL DEFAULT 0');

CALL add_index_if_not_exists('daily_event_stats', 'idx_event_stats_date', 'INDEX idx_event_stats_date (date_key)');

-- ====================================================================
-- 8. TABLE : consequence
-- ====================================================================
CREATE TABLE IF NOT EXISTS consequence (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('consequence', 'victim_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('consequence', 'attacker_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('consequence', 'delete_at', 'DATETIME(6) NOT NULL');

CALL add_index_if_not_exists('consequence', 'idx_consequence_victim', 'INDEX idx_consequence_victim (ictim_id)');
CALL add_index_if_not_exists('consequence', 'idx_consequence_delete_at', 'INDEX idx_consequence_delete_at (delete_at)');
CALL add_foreign_key_if_not_exists('consequence', 'fk_consequence_victim_id', 'FOREIGN KEY (ictim_id) REFERENCES players(discord_id) ON DELETE CASCADE');
CALL add_foreign_key_if_not_exists('consequence', 'fk_consequence_attacker_id', 'FOREIGN KEY (ttacker_id) REFERENCES players(discord_id) ON DELETE CASCADE');

-- ====================================================================
-- 9. TABLE : pvp_attacks
-- ====================================================================
CREATE TABLE IF NOT EXISTS pvp_attacks (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('pvp_attacks', 'attacker_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('pvp_attacks', 'victim_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('pvp_attacks', 'attack_points', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('pvp_attacks', 'target', 'ENUM(\'mining\', \'attack\') NOT NULL');
CALL add_column_if_not_exists('pvp_attacks', 'started_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL add_column_if_not_exists('pvp_attacks', 'resolves_at', 'DATETIME(6) NOT NULL');

CALL add_index_if_not_exists('pvp_attacks', 'uq_pvp_attacks_victim', 'UNIQUE KEY uq_pvp_attacks_victim (ictim_id)');
CALL add_index_if_not_exists('pvp_attacks', 'idx_pvp_attacks_resolves', 'INDEX idx_pvp_attacks_resolves (
esolves_at)');
CALL add_index_if_not_exists('pvp_attacks', 'idx_pvp_attacks_attacker', 'INDEX idx_pvp_attacks_attacker (ttacker_id)');
CALL add_foreign_key_if_not_exists('pvp_attacks', 'fk_pvp_attacks_attacker_id', 'FOREIGN KEY (ttacker_id) REFERENCES players(discord_id) ON DELETE CASCADE');
CALL add_foreign_key_if_not_exists('pvp_attacks', 'fk_pvp_attacks_victim_id', 'FOREIGN KEY (ictim_id) REFERENCES players(discord_id) ON DELETE CASCADE');

-- ====================================================================
-- 10. TABLE : economy_hourly
-- ====================================================================
CREATE TABLE IF NOT EXISTS economy_hourly (
    ucket_start DATETIME NOT NULL,
    player_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (ucket_start, player_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('economy_hourly', 'bucket_start', 'DATETIME NOT NULL');
CALL add_column_if_not_exists('economy_hourly', 'player_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('economy_hourly', 'new_players', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'returning_players', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'claims', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'full_claims', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'mining_rtm', 'DECIMAL(38, 5) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'event_hash_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'event_pin_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'event_decode_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'event_anomaly_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'event_buffer_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'event_signal_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'event_packet_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'grant_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'miners_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'miners_rtm', 'DECIMAL(38, 5) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'combat_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'combat_rtm', 'DECIMAL(38, 5) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'upgrades_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'hourly_claims', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'hourly_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'contracts_collected', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'contracts_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'compile_rtm', 'DECIMAL(38, 5) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'scan_rtm', 'DECIMAL(38, 5) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'miners_t1', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'miners_t2', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'miners_t3', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'miners_t4', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'miners_t5', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'attack_bought', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'defense_bought', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'upgrades_started', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'conversions', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'converted_rtm', 'DECIMAL(38, 5) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'converted_usd', 'DECIMAL(38, 2) NOT NULL DEFAULT 0');
CALL add_column_if_not_exists('economy_hourly', 'trades', 'BIGINT UNSIGNED NOT NULL DEFAULT 0');

-- ====================================================================
-- 11. TABLE : economy_reports
-- ====================================================================
CREATE TABLE IF NOT EXISTS economy_reports (
    period_hours SMALLINT UNSIGNED NOT NULL PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('economy_reports', 'period_hours', 'SMALLINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('economy_reports', 'tracking_start', 'DATETIME NOT NULL');
CALL add_column_if_not_exists('economy_reports', 'next_start', 'DATETIME NOT NULL');
CALL add_column_if_not_exists('economy_reports', 'pending_end', 'DATETIME NULL');
CALL add_column_if_not_exists('economy_reports', 'pending_payload', 'JSON NULL');
CALL add_column_if_not_exists('economy_reports', 'pending_channel_id', 'BIGINT UNSIGNED NULL');
CALL add_column_if_not_exists('economy_reports', 'last_message_id', 'BIGINT UNSIGNED NULL');
CALL add_column_if_not_exists('economy_reports', 'last_sent_at', 'DATETIME(6) NULL');

-- ====================================================================
-- 12. TABLE : daily_claim_logs
-- ====================================================================
CREATE TABLE IF NOT EXISTS daily_claim_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('daily_claim_logs', 'discord_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('daily_claim_logs', 'claimed_at', 'DATETIME(6) NOT NULL');
CALL add_column_if_not_exists('daily_claim_logs', 'interval_seconds', 'INT UNSIGNED NULL DEFAULT NULL');
CALL add_column_if_not_exists('daily_claim_logs', 'amount', 'DECIMAL(30, 5) NOT NULL DEFAULT 0.00000');
CALL add_column_if_not_exists('daily_claim_logs', 'is_auto', 'TINYINT(1) NOT NULL DEFAULT 0');

CALL add_index_if_not_exists('daily_claim_logs', 'idx_daily_claims_user', 'INDEX idx_daily_claims_user (discord_id, claimed_at)');
CALL add_index_if_not_exists('daily_claim_logs', 'idx_daily_claims_time', 'INDEX idx_daily_claims_time (claimed_at)');
CALL add_index_if_not_exists('daily_claim_logs', 'idx_daily_claims_auto', 'INDEX idx_daily_claims_auto (is_auto)');
CALL add_foreign_key_if_not_exists('daily_claim_logs', 'fk_daily_claims_discord_id', 'FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE');

-- ====================================================================
-- 13. TABLE : event_availability_logs
-- ====================================================================
CREATE TABLE IF NOT EXISTS event_availability_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('event_availability_logs', 'event', 'VARCHAR(32) NOT NULL');
CALL add_column_if_not_exists('event_availability_logs', 'opened_at', 'DATETIME(6) NOT NULL');
CALL add_column_if_not_exists('event_availability_logs', 'solved_at', 'DATETIME(6) NOT NULL');
CALL add_column_if_not_exists('event_availability_logs', 'duration_seconds', 'INT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('event_availability_logs', 'winner_id', 'BIGINT UNSIGNED NULL');
CALL add_column_if_not_exists('event_availability_logs', 'reward', 'DECIMAL(30, 2) NOT NULL DEFAULT 0.00');

CALL add_index_if_not_exists('event_availability_logs', 'idx_event_solved', 'INDEX idx_event_solved (event, solved_at)');
CALL add_index_if_not_exists('event_availability_logs', 'idx_solved_at', 'INDEX idx_solved_at (solved_at)');

-- ====================================================================
-- 14. TABLE : hourly_logs
-- ====================================================================
CREATE TABLE IF NOT EXISTS hourly_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('hourly_logs', 'discord_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('hourly_logs', 'claimed_at', 'DATETIME(6) NOT NULL');
CALL add_column_if_not_exists('hourly_logs', 'interval_seconds', 'INT UNSIGNED NULL DEFAULT NULL');
CALL add_column_if_not_exists('hourly_logs', 'base_usd', 'DECIMAL(10, 2) NOT NULL DEFAULT 0.00');
CALL add_column_if_not_exists('hourly_logs', 'bonus_pct', 'DECIMAL(10, 2) NOT NULL DEFAULT 0.00');
CALL add_column_if_not_exists('hourly_logs', 'total_usd', 'DECIMAL(10, 2) NOT NULL DEFAULT 0.00');
CALL add_column_if_not_exists('hourly_logs', 'streak', 'INT UNSIGNED NOT NULL DEFAULT 1');
CALL add_column_if_not_exists('hourly_logs', 'combo_lost', 'TINYINT(1) NOT NULL DEFAULT 0');

CALL add_index_if_not_exists('hourly_logs', 'idx_hourly_logs_user', 'INDEX idx_hourly_logs_user (discord_id, claimed_at)');
CALL add_index_if_not_exists('hourly_logs', 'idx_hourly_logs_time', 'INDEX idx_hourly_logs_time (claimed_at)');
CALL add_foreign_key_if_not_exists('hourly_logs', 'fk_hourly_logs_discord_id', 'FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE');

-- ====================================================================
-- 15. TABLE : reminders
-- ====================================================================
CREATE TABLE IF NOT EXISTS 
eminders (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CALL add_column_if_not_exists('reminders', 'discord_id', 'BIGINT UNSIGNED NOT NULL');
CALL add_column_if_not_exists('reminders', 'channel_id', 'BIGINT UNSIGNED NULL DEFAULT NULL');
CALL add_column_if_not_exists('reminders', 'guild_id', 'BIGINT UNSIGNED NULL DEFAULT NULL');
CALL add_column_if_not_exists('reminders', 'reminder_type', 'VARCHAR(32) NOT NULL DEFAULT \'custom\'');
CALL add_column_if_not_exists('reminders', 'target_event', 'VARCHAR(32) NULL DEFAULT NULL');
CALL add_column_if_not_exists('reminders', 'message', 'VARCHAR(255) NOT NULL DEFAULT \'Rappel\'');
CALL add_column_if_not_exists('reminders', 'created_at', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL add_column_if_not_exists('reminders', 'remind_at', 'DATETIME(6) NOT NULL');

CALL add_index_if_not_exists('reminders', 'idx_reminders_remind_at', 'INDEX idx_reminders_remind_at (
emind_at)');
CALL add_index_if_not_exists('reminders', 'idx_reminders_discord', 'INDEX idx_reminders_discord (discord_id)');
CALL add_foreign_key_if_not_exists('reminders', 'fk_reminders_discord_id', 'FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE');

-- --------------------------------------------------------------------
-- Nettoyage des procédures temporaires
-- --------------------------------------------------------------------
DROP PROCEDURE IF EXISTS add_column_if_not_exists;
DROP PROCEDURE IF EXISTS add_index_if_not_exists;
DROP PROCEDURE IF EXISTS add_foreign_key_if_not_exists;
