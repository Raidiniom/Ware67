# Ware67 Backend — Team Guide

This is the reference doc for working on the FastAPI backend: how the project is structured, how to build a new API endpoint, how to test it, and how to get it live on the DCISM server.

---

## 1. Stack Overview

- **Backend:** Python, FastAPI, SQLAlchemy (ORM), Alembic (migrations), MySQL/MariaDB
- **Auth:** JWT access + refresh tokens (`python-jose`), passwords hashed with `bcrypt`
- **Frontend:** React + Vite, talks to the backend via `axios` (`frontend/src/api/client.js`)
- **Hosting:** DCISM server
  - Frontend → `https://ware67.dcism.org` (static site)
  - Backend API → `https://ware67-api.dcism.org` (Custom Application Hosting, run via PM2 + uvicorn)
- **Local dev DB access:** SSH tunnel to the server's MySQL (see §6)

---

## 2. Project Structure

```
backend/
├── alembic/              # DB migration scripts (auto-managed, don't hand-edit versions/)
├── app/
│   ├── api/
│   │   ├── deps.py               # shared dependencies (get_current_user, require_roles)
│   │   └── v1/
│   │       ├── api.py            # aggregates all routers — register new routers here
│   │       └── endpoints/        # one file per resource (auth.py, admin.py, products.py...)
│   ├── core/
│   │   ├── config.py             # Settings (reads .env)
│   │   └── security.py           # password hashing + JWT creation/decoding
│   ├── db/
│   │   ├── base_class.py         # defines Base (SQLAlchemy declarative base) — models import FROM HERE
│   │   ├── base.py               # imports all models for Alembic autogenerate — NOT imported by models
│   │   └── session.py            # engine + get_db() dependency
│   ├── models/                   # SQLAlchemy ORM models (one class per table)
│   │   └── __init__.py           # imports ALL models together — required, see §3.4
│   ├── schemas/                  # Pydantic request/response schemas
│   └── main.py                   # FastAPI app instance, CORS, router registration
├── .env                          # NEVER commit this (DB creds, JWT secret)
├── requirements.txt
└── alembic.ini
```

---

## 3. Adding a New API Endpoint

### 3.1 Naming & REST conventions

- Plural nouns for resources: `/products`, `/suppliers`, not `/product` or `/getProducts`
- Standard verbs via HTTP methods, not the URL:
  | Action | Method | Path |
  |---|---|---|
  | List | GET | `/products` |
  | Get one | GET | `/products/{id}` |
  | Create | POST | `/products` |
  | Update | PUT/PATCH | `/products/{id}` |
  | Delete | DELETE | `/products/{id}` |
- All routes live under `/api/v1/...` (already handled by the `api_router` prefix in `main.py`)

### 3.2 Response format

- Success: return the Pydantic model directly (FastAPI serializes it). No custom `{success: true, data: ...}` wrapper — keep it simple, let HTTP status codes carry meaning.
- Errors: raise `HTTPException(status_code=..., detail="human readable message")`. FastAPI returns `{"detail": "..."}` automatically — don't invent a different error shape.
- Use the right status code: `200` (OK), `201` (Created), `204` (No Content, e.g. after delete), `400` (bad input), `401` (not authenticated), `403` (authenticated but not allowed), `404` (not found), `422` (validation error — FastAPI does this automatically for bad request bodies).

### 3.3 Standard steps to add a resource (example: `products`)

1. **Model** — `app/models/product.py`, matching the existing MySQL table exactly (column names/types).
2. **Register it** in `app/models/__init__.py`:
   ```python
   from app.models.product import Product  # noqa
   ```
3. **Schemas** — `app/schemas/product.py`:
   ```python
   from pydantic import BaseModel, ConfigDict

   class ProductCreate(BaseModel):
       sku: str
       name: str
       price: float

   class ProductRead(BaseModel):
       model_config = ConfigDict(from_attributes=True)
       id: str
       sku: str
       name: str
       price: float
   ```
4. **Endpoint** — `app/api/v1/endpoints/products.py`:
   ```python
   from fastapi import APIRouter, Depends, HTTPException
   from sqlalchemy.orm import Session
   from app.db.session import get_db
   from app.api.deps import get_current_user, require_roles
   from app.models.product import Product
   from app.schemas.product import ProductCreate, ProductRead

   router = APIRouter(prefix="/products", tags=["products"])

   @router.get("", response_model=list[ProductRead])
   def list_products(db: Session = Depends(get_db), _=Depends(get_current_user)):
       return db.query(Product).all()

   @router.post("", response_model=ProductRead, status_code=201)
   def create_product(
       payload: ProductCreate,
       db: Session = Depends(get_db),
       _=Depends(require_roles("ADMIN", "MANAGER")),
   ):
       product = Product(**payload.model_dump())
       db.add(product)
       db.commit()
       db.refresh(product)
       return product
   ```
5. **Register the router** in `app/api/v1/api.py`:
   ```python
   from app.api.v1.endpoints import auth, admin, products

   api_router.include_router(products.router)
   ```

### 3.4 Protecting routes

- Any logged-in user: `Depends(get_current_user)`
- Restricted to specific roles: `Depends(require_roles("ADMIN"))` or `Depends(require_roles("ADMIN", "MANAGER"))`
- Public (no auth): just don't add either dependency

### 3.5 ⚠️ Gotcha: model relationships and circular imports

If your model has a `relationship("SomeOtherModel")` (string reference), **both** models must be imported before either is used, or SQLAlchemy throws `InvalidRequestError: ... failed to locate a name`. This is why `app/models/__init__.py` imports every model together — always add new models there, don't rely on importing them individually from endpoint files.

Also: models must import `Base` from `app.db.base_class`, **never** from `app.db.base` (that causes a circular import — `base.py` imports models, so models importing back from `base.py` creates a loop).

---

## 4. Local Development Setup (new clone)

```bash
git clone <repo-url>
cd backend

# Python's "npm install" — but env must be created + activated manually every session
python3 -m venv venv          # or `virtualenv venv` if this fails (see §7)
source venv/bin/activate       # do this every new terminal — easy to forget!
pip install -r requirements.txt
```

Create `backend/.env` (get real values from a teammate, never commit this file):
```
DATABASE_URL=mysql+pymysql://USERNAME:PASSWORD@localhost:PORT/DBNAME
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

For local dev, you need an SSH tunnel to reach the DB (it's not exposed publicly):
```bash
ssh -p 22077 -L 3307:localhost:3306 YOUR_USERNAME@web.dcism.org
```
Keep that terminal open, then in your local `.env` use `localhost:3307` instead of `localhost:3306`.

Run locally:
```bash
uvicorn app.main:app --reload --port 8000
```

---

## 5. Git & Deploy Workflow

1. **Branch off `develop`**, work locally, test against your tunneled local DB.
2. **Push your feature branch, open a PR into `develop`.**
3. Once merged into `develop`, whoever's testing on the live server does:

   ```bash
   ssh -p 22077 YOUR_USERNAME@web.dcism.org
   cd ~/ware67-api.dcism.org/Ware67/backend
   source venv/bin/activate
   git fetch origin
   git pull origin develop
   pip install -r requirements.txt      # only if dependencies changed
   ```

4. **Only if there are new/changed models:**
   ```bash
   alembic upgrade head
   ```
   ⚠️ Don't run this reflexively on every deploy — only when a migration was actually added. If you're not sure, ask before running it, since a bad migration against the live DB is hard to undo cleanly.

5. **Restart the app:**
   ```bash
   pm2 restart ware67-api
   pm2 logs ware67-api --lines 30 --nostream
   ```
   Always check the logs after restarting — a clean restart with no traceback in the error log means it's genuinely up, not just "PM2 says online."

6. **Sanity check:**
   ```bash
   curl https://ware67-api.dcism.org/health
   ```

---

## 6. Testing with Postman

Base URL: `https://ware67-api.dcism.org/api/v1`

**Typical flow:**
1. `POST /auth/login` with `{"email": "...", "password": "..."}` → copy `access_token` from the response.
2. For any protected endpoint, add header: `Authorization: Bearer <access_token>`.
3. Access tokens expire after 15 min — when you start getting `401`s, hit `POST /auth/refresh` with your `refresh_token` to get a new pair.

**Tip:** set up a Postman environment variable (e.g. `{{access_token}}`) and use a small script in the login request's "Tests" tab to auto-save it:
```javascript
pm.environment.set("access_token", pm.response.json().access_token);
pm.environment.set("refresh_token", pm.response.json().refresh_token);
```
Then every other request can just use `Authorization: Bearer {{access_token}}` without manual copy-pasting.

**Also test the negative cases**, not just the happy path:
- No `Authorization` header → expect `401`
- Garbage token → expect `401`
- Valid token but wrong role for the endpoint → expect `403`

---

## 7. Known Gotchas (things we already hit, so you don't have to)

- **No `sudo` on the server** — `apt install ...` will always fail with permission denied. If `python3 -m venv` fails with an `ensurepip` error, use this instead:
  ```bash
  pip3 install --user --break-system-packages virtualenv
  ~/.local/bin/virtualenv venv
  ```
- **`pip install --user` blocked by "externally-managed-environment"** — add `--break-system-packages` (safe here since we have no sudo access to break anyway).
- **`bcrypt` + `passlib` version conflict** — if password hashing throws `AttributeError: module 'bcrypt' has no attribute '__about__'`, pin `bcrypt==4.0.1`.
- **`EmailStr` in Pydantic schemas needs an extra package** — if you see `email-validator is not installed`, run `pip install "pydantic[email]"` and add it to `requirements.txt`.
- **Each subdomain has its own assigned port** for Custom Application Hosting — check the panel's subdomain settings, don't assume `4000` or any other default. PM2 must bind to exactly that port or the subdomain shows a placeholder/502 page.
- **Every fresh `git clone` needs its own `venv` and `.env`** — neither is committed to the repo (by design), so re-run the setup in §4 on every new checkout, including on the server.
- **Alembic won't know about tables created via raw SQL** — if a table was created outside of Alembic (e.g. the original schema script), don't run `alembic revision --autogenerate` blindly; it may try to re-create tables that already exist. Use `alembic stamp head` to mark the current state as the baseline instead.

---

## 8. Frontend Integration Notes

- API base URL is set via `VITE_API_BASE_URL` in the frontend's `.env` — locally this points at your tunneled/local backend; in production (`frontend/.env.production`) it should be `https://ware67-api.dcism.org`.
- `frontend/src/api/client.js` already attaches the JWT from `localStorage` (`ware67_token`) to every request via an axios interceptor — after login, store the `access_token` there.
- CORS: the backend's `main.py` has an explicit `allow_origins` list in `CORSMiddleware` — if you add a new frontend origin (e.g. a preview deploy URL), it must be added there or requests will be silently blocked by the browser.