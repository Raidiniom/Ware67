-- =====================================================================
-- WARE67 - DATABASE STRUCTURE
-- MySQL schema generation script (fresh install; drops existing tables).
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Drop tables in reverse dependency order (safe re-run)
DROP TABLE IF EXISTS inventory_adjustments;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS api_keys;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS locations;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS companies;

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================================
-- COMPANIES
-- Every business row belongs to exactly one company; companies never see
-- each other's data. Deactivating a company locks out its members and keys.
-- =====================================================================
CREATE TABLE companies (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    name        VARCHAR(150)  NOT NULL,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- ROLES
-- =====================================================================
CREATE TABLE roles (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    name        VARCHAR(100)  NOT NULL,
    description TEXT          NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_roles_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- USERS
-- Note: diagram shows a `role` enum column on USERS AND a separate
-- M:1 relationship to ROLES. Both are implemented below: the enum
-- is kept for quick checks, and role_id is the real FK driving the
-- USERS -> ROLES relationship shown in the diagram.
-- company_id is NULL only for platform admins (the WARE67 team).
-- =====================================================================
CREATE TABLE users (
    id                CHAR(36)      NOT NULL DEFAULT (UUID()),
    name              VARCHAR(150)  NOT NULL,
    email             VARCHAR(150)  NOT NULL,
    password          VARCHAR(255)  NOT NULL,
    role              ENUM('GUEST', 'STAFF', 'MANAGER', 'ADMIN', 'OWNER') NOT NULL DEFAULT 'GUEST',
    role_id           CHAR(36)      NULL,
    company_id        CHAR(36)      NULL,
    is_platform_admin BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active         BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_role_id (role_id),
    KEY idx_users_company_id (company_id),
    CONSTRAINT fk_users_role
        FOREIGN KEY (role_id) REFERENCES roles (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_users_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- AUDIT_LOGS
-- company_id is NULL for platform-level events.
-- =====================================================================
CREATE TABLE audit_logs (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    company_id  CHAR(36)      NULL,
    user_id     CHAR(36)      NULL,
    action      VARCHAR(100)  NOT NULL,
    entity      VARCHAR(100)  NOT NULL,
    entity_id   CHAR(36)      NULL,
    details     JSON          NULL,
    ip_address  VARCHAR(45)   NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_audit_logs_company_id (company_id),
    KEY idx_audit_logs_user_id (user_id),
    KEY idx_audit_logs_entity (entity, entity_id),
    CONSTRAINT fk_audit_logs_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_audit_logs_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- API_KEYS
-- A row starts as a company's request (PENDING). The platform team approves
-- (APPROVED) or rejects it; the company then reveals it once (ACTIVE). Only
-- at reveal are key_prefix and key_hash set: the raw key is shown once and
-- never stored; key_hash is a SHA-256 digest. Each key reads and changes
-- only its company's data.
-- =====================================================================
CREATE TABLE api_keys (
    id               CHAR(36)     NOT NULL DEFAULT (UUID()),
    company_id       CHAR(36)     NOT NULL,
    name             VARCHAR(150) NOT NULL,
    purpose          TEXT         NULL,
    status           ENUM('PENDING', 'APPROVED', 'REJECTED', 'ACTIVE', 'REVOKED', 'LAPSED')
                                  NOT NULL DEFAULT 'PENDING',
    requested_scopes JSON         NOT NULL,
    scopes           JSON         NULL COMMENT 'granted at approval',
    key_prefix       VARCHAR(32)  NULL,
    key_hash         CHAR(64)     NULL,
    requested_by     CHAR(36)     NOT NULL,
    reviewed_by      CHAR(36)     NULL,
    reviewed_at      DATETIME     NULL,
    rejection_reason TEXT         NULL,
    reveal_deadline  DATETIME     NULL,
    revealed_by      CHAR(36)     NULL,
    revealed_at      DATETIME     NULL,
    expires_at       DATETIME     NULL,
    last_used_at     DATETIME     NULL,
    revoked_by       CHAR(36)     NULL,
    revoked_at       DATETIME     NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_api_keys_prefix (key_prefix),
    UNIQUE KEY uq_api_keys_hash (key_hash),
    KEY idx_api_keys_company_id (company_id),
    KEY idx_api_keys_status (status),
    CONSTRAINT fk_api_keys_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_api_keys_requested_by
        FOREIGN KEY (requested_by) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_api_keys_reviewed_by
        FOREIGN KEY (reviewed_by) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_api_keys_revealed_by
        FOREIGN KEY (revealed_by) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_api_keys_revoked_by
        FOREIGN KEY (revoked_by) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- CATEGORIES
-- =====================================================================
CREATE TABLE categories (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    company_id  CHAR(36)      NOT NULL,
    name        VARCHAR(150)  NOT NULL,
    description TEXT          NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_categories_company_id (company_id),
    CONSTRAINT fk_categories_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- SUPPLIERS
-- =====================================================================
CREATE TABLE suppliers (
    id              CHAR(36)      NOT NULL DEFAULT (UUID()),
    company_id      CHAR(36)      NOT NULL,
    name            VARCHAR(150)  NOT NULL,
    contact_person  VARCHAR(150)  NULL,
    contact_number  VARCHAR(50)   NULL,
    email           VARCHAR(150)  NULL,
    address         TEXT          NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_suppliers_company_id (company_id),
    CONSTRAINT fk_suppliers_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- LOCATIONS
-- =====================================================================
CREATE TABLE locations (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    company_id  CHAR(36)      NOT NULL,
    name        VARCHAR(150)  NOT NULL,
    description TEXT          NULL,
    warehouse   VARCHAR(100)  NULL,
    aisle       VARCHAR(50)   NULL,
    shelf       VARCHAR(50)   NULL,
    bin         VARCHAR(50)   NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_locations_company_id (company_id),
    CONSTRAINT fk_locations_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- PRODUCTS
-- SKUs are unique per company, not globally.
-- =====================================================================
CREATE TABLE products (
    id              CHAR(36)      NOT NULL DEFAULT (UUID()),
    company_id      CHAR(36)      NOT NULL,
    sku             VARCHAR(100)  NOT NULL,
    name            VARCHAR(200)  NOT NULL,
    description     TEXT          NULL,
    category_id     CHAR(36)      NULL,
    supplier_id     CHAR(36)      NULL,
    location_id     CHAR(36)      NULL,
    unit            VARCHAR(50)   NULL,
    price           DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    reorder_level   INT           NOT NULL DEFAULT 0,
    current_stock   INT           NOT NULL DEFAULT 0,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_products_company_sku (company_id, sku),
    KEY idx_products_category_id (category_id),
    KEY idx_products_supplier_id (supplier_id),
    KEY idx_products_location_id (location_id),
    CONSTRAINT fk_products_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_products_supplier
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_products_location
        FOREIGN KEY (location_id) REFERENCES locations (id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- TRANSACTIONS
-- type: STOCK_IN, STOCK_OUT
-- Made by a user (user_id) or a partner integration (api_key_id).
-- =====================================================================
CREATE TABLE transactions (
    id              CHAR(36)      NOT NULL DEFAULT (UUID()),
    company_id      CHAR(36)      NOT NULL,
    product_id      CHAR(36)      NOT NULL,
    user_id         CHAR(36)      NULL,
    api_key_id      CHAR(36)      NULL,
    type            ENUM('STOCK_IN', 'STOCK_OUT') NOT NULL,
    quantity        INT           NOT NULL,
    reference_type  VARCHAR(50)   NULL COMMENT 'e.g., PO, SO, MANUAL',
    reference_id    VARCHAR(100)  NULL,
    notes           TEXT          NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_transactions_company_id (company_id),
    KEY idx_transactions_product_id (product_id),
    KEY idx_transactions_user_id (user_id),
    KEY idx_transactions_api_key_id (api_key_id),
    CONSTRAINT fk_transactions_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_product
        FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_api_key
        FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =====================================================================
-- INVENTORY_ADJUSTMENTS
-- quantity_change: positive or negative
-- =====================================================================
CREATE TABLE inventory_adjustments (
    id              CHAR(36)      NOT NULL DEFAULT (UUID()),
    company_id      CHAR(36)      NOT NULL,
    product_id      CHAR(36)      NOT NULL,
    user_id         CHAR(36)      NOT NULL,
    quantity_change INT           NOT NULL COMMENT 'positive or negative',
    reason          VARCHAR(150)  NULL,
    notes           TEXT          NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_inv_adj_company_id (company_id),
    KEY idx_inv_adj_product_id (product_id),
    KEY idx_inv_adj_user_id (user_id),
    CONSTRAINT fk_inv_adj_company
        FOREIGN KEY (company_id) REFERENCES companies (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_inv_adj_product
        FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_inv_adj_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
