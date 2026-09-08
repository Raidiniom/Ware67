-- =====================================================================
-- WARE67 - DATABASE STRUCTURE
-- MySQL schema generation script
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Drop tables in reverse dependency order (safe re-run)
DROP TABLE IF EXISTS inventory_adjustments;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS locations;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS roles;

SET FOREIGN_KEY_CHECKS = 1;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- USERS
-- Note: diagram shows a `role` enum column on USERS AND a separate
-- M:1 relationship to ROLES. Both are implemented below: the enum
-- is kept for quick checks, and role_id is the real FK driving the
-- USERS -> ROLES relationship shown in the diagram.
-- =====================================================================
CREATE TABLE users (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    name        VARCHAR(150)  NOT NULL,
    email       VARCHAR(150)  NOT NULL,
    password    VARCHAR(255)  NOT NULL,
    role        ENUM('ADMIN', 'MANAGER', 'STAFF') NOT NULL DEFAULT 'STAFF',
    role_id     CHAR(36)      NULL,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_role_id (role_id),
    CONSTRAINT fk_users_role
        FOREIGN KEY (role_id) REFERENCES roles (id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- AUDIT_LOGS
-- =====================================================================
CREATE TABLE audit_logs (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    user_id     CHAR(36)      NULL,
    action      VARCHAR(100)  NOT NULL,
    entity      VARCHAR(100)  NOT NULL,
    entity_id   CHAR(36)      NULL,
    details     JSON          NULL,
    ip_address  VARCHAR(45)   NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_audit_logs_user_id (user_id),
    KEY idx_audit_logs_entity (entity, entity_id),
    CONSTRAINT fk_audit_logs_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- CATEGORIES
-- =====================================================================
CREATE TABLE categories (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    name        VARCHAR(150)  NOT NULL,
    description TEXT          NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- SUPPLIERS
-- =====================================================================
CREATE TABLE suppliers (
    id              CHAR(36)      NOT NULL DEFAULT (UUID()),
    name            VARCHAR(150)  NOT NULL,
    contact_person  VARCHAR(150)  NULL,
    contact_number  VARCHAR(50)   NULL,
    email           VARCHAR(150)  NULL,
    address         TEXT          NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- LOCATIONS
-- =====================================================================
CREATE TABLE locations (
    id          CHAR(36)      NOT NULL DEFAULT (UUID()),
    name        VARCHAR(150)  NOT NULL,
    description TEXT          NULL,
    warehouse   VARCHAR(100)  NULL,
    aisle       VARCHAR(50)   NULL,
    shelf       VARCHAR(50)   NULL,
    bin         VARCHAR(50)   NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- PRODUCTS
-- =====================================================================
CREATE TABLE products (
    id              CHAR(36)      NOT NULL DEFAULT (UUID()),
    sku             VARCHAR(100)  NOT NULL,
    name            VARCHAR(200)  NOT NULL,
    description     TEXT          NULL,
    category_id     CHAR(36)      NULL,
    supplier_id     CHAR(36)      NULL,
    location_id     CHAR(36)      NULL,
    unit            VARCHAR(50)   NULL,
    price           DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    reorder_level   INT           NOT NULL DEFAULT 0,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_products_sku (sku),
    KEY idx_products_category_id (category_id),
    KEY idx_products_supplier_id (supplier_id),
    KEY idx_products_location_id (location_id),
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_products_supplier
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_products_location
        FOREIGN KEY (location_id) REFERENCES locations (id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- TRANSACTIONS
-- type: STOCK_IN, STOCK_OUT
-- =====================================================================
CREATE TABLE transactions (
    id              CHAR(36)      NOT NULL DEFAULT (UUID()),
    product_id      CHAR(36)      NOT NULL,
    user_id         CHAR(36)      NOT NULL,
    type            ENUM('STOCK_IN', 'STOCK_OUT') NOT NULL,
    quantity        INT           NOT NULL,
    reference_type  VARCHAR(50)   NULL COMMENT 'e.g., PO, SO, MANUAL',
    reference_id    VARCHAR(100)  NULL,
    notes           TEXT          NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_transactions_product_id (product_id),
    KEY idx_transactions_user_id (user_id),
    CONSTRAINT fk_transactions_product
        FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- INVENTORY_ADJUSTMENTS
-- quantity_change: positive or negative
-- =====================================================================
CREATE TABLE inventory_adjustments (
    id              CHAR(36)      NOT NULL DEFAULT (UUID()),
    product_id      CHAR(36)      NOT NULL,
    user_id         CHAR(36)      NOT NULL,
    quantity_change INT           NOT NULL COMMENT 'positive or negative',
    reason          VARCHAR(150)  NULL,
    notes           TEXT          NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_inv_adj_product_id (product_id),
    KEY idx_inv_adj_user_id (user_id),
    CONSTRAINT fk_inv_adj_product
        FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_inv_adj_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
