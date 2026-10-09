-- API keys switched from HMAC-SHA256 (keyed with JWT_SECRET_KEY) to plain
-- SHA-256, and new keys use a 12-character public prefix. Raw keys are never
-- stored, so existing hashes can't be converted: every key issued before this
-- change already fails to authenticate. Mark them revoked so the key list
-- tells the truth, then reissue keys to partners.
--
-- RUN ONCE, WHEN THE SHA-256 CODE IS DEPLOYED. The database is shared by every
-- local backend and production; running it earlier breaks production's keys.
--
-- Each revoked key gets a REVOKE audit row (user_id NULL, reason
-- "hash migration"), so the bulk revoke is visible in /audit-logs.

START TRANSACTION;

SET @revoked_at = UTC_TIMESTAMP();

INSERT INTO audit_logs (id, user_id, action, entity, entity_id, details)
SELECT UUID(), NULL, 'REVOKE', 'API_KEY', id,
       JSON_OBJECT('name', name, 'key_prefix', key_prefix, 'reason', 'hash migration')
FROM api_keys
WHERE is_active = TRUE;

UPDATE api_keys
SET is_active = FALSE,
    revoked_at = @revoked_at
WHERE is_active = TRUE;

COMMIT;
