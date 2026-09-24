-- ====================================================================
-- Migration: Système de Combo Saver pour la récompense horaire (/hourly)
-- ====================================================================

ALTER TABLE players ADD COLUMN combo_saver_credits INT UNSIGNED NOT NULL DEFAULT 0;
ALTER TABLE players ADD COLUMN hourly_lost_streak INT UNSIGNED NOT NULL DEFAULT 0;
ALTER TABLE players ADD COLUMN hourly_lost_bonus DECIMAL(10, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE players ADD CONSTRAINT chk_combo_saver_credits CHECK (combo_saver_credits >= 0);

