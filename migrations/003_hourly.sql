-- ====================================================================
-- Root Bot - Migration 003 : récompense horaire (/hourly)
-- Installations existantes (MySQL 8.0+). Schéma cible : root.sql.
--
-- MySQL 8.0 ne supporte pas ADD COLUMN IF NOT EXISTS ni
-- ADD CONSTRAINT IF NOT EXISTS : exécuter ce fichier une seule fois
-- sur une base déjà déployée qui n'a pas encore ces colonnes / cette
-- table. Ignorer si l'erreur "Duplicate column name" ou
-- "Duplicate check constraint name" apparaît (objet déjà présent).
--
-- N'efface aucune ligne de hourly_logs (CREATE TABLE IF NOT EXISTS).
-- ====================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Colonnes joueur : hourly_last_at, hourly_combo_bonus, hourly_streak.
-- Un seul ALTER pour que l'ajout soit atomique sur une base en service.
ALTER TABLE players
    ADD COLUMN hourly_last_at DATETIME(6) NULL DEFAULT NULL,
    ADD COLUMN hourly_combo_bonus DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    ADD COLUMN hourly_streak INT UNSIGNED NOT NULL DEFAULT 0;

-- CHECK (hourly_combo_bonus >= 0), CHECK (hourly_streak >= 0).
-- MySQL 8.0.16+ les applique ; les versions 8.0 antérieures les analysent
-- sans les faire respecter. Pas d'ajout idempotent : une seconde exécution
-- échoue avec "Duplicate check constraint name".
ALTER TABLE players
    ADD CONSTRAINT chk_players_hourly_combo_bonus CHECK (hourly_combo_bonus >= 0),
    ADD CONSTRAINT chk_players_hourly_streak CHECK (hourly_streak >= 0);

-- Journaux d'exécution /hourly (surveillance, audit et anti-triche).
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
