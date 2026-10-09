-- =====================================================================
-- Company model migration (Phase 2, PR A)
--
-- Moves the single shared inventory into the first company, "ware67-inc",
-- adds the companies table, OWNER role, platform admins and company_id on
-- every company-owned table.
--
-- RUN ONCE, WHEN THIS CODE IS DEPLOYED. The database is shared by every
-- local backend and production; old code can't insert rows once company_id
-- is required, so running it early breaks everyone still on the old code.
--
-- MySQL/MariaDB commit each ALTER TABLE immediately, so this script can't be
-- rolled back as a whole. Take a backup first:
--   mysqldump -u DB_USER -p DB_NAME > ware67_before_company_model.sql
--
-- Afterwards, create the platform team's accounts with
--   python scripts/create_platform_admin.py --email ... --name ...
-- =====================================================================

SET @company_id = UUID();

-- ---------------------------------------------------------------------
-- COMPANIES
-- Explicit charset/collation on every company_id column (here and below)
-- so the foreign keys match regardless of each table's default collation.
-- ---------------------------------------------------------------------
CREATE TABLE companies (
    id          CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    name        VARCHAR(150) NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO companies (id, name) VALUES (@company_id, 'ware67-inc');

-- ---------------------------------------------------------------------
-- USERS: OWNER role, company membership, platform admin flag.
-- Everyone joins ware67-inc; today's ADMINs become its OWNERs.
-- ---------------------------------------------------------------------
ALTER TABLE users
    MODIFY role ENUM('GUEST', 'STAFF', 'MANAGER', 'ADMIN', 'OWNER') NOT NULL DEFAULT 'GUEST',
    ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER role_id,
    ADD COLUMN is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE AFTER company_id;

UPDATE users SET company_id = @company_id;
UPDATE users SET role = 'OWNER' WHERE role = 'ADMIN';

ALTER TABLE users
    ADD KEY idx_users_company_id (company_id),
    ADD CONSTRAINT fk_users_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- ---------------------------------------------------------------------
-- company_id on every company-owned table: add nullable, fill, then
-- require it.
-- ---------------------------------------------------------------------
ALTER TABLE categories ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER id;
UPDATE categories SET company_id = @company_id;
ALTER TABLE categories
    MODIFY company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    ADD KEY idx_categories_company_id (company_id),
    ADD CONSTRAINT fk_categories_company FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE suppliers ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER id;
UPDATE suppliers SET company_id = @company_id;
ALTER TABLE suppliers
    MODIFY company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    ADD KEY idx_suppliers_company_id (company_id),
    ADD CONSTRAINT fk_suppliers_company FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE locations ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER id;
UPDATE locations SET company_id = @company_id;
ALTER TABLE locations
    MODIFY company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    ADD KEY idx_locations_company_id (company_id),
    ADD CONSTRAINT fk_locations_company FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE products ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER id;
UPDATE products SET company_id = @company_id;
ALTER TABLE products
    MODIFY company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    ADD KEY idx_products_company_id (company_id),
    ADD CONSTRAINT fk_products_company FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- SKUs become unique per company. The old single-column unique index may be
-- named differently depending on how the table was created, so look it up.
SET @sku_index = (
    SELECT INDEX_NAME FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'products'
      AND COLUMN_NAME = 'sku' AND NON_UNIQUE = 0 AND SEQ_IN_INDEX = 1
    LIMIT 1
);
SET @drop_sku = IF(@sku_index IS NULL, 'DO 0', CONCAT('ALTER TABLE products DROP INDEX `', @sku_index, '`'));
PREPARE drop_sku FROM @drop_sku;
EXECUTE drop_sku;
DEALLOCATE PREPARE drop_sku;
ALTER TABLE products ADD UNIQUE KEY uq_products_company_sku (company_id, sku);

ALTER TABLE inventory_adjustments ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER id;
UPDATE inventory_adjustments SET company_id = @company_id;
ALTER TABLE inventory_adjustments
    MODIFY company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    ADD KEY idx_inv_adj_company_id (company_id),
    ADD CONSTRAINT fk_inv_adj_company FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE api_keys ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER id;
UPDATE api_keys SET company_id = @company_id;
ALTER TABLE api_keys
    MODIFY company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    ADD KEY idx_api_keys_company_id (company_id),
    ADD CONSTRAINT fk_api_keys_company FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- ---------------------------------------------------------------------
-- TRANSACTIONS: company_id, and partner-made rows record the API key
-- instead of a user.
-- ---------------------------------------------------------------------
ALTER TABLE transactions ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER id;
UPDATE transactions SET company_id = @company_id;
ALTER TABLE transactions
    MODIFY company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
    -- Same collation as users.id / api_keys.id, which their FKs require.
    MODIFY user_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL,
    ADD COLUMN api_key_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER user_id,
    ADD KEY idx_transactions_company_id (company_id),
    ADD KEY idx_transactions_api_key_id (api_key_id),
    ADD CONSTRAINT fk_transactions_company FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    ADD CONSTRAINT fk_transactions_api_key FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- ---------------------------------------------------------------------
-- AUDIT_LOGS: nullable company_id (platform events have none). Every
-- existing row was activity inside the one company.
-- ---------------------------------------------------------------------
ALTER TABLE audit_logs ADD COLUMN company_id CHAR(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL AFTER id;
UPDATE audit_logs SET company_id = @company_id;
ALTER TABLE audit_logs
    ADD KEY idx_audit_logs_company_id (company_id),
    ADD CONSTRAINT fk_audit_logs_company FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- Quick check: every count below should be 0.
SELECT
    (SELECT COUNT(*) FROM users WHERE company_id IS NULL AND is_platform_admin = FALSE) AS users_without_company,
    (SELECT COUNT(*) FROM products WHERE company_id IS NULL) AS products_without_company,
    (SELECT COUNT(*) FROM transactions WHERE company_id IS NULL) AS transactions_without_company;
