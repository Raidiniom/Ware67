# WARE67 — Local Dev Setup (Tunnel to DB, No More Deploy-to-Test)

This replaces the old loop of `push → merge → SSH → pull → pm2 restart → Postman` for every
change. Instead, you run the backend and frontend **locally**, connected straight to the
shared DCISM database through an SSH tunnel. You only deploy when a feature is actually done.

---

## Prerequisites (one-time)

- Python 3.12+ and Node.js installed locally
- A DCISM SSH username/password
- DB username/password/database name (ask a teammate — matches what's used on the live server)
- Repo cloned locally

---

## 1. Open the SSH tunnel to the database

Open a terminal and run:

```powershell
ssh -p 22077 -L 3307:localhost:3306 YOUR_DCISM_USERNAME@web.dcism.org
```

- `-p 22077` — the SSH server's port
- `-L 3307:localhost:3306` — forwards **your** local port `3307` to the server's MySQL on `3306`
- Enter your SSH password when prompted
- **Leave this terminal open** for the whole session — closing it kills the tunnel and your DB connection will start failing with `Connection refused`.

> Using PuTTY on Windows instead? Session → Host: `web.dcism.org`, Port: `22077`. Then
> Connection → SSH → Tunnels → Source port `3307`, Destination `localhost:3306` → Add → Open.

---

## 2. Configure the backend `.env`

Create/edit `backend/.env` (gitignored — never commit this):

```env
DATABASE_URL=mysql+pymysql://DB_USERNAME:DB_PASSWORD@localhost:3307/DBNAME
JWT_SECRET_KEY=some-local-dev-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
```

- Port must match the **local** side of your `-L` tunnel flag (`3307` above).
- Only include keys that actually exist in `app/core/config.py`'s `Settings` class — pydantic-settings
  rejects unknown env vars by default. If you need extra settings (e.g. `RESET_TOKEN_EXPIRE_MINUTES`,
  `FRONTEND_URL`), add matching fields to `Settings` first.

---

## 3. Set up the Python virtual environment

```powershell
cd backend
python -m venv venv
```

Activate it (PowerShell):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` appear at the start of your prompt.

**In VS Code**, make sure the interpreter matches this venv (not a phantom `.venv`):
- `Ctrl+Shift+P` → **Python: Select Interpreter** → pick `backend\venv\Scripts\python.exe`
- Optional: pin it in `.vscode/settings.json`:
  ```json
  { "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/Scripts/python.exe" }
  ```
- Open a **new** integrated terminal afterward so it auto-activates.

Install dependencies:

```powershell
pip install -r requirements.txt
```

If you're on a host with no sudo / an "externally managed environment" error:
```powershell
pip install -r requirements.txt --break-system-packages
```

---

## 4. Baseline Alembic (first time only, per fresh checkout)

The original schema (`ware67_schema.sql`) was applied outside Alembic, so mark the current
DB state as the baseline **before** ever running a real migration locally:

```powershell
alembic stamp head
```

No output = success (it just recorded the current revision, no DDL was run).

> ⚠️ Only run `alembic upgrade head` (actually applying new migrations) when you know a
> migration was intentionally added — never reflexively.

---

## 5. Run the backend with auto-reload

```powershell
uvicorn app.main:app --reload --port 8000
```

Leave this running. Every saved `.py` change triggers an automatic restart — no manual
`pm2 restart` needed.

Verify it's alive (new terminal):

```powershell
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Browse the interactive API docs at **http://127.0.0.1:8000/docs** (Swagger UI) — you can call
any endpoint, including protected ones (click "Authorize" and paste `Bearer <access_token>`
after logging in via `/auth/login`).

---

## 6. Point the frontend at your local backend

Create `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Run it:

```powershell
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173` by default. `backend/app/main.py`'s CORS config already
allows this origin, so no backend changes are needed.

---

## 7. Your day-to-day loop

Three terminals running simultaneously:

| Terminal | Command | Purpose |
|---|---|---|
| 1 | `ssh -p 22077 -L 3307:localhost:3306 USER@web.dcism.org` | DB tunnel |
| 2 | `uvicorn app.main:app --reload --port 8000` (from `backend/`) | Backend, auto-reloads |
| 3 | `npm run dev` (from `frontend/`) | Frontend, auto-reloads |

Edit code → auto-reload → test in Swagger UI (`/docs`) or the running frontend → repeat.
No git push, no SSH deploy, no pm2 restart, until a feature is actually ready to ship.

---

## 8. Only deploy when a feature is actually done

```powershell
git push origin your-branch
# open PR into develop, merge

ssh -p 22077 YOUR_DCISM_USERNAME@web.dcism.org
cd ~/ware67-api.dcism.org/Ware67/backend
source venv/bin/activate
git pull origin develop
pip install -r requirements.txt --break-system-packages   # only if deps changed
alembic upgrade head                                       # only if a migration was added
pm2 restart ware67-api
pm2 logs ware67-api --lines 30 --nostream

curl https://ware67-api.dcism.org/health
```

---

## Troubleshooting quick reference

| Error | Cause | Fix |
|---|---|---|
| `pydantic_core.ValidationError: Extra inputs are not permitted` | `.env` has keys not defined in `Settings` | Remove the extra keys from `.env`, or add matching fields to `app/core/config.py` |
| `ModuleNotFoundError: No module named 'pymysql'` | Driver not installed in the active venv | `pip install pymysql`, confirm it's in `requirements.txt` |
| `.venv/Scripts/python.exe` not found | VS Code guessed the wrong interpreter folder name | Reselect interpreter (`Ctrl+Shift+P` → Python: Select Interpreter) → point at `backend\venv\Scripts\python.exe` |
| `pymysql.err.OperationalError: Can't connect to MySQL server on 'localhost'` (Connection refused) | SSH tunnel isn't running, or `.env` port doesn't match the tunnel's local port | Reopen the `ssh -L` tunnel; make sure `DATABASE_URL` uses the same local port (e.g. `3307`) |
| `ImportError: email-validator is not installed` | `pydantic[email]` extra didn't fully install | `pip install email-validator` (or re-run `pip install -r requirements.txt`) |

---

## Notes / gotchas

- **Shared DB warning:** everyone's local backend points at the *same* remote DB via tunnel —
  there's no separate local copy. Be careful with destructive testing or concurrent migrations;
  coordinate with teammates before running `alembic upgrade head`.
- Don't commit `backend/.env` or `frontend/.env.local` — both are gitignored by design.
- If `requirements.txt` is missing a package someone added locally, add it there too so fresh
  clones don't break the same way.