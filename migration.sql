-- Migration SQL : Refonte Graphique Root OS (v3.0.0)
-- Aucune modification de schéma requise (les colonnes existantes supportent l'infrastructure 0 à 5).

-- Migration SQL : Contrats Dynamiques V2
ALTER TABLE contracts MODIFY COLUMN title VARCHAR(255) NOT NULL;
ALTER TABLE contracts MODIFY COLUMN duration_type VARCHAR(32) NOT NULL;

-- Migration SQL : Macros Joueur (Système d'automatisation)
CREATE TABLE IF NOT EXISTS macros (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id  BIGINT UNSIGNED NOT NULL,
    name        VARCHAR(32) NOT NULL,
    created_at  DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at  DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_macro_owner_name (discord_id, name),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS macro_steps (
    macro_id  BIGINT UNSIGNED NOT NULL,
    position  TINYINT UNSIGNED NOT NULL,
    method    VARCHAR(32) NOT NULL,
    args_json JSON NOT NULL,
    PRIMARY KEY (macro_id, position),
    FOREIGN KEY (macro_id) REFERENCES macros(id) ON DELETE CASCADE,
    CHECK (position BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS macro_runs (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id  BIGINT UNSIGNED NOT NULL,
    started_at  DATETIME(6) NOT NULL,
    INDEX idx_macro_runs_owner_time (discord_id, started_at),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Migration SQL : Procédure de sauvegarde et dégâts critiques PvP
ALTER TABLE players ADD COLUMN critical_lock_until DATETIME(6) NULL DEFAULT NULL;

-- Migration SQL : Cours dynamique du RTM (etat courant + historique 15 min)
CREATE TABLE IF NOT EXISTS rtm_market_state (
    id           TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    price_usd    DECIMAL(24,8) NOT NULL,
    market_ts    DATETIME(0)   NOT NULL,
    observed_at  DATETIME(6)   NOT NULL,
    status       VARCHAR(16)   NOT NULL DEFAULT 'live',
    source       VARCHAR(32)   NOT NULL,
    CHECK (id = 1),
    CHECK (price_usd > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO rtm_market_state (id, price_usd, market_ts, observed_at, status, source)
VALUES (1, 43567, UTC_TIMESTAMP(), UTC_TIMESTAMP(6), 'seed', 'seed');

CREATE TABLE IF NOT EXISTS rtm_market_history (
    market_ts     DATETIME(0)   NOT NULL PRIMARY KEY,
    price_before  DECIMAL(24,8) NOT NULL,
    price_after   DECIMAL(24,8) NOT NULL,
    btc_pct       DECIMAL(12,6) NOT NULL,
    eth_pct       DECIMAL(12,6) NOT NULL,
    sol_pct       DECIMAL(12,6) NOT NULL,
    avg_pct       DECIMAL(12,6) NOT NULL,
    capped        TINYINT(1)    NOT NULL DEFAULT 0,
    source        VARCHAR(32)   NOT NULL,
    created_at    DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Migration SQL : Alertes de cours du RTM
CREATE TABLE IF NOT EXISTS rtm_price_alerts (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id       BIGINT UNSIGNED NOT NULL,
    direction        ENUM('above','below') NOT NULL,
    threshold_usd    DECIMAL(24,8) NOT NULL,
    cooldown_minutes INT UNSIGNED NOT NULL DEFAULT 60,
    enabled          TINYINT(1) NOT NULL DEFAULT 1,
    armed            TINYINT(1) NOT NULL DEFAULT 1,
    last_notified_at DATETIME(6) NULL,
    created_at       DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_alert (discord_id, direction, threshold_usd),
    INDEX idx_alert_enabled (enabled, armed),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Migration SQL : Vente automatique de Rootium (RTM)
CREATE TABLE IF NOT EXISTS rtm_auto_sell_rules (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    discord_id       BIGINT UNSIGNED NOT NULL,
    direction        ENUM('above','below') NOT NULL,
    threshold_usd    DECIMAL(24,8) NOT NULL,
    mode             ENUM('fixed','percent') NOT NULL DEFAULT 'fixed',
    amount_rtm       DECIMAL(20,5) NULL DEFAULT NULL,
    percent          DECIMAL(5,2) NULL DEFAULT NULL,
    max_rtm_per_run  DECIMAL(20,5) NULL DEFAULT NULL,
    cooldown_minutes INT UNSIGNED NOT NULL DEFAULT 60,
    repeat_mode      ENUM('once','repeat') NOT NULL DEFAULT 'once',
    enabled          TINYINT(1) NOT NULL DEFAULT 1,
    last_run_at      DATETIME(6) NULL DEFAULT NULL,
    created_at       DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_auto_sell_eligible (enabled, direction, threshold_usd),
    INDEX idx_auto_sell_user (discord_id),
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS rtm_auto_sell_runs (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    rule_id     BIGINT UNSIGNED NOT NULL,
    discord_id  BIGINT UNSIGNED NOT NULL,
    market_ts   DATETIME(0) NOT NULL,
    rate_usd    DECIMAL(24,8) NOT NULL,
    rtm_amount  DECIMAL(20,5) NOT NULL,
    usd_amount  DECIMAL(24,2) NOT NULL,
    created_at  DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_rule_cycle (rule_id, market_ts),
    INDEX idx_runs_user (discord_id, created_at),
    FOREIGN KEY (rule_id) REFERENCES rtm_auto_sell_rules(id) ON DELETE CASCADE,
    FOREIGN KEY (discord_id) REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
