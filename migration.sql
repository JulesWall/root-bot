-- ====================================================================
-- Migration: Système de Combo Saver pour la récompense horaire (/hourly)
-- ====================================================================

ALTER TABLE players ADD COLUMN combo_saver_credits INT UNSIGNED NOT NULL DEFAULT 0;
ALTER TABLE players ADD COLUMN hourly_lost_streak INT UNSIGNED NOT NULL DEFAULT 0;
ALTER TABLE players ADD COLUMN hourly_lost_bonus DECIMAL(10, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE players ADD CONSTRAINT chk_combo_saver_credits CHECK (combo_saver_credits >= 0);

-- Compensation / Déploiement Hotfix N°4 :
-- 1. Décale le dernier claim horaire de 7 minutes pour accorder 7 min de délai supplémentaire à tous les joueurs
UPDATE players SET hourly_last_at = DATE_ADD(hourly_last_at, INTERVAL 7 MINUTE) WHERE hourly_last_at IS NOT NULL;

-- 2. Offre 1 crédit Combo Saver à l'ensemble des joueurs
UPDATE players SET combo_saver_credits = combo_saver_credits + 1;


