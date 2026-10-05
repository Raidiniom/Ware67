-- Add API-key authentication without recreating the existing WARE67 database.
CREATE TABLE IF NOT EXISTS api_keys (
    id           CHAR(36)     NOT NULL,
    name         VARCHAR(150) NOT NULL,
    key_prefix   VARCHAR(32)  NOT NULL,
    key_hash     CHAR(64)     NOT NULL,
    scopes       JSON         NOT NULL,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by   CHAR(36)     NOT NULL,
    expires_at   DATETIME     NULL,
    last_used_at DATETIME     NULL,
    revoked_at   DATETIME     NULL,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_api_keys_prefix (key_prefix),
    UNIQUE KEY uq_api_keys_hash (key_hash),
    KEY idx_api_keys_created_by (created_by),
    CONSTRAINT fk_api_keys_created_by
        FOREIGN KEY (created_by) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
