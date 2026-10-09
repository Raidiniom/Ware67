# Phase 2: Company Model Plan

Turns WARE67 from one shared inventory into a multi-company platform, where each
company only ever sees its own data and API keys are issued by the platform team.

## Decisions (agreed 2026-10-09)

| Question | Decision |
| -------- | -------- |
| Accounts per company | One company per account (`users.company_id`) |
| Categories/suppliers/locations | Per company, like everything else |
| Sign-up | Registering creates a company and makes you its `OWNER`; owners/admins add teammates from the Users page |
| Who issues/approves API keys | Platform team only |
| Who requests and reveals keys | Company `OWNER` and `ADMIN` |
| Who revokes keys | Platform team, and the company itself (`OWNER`/`ADMIN`) |
| Key handover | Request → platform approves → company reveals once; platform team never sees the raw key |
| Platform team and inventory data | **No access.** Platform team manages companies and keys only |

## Roles

**Platform level:** `users.is_platform_admin = TRUE`, `company_id = NULL`.
Can manage companies and API keys. Gets 403 on every inventory route.

**Company level:** existing roles plus `OWNER`:

| Role | Inventory | Users | API keys |
| ---- | --------- | ----- | -------- |
| `OWNER` | full | everyone, including other owners | request, reveal, revoke, view |
| `ADMIN` | full | everyone except owners | request, reveal, revoke, view |
| `MANAGER` | full | staff and guests | none |
| `STAFF` | record transactions | none | none |
| `GUEST` | read only | none | none |

A company must always keep at least one active `OWNER`.

## How isolation is enforced

- `company_id` (NOT NULL) on `categories`, `suppliers`, `locations`, `products`,
  `transactions`, `inventory_adjustments`, `api_keys`. Nullable on `audit_logs`
  (platform events have no company).
- One dependency, `get_current_member`, resolves the user and their company and
  rejects platform admins, users with no company, and inactive companies. Every
  inventory route uses it instead of `get_current_user`.
- Every query filters by the caller's `company_id`, including:
  - lookups by id, which return **404 for another company's row** (not 403, so
    ids don't reveal that a row exists);
  - reference checks: a product can't point at another company's category,
    supplier or location;
  - `apply_stock_change`, lists, counts, and the product counts on categories etc.
- Uniqueness becomes per company: SKU unique per `(company_id, sku)`; category
  names unique per company.
- Partner API keys carry `company_id`; `/integration` routes are scoped to it, and
  a key stops working the moment its company is deactivated.
- Partner writes are logged under the company and key, not under whoever issued
  the key: `transactions.user_id` becomes nullable with a new `api_key_id`
  column, and the ledger shows "via API key <name>".
- Audit logs: company owners/admins see their company's rows; platform admins
  see platform rows (companies, key approvals) only.
- The global `roles` descriptions become platform-only to edit (today any ADMIN
  could edit text every company sees).

## Pull requests

### PR A: Companies and data isolation (backend + small frontend)

Status: built on `feat/company-model`. Deploy steps are under "Deploying PR A"
below.

1. `companies` table; `users.company_id`, `users.is_platform_admin`; `OWNER` role.
2. `company_id` on all business tables, per-company uniqueness.
3. `get_current_member`, `require_company_roles`, `require_platform_admin`.
4. Scope every endpoint in `products`, `categories`, `suppliers`, `locations`,
   `transactions`, `adjustments`, `audit_logs`, `management`, `auth`, `integration`.
5. Register takes a company name and creates company + `OWNER`.
6. Platform endpoints: list companies, activate/deactivate a company.
7. Interim key issuing: platform team creates a key for a given `company_id`
   (replaced by the request/approve/reveal flow in PR B).
8. Script to make an existing account a platform admin.
9. Frontend: company name on the register page, `OWNER` in role lists.
10. **Cross-company test suite:** for every endpoint, a user and an API key from
    company B try to list, read, update, delete and reference company A's data,
    expecting 404 or empty results. Platform admins get 403 on inventory routes.

### PR B: API key request → approve → reveal

Status: built on `feat/api-key-requests`.

1. `api_keys` gains `status` (`PENDING`, `APPROVED`, `REJECTED`, `ACTIVE`,
   `REVOKED`, `LAPSED`), requested/approved/revealed by and at, rejection
   reason. Hash and prefix stay empty until reveal.
2. Company routes (`OWNER`/`ADMIN`): request a key, list own keys (metadata
   only), reveal once, revoke.
3. Platform routes: pending queue, approve (optionally with fewer scopes),
   reject with reason, revoke, keys expiring in the next 14 days.
4. Reveal generates the key inside a row lock, so a double click can't reveal
   twice; the 90 days start at reveal; approvals not revealed within 7 days lapse.
5. The direct `POST /api-keys` from PR A is removed.

### PR C (Phase 3): Frontend pages

Platform console (companies, key request queue, expiring keys) and the company
API keys page (request, reveal-once dialog, revoke).

## Existing data

Decided 2026-10-09, with the team's agreement: **start fresh**. The current
data is not kept; on deploy day the shared database is rebuilt empty from
`schema/ware67_schema.sql`, and everyone signs up again.

## Deploying PR A

Follow README section 5 (Git & Deploy Workflow), with these extras. The app
is down from step 3 until step 4 finishes, so pick a quiet moment and tell the
team first.

1. **Back up the database anyway** (cheap insurance if a step fails):
   `mysqldump -u DB_USER -p DB_NAME > ware67_before_company_model.sql`
2. On the server, pull `develop`. No `pip install` or `alembic upgrade` needed.
3. Rebuild the database (from `backend/`). **This deletes every table and all
   data:**
   `mysql -u DB_USER -p DB_NAME < schema/ware67_schema.sql`
4. `pm2 restart ware67-api`, then check `pm2 logs ware67-api --lines 30 --nostream`.
   Deploy the frontend build at the same time: the old register page doesn't
   send a company name, so sign-ups fail until it's updated.
5. Create the platform team accounts, one per person, each with a real password
   (not the one used for local testing):
   `python scripts/create_platform_admin.py --email platform_dev1@ware67.com --name "..."`
6. Check: sign in as a platform admin and get the "platform team" dashboard;
   sign up a company and confirm it starts empty; sign up a second one and
   confirm neither sees the other's products.
7. Tell the team to pull `develop`: older branches no longer match the database.

## ⚠️ Risks

- **Shared database.** Don't rebuild the shared DCISM database before deploy
  day: production and teammates' local backends run the old code and use it.
  Develop against a local SQLite file instead (Local_Development_Setup.md,
  "Working on the company model").
- **One missed filter leaks data.** That's why scoping goes through one
  dependency and why the cross-company suite covers every endpoint, including
  ones added later.
- **Breaking API change for partners.** All existing keys are deleted with the
  fresh start; partners get new keys afterwards.
