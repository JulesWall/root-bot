-- ====================================================================
-- MIGRATION PvP V2 — Étape 2
-- Idempotent : utilise CREATE TABLE IF NOT EXISTS.
-- Ordre : tables sans dépendances d'abord, puis celles avec FK vers d'autres V2.
-- ====================================================================

CREATE TABLE IF NOT EXISTS pvp_v2_research_folders (
  id           BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
  owner_id     BIGINT UNSIGNED     NOT NULL,
  channel      ENUM('offense','defense') NOT NULL,
  family       VARCHAR(32)         NOT NULL,
  tier         TINYINT UNSIGNED    NOT NULL,
  fingerprint  CHAR(4)             NOT NULL,
  created_at   DATETIME(6)         NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_folder_family_fp (family, fingerprint),
  INDEX idx_folder_owner (owner_id),
  FOREIGN KEY (owner_id) REFERENCES players(discord_id) ON DELETE CASCADE,
  CHECK (tier BETWEEN 1 AND 6),
  CHECK (channel IN ('offense', 'defense'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pvp_v2_software_copies (
  id           BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
  owner_id     BIGINT UNSIGNED     NOT NULL,
  family       VARCHAR(32)         NOT NULL,
  tier         TINYINT UNSIGNED    NOT NULL,
  fingerprint  CHAR(4)             NOT NULL,
  origin       ENUM('compiled','purchased','stolen') NOT NULL DEFAULT 'compiled',
  resellable   TINYINT(1)          NOT NULL DEFAULT 1,
  reserved     TINYINT(1)          NOT NULL DEFAULT 0,
  created_at   DATETIME(6)         NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  INDEX idx_copy_owner (owner_id),
  INDEX idx_copy_fingerprint (fingerprint),
  FOREIGN KEY (owner_id) REFERENCES players(discord_id) ON DELETE CASCADE,
  CHECK (tier BETWEEN 1 AND 6),
  CHECK (resellable IN (0, 1)),
  CHECK (reserved IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pvp_v2_patches (
  id           BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
  owner_id     BIGINT UNSIGNED     NOT NULL,
  family       VARCHAR(32)         NOT NULL,
  fingerprint  CHAR(4)             NOT NULL,
  installed    TINYINT(1)          NOT NULL DEFAULT 0,
  installed_at DATETIME(6)         NULL,
  reserved     TINYINT(1)          NOT NULL DEFAULT 0,
  created_at   DATETIME(6)         NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  INDEX idx_patch_owner_fp (owner_id, fingerprint),
  INDEX idx_patch_owner_installed (owner_id, installed),
  FOREIGN KEY (owner_id) REFERENCES players(discord_id) ON DELETE CASCADE,
  CHECK (installed IN (0, 1)),
  CHECK (reserved IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pvp_v2_dev_jobs (
  id           BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
  player_id    BIGINT UNSIGNED     NOT NULL,
  channel      ENUM('offense','defense') NOT NULL,
  job_type     ENUM('research','compile','patch_research','patch_compile') NOT NULL,
  family       VARCHAR(32)         NOT NULL,
  tier         TINYINT UNSIGNED    NOT NULL,
  fingerprint  CHAR(4)             NULL DEFAULT NULL,
  rtm_paid     DECIMAL(30, 5)      NOT NULL,
  bits_per_s   BIGINT UNSIGNED     NOT NULL DEFAULT 0,
  started_at   DATETIME(6)         NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  resolves_at  DATETIME(6)         NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_job_player_channel (player_id, channel),
  INDEX idx_job_resolves_at (resolves_at),
  INDEX idx_job_player (player_id),
  FOREIGN KEY (player_id) REFERENCES players(discord_id) ON DELETE CASCADE,
  CHECK (tier BETWEEN 1 AND 6),
  CHECK (rtm_paid >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pvp_v2_operations (
  id                BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
  attacker_id       BIGINT UNSIGNED     NOT NULL,
  victim_id         BIGINT UNSIGNED     NOT NULL,
  family            VARCHAR(32)         NOT NULL,
  tier              TINYINT UNSIGNED    NOT NULL,
  fingerprint       CHAR(4)             NOT NULL,
  software_copy_id  BIGINT UNSIGNED     NOT NULL,
  status            ENUM('installing','active','completed','failed','cancelled') NOT NULL DEFAULT 'installing',
  rtm_cost          DECIMAL(30, 5)      NOT NULL DEFAULT 0,
  started_at        DATETIME(6)         NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  resolves_at       DATETIME(6)         NULL DEFAULT NULL,
  installed_at      DATETIME(6)         NULL,
  ended_at          DATETIME(6)         NULL,
  end_reason        VARCHAR(32)         NULL,
  PRIMARY KEY (id),
  INDEX idx_op_attacker_status (attacker_id, status),
  INDEX idx_op_victim_status (victim_id, status),
  INDEX idx_op_started_at (started_at),
  INDEX idx_op_resolves_at (status, resolves_at),
  FOREIGN KEY (attacker_id) REFERENCES players(discord_id) ON DELETE CASCADE,
  FOREIGN KEY (victim_id)   REFERENCES players(discord_id) ON DELETE CASCADE,
  FOREIGN KEY (software_copy_id) REFERENCES pvp_v2_software_copies(id) ON DELETE RESTRICT,
  CHECK (tier BETWEEN 1 AND 6),
  CHECK (rtm_cost >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pvp_v2_active_effects (
  id           BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
  operation_id BIGINT UNSIGNED     NOT NULL,
  attacker_id  BIGINT UNSIGNED     NOT NULL,
  victim_id    BIGINT UNSIGNED     NOT NULL,
  family       VARCHAR(32)         NOT NULL,
  tier         TINYINT UNSIGNED    NOT NULL,
  fingerprint  CHAR(4)             NOT NULL,
  effect_data  JSON                NULL,
  started_at   DATETIME(6)         NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  ended_at     DATETIME(6)         NULL,
  end_reason   VARCHAR(32)         NULL,
  PRIMARY KEY (id),
  INDEX idx_effect_victim_active (victim_id, ended_at),
  INDEX idx_effect_attacker_active (attacker_id, ended_at),
  INDEX idx_effect_fp_victim (fingerprint, victim_id),
  FOREIGN KEY (operation_id) REFERENCES pvp_v2_operations(id) ON DELETE CASCADE,
  FOREIGN KEY (attacker_id)  REFERENCES players(discord_id) ON DELETE CASCADE,
  FOREIGN KEY (victim_id)    REFERENCES players(discord_id) ON DELETE CASCADE,
  CHECK (tier BETWEEN 1 AND 6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table pvp_v2_scan_reports supprimée : les rapports de scan ne sont plus archivés en base
DROP TABLE IF EXISTS pvp_v2_scan_reports;

CREATE TABLE IF NOT EXISTS pvp_v2_espionage_reports (
  id           BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
  attacker_id  BIGINT UNSIGNED     NOT NULL,
  victim_id    BIGINT UNSIGNED     NOT NULL,
  scanned_at   DATETIME(6)         NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  expires_at   DATETIME(6)         NOT NULL,
  report_data  JSON                NOT NULL,
  PRIMARY KEY (id),
  INDEX idx_espionage_attacker (attacker_id, scanned_at),
  INDEX idx_espionage_expires (expires_at),
  FOREIGN KEY (attacker_id) REFERENCES players(discord_id) ON DELETE CASCADE,
  FOREIGN KEY (victim_id)   REFERENCES players(discord_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pvp_v2_market_listings (
  id           BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
  seller_id    BIGINT UNSIGNED     NOT NULL,
  item_type    ENUM('research_folder','compiled_software','patch') NOT NULL,
  item_id      BIGINT UNSIGNED     NOT NULL,
  price_usd    DECIMAL(30, 2)      NOT NULL,
  status       ENUM('active','sold','cancelled','expired') NOT NULL DEFAULT 'active',
  listed_at    DATETIME(6)         NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  expires_at   DATETIME(6)         NULL,
  sold_to      BIGINT UNSIGNED     NULL,
  sold_at      DATETIME(6)         NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_listing_item_active (item_type, item_id, status),
  INDEX idx_listing_seller (seller_id, status),
  INDEX idx_listing_market (status, item_type),
  INDEX idx_listing_expires (expires_at),
  FOREIGN KEY (seller_id) REFERENCES players(discord_id) ON DELETE CASCADE,
  CHECK (price_usd >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================================================
-- MIGRATION PvP V2 — Étape 6 : Hostile Miner & Opérations Offensives
-- Note : Le code utilise directement la colonne existante `installed_at`
-- pour planifier et résoudre l'échéance de l'installation, évitant ainsi
-- un ALTER TABLE obligatoire en production si le compte DB n'a pas les droits DDL.
-- Les commandes ci-dessous restent purement optionnelles :
-- ALTER TABLE pvp_v2_operations ADD COLUMN resolves_at DATETIME(6) NULL DEFAULT NULL AFTER started_at;
-- ALTER TABLE pvp_v2_operations ADD INDEX idx_op_resolves_at (status, resolves_at);

-- ====================================================================
-- MIGRATION PvP V2 — Étape 17 : Conversion finale du stock attack_points (1 AP = 20 USD)
-- ====================================================================
-- UPDATE players SET dollars = dollars + (attack_points * 20), attack_points = 0 WHERE attack_points > 0;

