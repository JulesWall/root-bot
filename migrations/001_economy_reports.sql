-- ============================================================
-- Migration 001 : Suivi économique (economy_hourly + economy_reports)
-- À appliquer UNE SEULE FOIS sur une base existante.
-- Ne pas réimporter root.sql pour une mise à jour.
-- ============================================================

CREATE TABLE IF NOT EXISTS economy_hourly (
    bucket_start        DATETIME NOT NULL,
    player_id           BIGINT UNSIGNED NOT NULL,
    new_players         BIGINT UNSIGNED NOT NULL DEFAULT 0,
    returning_players   BIGINT UNSIGNED NOT NULL DEFAULT 0,
    claims              BIGINT UNSIGNED NOT NULL DEFAULT 0,
    full_claims         BIGINT UNSIGNED NOT NULL DEFAULT 0,
    mining_rtm          DECIMAL(38,5) NOT NULL DEFAULT 0,
    event_hash_usd      DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_pin_usd       DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_decode_usd    DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_anomaly_usd   DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_buffer_usd    DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_signal_usd    DECIMAL(38,2) NOT NULL DEFAULT 0,
    event_packet_usd    DECIMAL(38,2) NOT NULL DEFAULT 0,
    grant_usd           DECIMAL(38,2) NOT NULL DEFAULT 0,
    miners_usd          DECIMAL(38,2) NOT NULL DEFAULT 0,
    miners_rtm          DECIMAL(38,5) NOT NULL DEFAULT 0,
    combat_usd          DECIMAL(38,2) NOT NULL DEFAULT 0,
    combat_rtm          DECIMAL(38,5) NOT NULL DEFAULT 0,
    upgrades_usd        DECIMAL(38,2) NOT NULL DEFAULT 0,
    compile_rtm         DECIMAL(38,5) NOT NULL DEFAULT 0,
    scan_rtm            DECIMAL(38,5) NOT NULL DEFAULT 0,
    miners_t1           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    miners_t2           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    miners_t3           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    miners_t4           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    miners_t5           BIGINT UNSIGNED NOT NULL DEFAULT 0,
    attack_bought       BIGINT UNSIGNED NOT NULL DEFAULT 0,
    defense_bought      BIGINT UNSIGNED NOT NULL DEFAULT 0,
    upgrades_started    BIGINT UNSIGNED NOT NULL DEFAULT 0,
    conversions         BIGINT UNSIGNED NOT NULL DEFAULT 0,
    converted_rtm       DECIMAL(38,5) NOT NULL DEFAULT 0,
    converted_usd       DECIMAL(38,2) NOT NULL DEFAULT 0,
    trades              BIGINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket_start, player_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS economy_reports (
    period_hours        SMALLINT UNSIGNED NOT NULL,
    tracking_start      DATETIME NOT NULL,
    next_start          DATETIME NOT NULL,
    pending_end         DATETIME NULL,
    pending_payload     JSON NULL,
    pending_channel_id  BIGINT UNSIGNED NULL,
    last_message_id     BIGINT UNSIGNED NULL,
    last_sent_at        DATETIME(6) NULL,
    PRIMARY KEY (period_hours)
) ENGINE=InnoDB;

