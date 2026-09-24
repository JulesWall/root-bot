UPDATE players
SET hourly_last_at = DATE_ADD(hourly_last_at, INTERVAL 20 MINUTE)
WHERE hourly_last_at IS NOT NULL;

