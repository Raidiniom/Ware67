# Partner API Keys: Team Notes

Internal notes for the WARE67 team. Partner-facing usage is in
[README.md, section 9](README.md#9-partner-api-keys).

## Database setup

New database: `backend/schema/ware67_schema.sql` already creates `api_keys`.
Do not rerun it on a populated database; it drops and recreates tables.

Existing database without the table, apply once:

```bash
mysql -h 127.0.0.1 -P 3307 -u YOUR_DB_USER -p YOUR_DB_NAME < backend/schema/add_api_keys.sql
```

### Upgrading from HMAC keys (one-time)

> **Skip this if you deploy the company model with a fresh database**
> (Company_Model_Plan.md, "Deploying PR A"): rebuilding from
> `ware67_schema.sql` deletes all old keys anyway.

Keys used to be hashed with HMAC-SHA256 keyed by `JWT_SECRET_KEY`. They are now
plain SHA-256. Raw keys are never stored, so old hashes can't be converted and
**every key issued before this change stops working**. Mark them revoked and
reissue keys to partners.

> **Run this only once, when the SHA-256 code is deployed to production.**
> Everyone's local backend shares the same DCISM database, so running it while
> testing locally revokes the keys production is still using.

```bash
mysql -h 127.0.0.1 -P 3307 -u YOUR_DB_USER -p YOUR_DB_NAME < backend/schema/api_keys_sha256_migration.sql
```

## Deploying the SHA-256 / hardening change

Follow README section 5 (Git & Deploy Workflow), with these extras. Pick a
quiet moment: partner keys stop working from step 3 until they're reissued.

1. On the server, pull `develop` and run `pip install -r requirements.txt`.
2. **No `alembic upgrade`**: this change adds no columns or tables.
3. Restart and check the logs:
   ```bash
   pm2 restart ware67-api
   pm2 logs ware67-api --lines 30 --nostream
   ```
4. Right after, run the one-time migration (credentials are in the server's
   `backend/.env`):
   ```bash
   mysql -u DB_USER -p DB_NAME < schema/api_keys_sha256_migration.sql
   ```
5. Sanity check on the live API docs page: create a key, call
   `GET /integration/products` with it (expect 200), and check `/audit-logs`
   shows one `REVOKE` row with `reason: "hash migration"` per old key.
6. Check the client IP (see "Client IPs behind a proxy" below): call any
   endpoint from your machine and look at the newest audit row's `ip_address`.
   Your public IP means it works; the same internal IP for everyone means
   `TRUSTED_PROXIES` needs setting in the server's `backend/.env`, then
   `pm2 restart ware67-api` again.
7. Reissue keys to anyone who had one (e.g. the "Next.js demo" app).
8. Tell the team to run `pip install -r requirements.txt` locally (new
   `httpx2` test dependency).

## How a key works

Format: `ware67_<12 hex chars>_<43 url-safe chars>`

- `ware67_<12 hex>` is the **public prefix** (`key_prefix`). It's stored in
  plain text, used to find the row, and safe to show in the UI and logs.
- The last part is 256 random bits. Only `sha256(full key)` is stored.

SHA-256 without a server secret is deliberate: the secret part is long and
random, so it can't be brute forced, and rotating `JWT_SECRET_KEY` no longer
breaks every partner integration.

On each request (`get_current_api_key` in `backend/app/api/deps.py`):

1. Find the row by prefix, compare hashes in constant time.
2. Only after the hash matches: reject unless the key is `ACTIVE`, its company
   is active and it hasn't expired. This way someone guessing keys learns
   nothing about which keys exist or their state.
3. Apply the per-key rate limit.
4. Update `last_used_at` at most once every 5 minutes.
5. Each route then checks its scope (`require_api_key_scope`).

## Time limits

| Limit | Default | Setting |
| ----- | ------- | ------- |
| Key lifetime, counted from reveal | 90 days | `API_KEY_MAX_TTL_DAYS` |
| Time to reveal an approved key | 7 days | `API_KEY_REVEAL_WINDOW_DAYS` |
| Open requests (pending or approved) per company | 5 | `API_KEY_MAX_OPEN_REQUESTS` |

- Times are stored as naive UTC, like every other timestamp in the database.
- `LAPSED` and `EXPIRED` happen with time, not with a write: the API works them
  out when showing a key (`effective_status` in `app/services/api_keys.py`).
  `LAPSED` is also saved when someone tries to reveal a lapsed approval.
  `EXPIRED` is never stored; it's an `ACTIVE` key past `expires_at`.

## Rate limiting

| Limit | Default | Setting |
| ----- | ------- | ------- |
| Requests per key per minute | 120 | `API_KEY_RATE_LIMIT_PER_MINUTE` |
| Failed attempts per IP per minute | 20 | `API_KEY_FAILED_ATTEMPTS_PER_MINUTE` |

- Only *failures* count toward the IP limit, so someone spamming bad keys can't
  lock out a partner sending a valid key from the same network.
- Counts are kept in each server process's memory (`app/services/rate_limit.py`).
  With several uvicorn workers each has its own counts, and a restart resets
  them. That's fine for stopping a runaway script. An exact global limit would
  need a shared store such as Redis.

## Audit log

| Action | When | Details |
| ------ | ---- | ------- |
| `REQUEST` on `API_KEY` | company asks for a key | name, requested scopes |
| `APPROVE` / `REJECT` on `API_KEY` | platform team reviews | granted scopes, or the reason |
| `REVEAL` on `API_KEY` | company reveals the key | name, prefix, scopes, expiry (never the key) |
| `LAPSE` on `API_KEY` | a reveal is tried after the window closed | name |
| `REVOKE` on `API_KEY` | company or platform team revokes or withdraws | name, prefix, previous status |
| `REVOKE` on `API_KEY`, no user | `api_keys_sha256_migration.sql` | name, prefix, `reason: "hash migration"` |
| `API_KEY_AUTH_FAILED` | bad, unknown, revoked or expired key | `reason`, `key_prefix` (never the key itself) |
| product/transaction actions | partner writes | `api_key_id`, `api_key_name`; `user_id` is empty and the row belongs to the key's company. Partner stock transactions store `api_key_id` instead of a user. |

Requests with no key at all are counted for rate limiting but not audited, since
they're mostly crawlers. Failures past the per-IP limit return 429 and are not
audited, so the audit table can't be flooded.

## Client IPs behind a proxy

`X-Forwarded-For` is set by whoever sends the request, so it's ignored unless
the request comes directly from a proxy listed in `TRUSTED_PROXIES`
(comma-separated IPs in `backend/.env`).

- **Default (empty):** the audit log records the direct connection's IP. If
  production runs behind a reverse proxy (nginx, a load balancer, cPanel's
  Apache), that will be the proxy's IP for every request. The rate limits still
  work per key; the per-IP failure limit would then be shared by everyone.
- **To fix that:** find the proxy's IP (it's what the audit log shows as the IP
  for every request) and set `TRUSTED_PROXIES=<that IP>`.

Production runs uvicorn under PM2 behind DCISM's web server. Uvicorn itself
already trusts `X-Forwarded-For` from `127.0.0.1` by default, so if DCISM's
proxy runs on the same machine the real client IP may already come through
with `TRUSTED_PROXIES` left empty. Confirm with step 6 of the deploy checklist.

## Running the tests

```bash
cd backend
python -m unittest discover -s tests
```

The API tests use FastAPI's `TestClient`, which with starlette 1.x needs the
`httpx2` package (listed in `requirements.txt`). Key auth and the
request/approve/reveal flow are covered in `tests/test_api_key_auth.py`;
keeping keys inside their company is covered in `tests/test_company_isolation.py`.

## Who does what

| | Company `OWNER` / `ADMIN` | Platform team |
| --- | --- | --- |
| Request a key | ✅ `POST /company/api-keys` | ❌ |
| Approve or reject | ❌ | ✅ `/platform/api-keys/{id}/approve`, `/reject` |
| Reveal (see the key) | ✅ once, `POST /company/api-keys/{id}/reveal` | ❌ never |
| See key metadata | own company only | all companies |
| Revoke | own company's keys | any key |
| Keys expiring soon | | ✅ `GET /platform/api-keys/expiring?days=14` |

In the app: companies use the **API Keys** page (`/api-keys`); the platform
team uses the **Platform Console** (`/platform`), which has the review queue,
all keys, keys expiring soon, and companies.

Other company roles (manager, staff, guest) can't touch keys at all. The
platform team is accounts with `is_platform_admin`, created with
`backend/scripts/create_platform_admin.py`.

Every key belongs to one company (`company_id`) and can only read and change
that company's data. Deactivating the company stops its keys immediately
(failed attempts are audited with `reason: "company_inactive"`).

### The flow

```
PENDING --approve--> APPROVED --reveal--> ACTIVE --(90 days)--> EXPIRED
   |                    |                   |
   +--reject--> REJECTED +--(7 days)--> LAPSED
   |                    |                   |
   +-------------------revoke/withdraw------+--> REVOKED
```

1. **Request:** a company asks for a key (name, scopes, optional purpose).
   Status `PENDING`; no key exists yet.
2. **Approve / reject:** the platform team approves (optionally with fewer
   scopes, never more) or rejects with a reason the company can see.
   Still no key.
3. **Reveal:** the company reveals it once. Only then is the key generated,
   hashed and returned. The row is locked while this happens, so a double
   click can't produce two keys. The platform team never sees the raw key.
4. **Renew:** the company requests a new key before expiry; the old one keeps
   working until it expires so they can switch over without downtime.

## Known gaps (planned)

- Nobody is notified automatically: the platform team checks the pending queue
  and the expiring list themselves.
- There's no rotate endpoint; request a new key, switch over, revoke the old one.
