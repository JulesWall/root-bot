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
