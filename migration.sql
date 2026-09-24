-- Migration : Fenêtre de grâce pour fidélité des contrats (/contract)
ALTER TABLE players
    ADD COLUMN contract_grace_until DATETIME(6) NULL DEFAULT NULL AFTER contracts_completed;

-- Migration : Table des préfixes personnalisés par utilisateur en MP (/prefix)
CREATE TABLE IF NOT EXISTS user_prefixes (
    user_id    BIGINT UNSIGNED NOT NULL,
    prefix     VARCHAR(32)     NOT NULL,
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

