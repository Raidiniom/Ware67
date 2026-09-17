# Core CRUD endpoints: categories, suppliers, locations, products, transactions, inventory_adjustments

## What's new
- Models, schemas and endpoints for all six tables in `ware67_schema.sql` that had no API yet.
- `app/api/v1/api.py` — all six routers registered.
- `app/models/__init__.py`, `app/db/base.py` — updated for Alembic autogenerate (README §3.5).
- `tests/` — pytest suite, **39 tests**, run against an in-memory SQLite DB, no live MySQL or
  real JWTs needed.

## Routes
| Resource   | Routes | Who can write |
|---|---|---|
| Categories | `GET/POST /categories`, `GET/PUT/DELETE /categories/{id}` | ADMIN, MANAGER |
| Suppliers  | `GET/POST /suppliers`, `GET/PUT/DELETE /suppliers/{id}` | ADMIN, MANAGER |
| Locations  | `GET/POST /locations`, `GET/PUT/DELETE /locations/{id}` | ADMIN, MANAGER |
| Products   | `GET/POST /products`, `GET/PUT/DELETE /products/{id}` | ADMIN, MANAGER |
| Transactions | `GET /transactions` (filter: `?product_id=`), `POST /transactions`, `DELETE /transactions/{id}` | create: anyone logged in; delete: ADMIN only |
| Inventory adjustments | `GET /inventory-adjustments` (filter: `?product_id=`), `POST /inventory-adjustments`, `DELETE /inventory-adjustments/{id}` | create: ADMIN, MANAGER; delete: ADMIN only |

All list/get routes are open to any logged-in user.

## Design notes on transactions / inventory_adjustments
These two are treated as **append-only ledgers**, not plain CRUD, since that's what they
represent physically (a stock movement or a manual count correction that already happened):
- **No PUT/update route.** To fix a mistake, delete the bad entry (ADMIN only) and create a
  correct one — there's no "edit history" concept in the schema, so silently rewriting an
  entry would be more surprising than not allowing it.
- **`user_id` is always taken from the authenticated token**, never from the request body —
  tested explicitly in `test_user_id_cannot_be_spoofed_by_client`.
- **Transactions**: any logged-in role can create one (staff do physical stock in/out), but
  only ADMIN can delete.
- **Inventory adjustments**: only ADMIN/MANAGER can create (a manual override, more sensitive
  than a normal stock movement), and only ADMIN can delete.
- `quantity` on transactions must be `> 0` (direction comes from `type`); `quantity_change` on
  adjustments must be non-zero (sign carries direction there).
- Both validate `product_id` exists before writing (400 if not).

These are assumptions about who should be allowed to do what — easy to adjust by changing the
`require_roles(...)` calls in `app/api/v1/endpoints/transactions.py` and
`inventory_adjustments.py` if your actual workflow differs.

## Running the tests
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

`tests/conftest.py` gives you three role-based clients (`admin_client`, `manager_client`,
`staff_client`) for single-role tests, plus a `login_as(user)` context manager for tests that
need to act as more than one role against the same client in one test (e.g. "create as admin,
then confirm manager can't delete it"). Don't mix two of the `*_client` fixtures in one test —
they share one dependency-override dict, so whichever is resolved last silently wins for both.

## Still not done
- No pagination/filtering beyond `?product_id=` on the ledger endpoints.
- No endpoint yet computes "current stock on hand" from transactions + adjustments — right now
  they're just an audit trail, matching what's actually in the schema (no running-total column
  anywhere). Say if you want a computed stock-level endpoint and I'll add it.
