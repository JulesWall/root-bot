UPDATE players
SET hourly_last_at = DATE_ADD(hourly_last_at, INTERVAL 20 MINUTE)
WHERE hourly_last_at IS NOT NULL;

-- Ajout du champ manquant pour les statistiques de claims horaires (/hourly)
ALTER TABLE economy_hourly
    ADD COLUMN hourly_claims BIGINT UNSIGNED NOT NULL DEFAULT 0 AFTER upgrades_usd;


