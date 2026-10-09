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
