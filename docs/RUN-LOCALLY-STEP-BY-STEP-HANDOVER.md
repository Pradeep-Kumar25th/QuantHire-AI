# QuantHire AI — Run locally on your laptop (step-by-step handover guide)

> **Latest (ZIP from Teams):** use **[LOCAL-SETUP-GUIDE-ZIP-HANDOVER.md](./LOCAL-SETUP-GUIDE-ZIP-HANDOVER.md)** and root **`RUN-QUANTHIRE-LOCALLY-READ-ME-FIRST.md`**. This file is kept for reference.

**Audience:** Malomatia team receiving the **zipped project** via Teams (or Azure DevOps clone)  
**One-page version:** [TEAMS-LOCAL-QUICK-START.md](./TEAMS-LOCAL-QUICK-START.md) · **Teams paste text:** [TEAMS-MESSAGE-LOCAL-SETUP.txt](./TEAMS-MESSAGE-LOCAL-SETUP.txt)  
**Project folder example:** `D:\QuantHire AI`  
**Time:** First setup ~1–2 hours (L2); full AI features (L3) depend on Azure credentials  

**You do not need local setup to use the hosted app:** https://quanthire-npd.malomatia.com (requires Entra/TAMM access).

---

## What you received

The zip contains the **full monorepo**, for example:

| Item | Purpose |
|------|---------|
| `apps\web` | Next.js UI + BFF (browser port **3000**) |
| `apps\api` | FastAPI backend (port **8000**) |
| `apps\agents` | JD, matching, parsing agents (loaded by API) |
| `apps\quantchat` | QuantChat RAG (loaded by API) |
| `docs\` | All handover `.md` guides |
| `Dockerfile.backend` / `Dockerfile.frontend` | Production images (optional for local dev) |
| `docker-compose*.yml` | Optional Docker stacks (if present in your zip) |
| `.env.example` | Template — **do not use someone else’s `.env` as-is** |

**Recommended way to run on a laptop:** **Native** Node + Python + Postgres (not full Docker app images — they are heavy).

---

## Part A — Before you start

### A1. Install software

| Software | Version | Download / check |
|----------|---------|------------------|
| **Node.js** | **20.x LTS** | https://nodejs.org — `node --version` |
| **Python** | **3.11.x** (64-bit) | https://www.python.org — `py -3.11 --version` |
| **Git** | Optional if you only use zip | https://git-scm.com |
| **Docker Desktop** | Optional (Postgres only or full compose) | https://www.docker.com/products/docker-desktop/ |
| **Visual Studio Build Tools** | Only if `pip install` fails on Windows | “Desktop development with C++” |

### A2. Unzip the project

1. Save the Teams zip to disk (e.g. `Downloads`).  
2. **Extract** to a short path, e.g. `D:\QuantHire AI`.  
3. Avoid deeply nested paths (Windows path length limits).

### A3. Clean up after unzip (important)

A zip from another machine may include **broken local paths**. Do this once:

| Remove or recreate | Why |
|--------------------|-----|
| **`venv`** at repo root (if present) | Tied to original PC; recreate in `apps\api` |
| **`apps\api\.venv`** | OK to keep if you created it; otherwise delete and recreate |
| **`node_modules`** | Optional: delete and run `npm ci` fresh (recommended) |
| **`__pycache__`**, **`cache`**, **`logs`** | Safe to delete; regenerated at runtime |
| **`.env` from handover** | **Delete or rename** — create your own from templates below (security) |

Do **not** delete: `apps`, `docs`, `infra`, `Dockerfile.*`, `.env.example`.

### A4. Open the folder in Cursor / VS Code

**File → Open Folder →** `D:\QuantHire AI`

Handover docs: **`docs\LOCAL-SETUP-GUIDE.md`**, **`docs\RUN-LOCALLY-STEP-BY-STEP-HANDOVER.md`** (this file).

---

## Part B — Choose your setup level

| Level | What works | Database | AI (Azure) |
|-------|------------|----------|------------|
| **L1** | API + UI wire-up, Swagger | Not required | Not required |
| **L2** | Login, jobs, candidates, dashboard | **Required** | Optional |
| **L3** | JD generate, resume parse, QuantChat, matching | **Required** + pgvector | **Azure OpenAI** (+ Document Intelligence) |

Do **L1 → L2 → L3** in order.

---

## Part C — Configuration (what you must change)

### C1. Create backend environment file

Create a **new** file at the **repository root**:

**`D:\QuantHire AI\.env`**

Copy the block for your level and edit values.

#### L1 — minimum (API starts without database)

```env
APP_ENV=development
DEBUG=true
AUTH_MODE=none
DEPLOYMENT_TARGET=local
API_HOST=0.0.0.0
API_PORT=8000

MILVUS_ENABLED=false
MILVUS_AUTO_LOAD=false
VECTOR_STORE=pgvector
```

#### L2 — add database and login

Add to the same `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quanthire
JWT_SECRET_KEY=your-local-jwt-secret-at-least-32-characters-long
AUTH_MODE=basic
```

#### L3 — full AI (request keys from platform team; mirror Non-Prod)

Add to the same `.env`:

```env
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://aif-ail-npd-we-01.openai.azure.com/
AZURE_OPENAI_API_KEY=PASTE_SECRET_HERE
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://di-ail-npd-we-01.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=PASTE_SECRET_HERE

# Optional: resume files to Azure Blob like NPD
# AZURE_STORAGE_CONNECTION_STRING=PASTE_SECRET_HERE
```

**Never commit `.env` to Git or share it on Teams.**

### C2. Frontend environment file

Create:

**`D:\QuantHire AI\apps\web\.env.local`**

```env
BFF_BACKEND_URL=http://localhost:8000
```

No trailing `/api`. The Next.js BFF adds `/api/v1/...` when proxying.

### C3. What you usually do **not** need to change

- Source code under `apps\` for first run  
- `BFF` proxy code — already points using `BFF_BACKEND_URL`  
- Entra SSO for first local test — use **L2 basic auth** + test user  

---

## Part D — Database (L2 and L3)

### Option 1 — Postgres + pgvector in Docker (recommended)

Open **PowerShell** or **CMD**:

```bat
docker run -d --name quanthire-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=quanthire pgvector/pgvector:pg16
```

Ensure `.env` has:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quanthire
```

### Option 2 — Local PostgreSQL

Install PostgreSQL 14+ and the **pgvector** extension, create database `quanthire`, set `DATABASE_URL` accordingly.

---

## Part E — Backend setup (step-by-step, Windows)

### E1. Open terminal 1 — PowerShell

```powershell
cd "D:\QuantHire AI\apps\api"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

If install fails, install **Visual Studio Build Tools** and retry.

### E2. Run database migrations (L2+ only)

Still in `apps\api` with venv active:

```powershell
alembic upgrade head
```

If you see an error about extension **`vector`**, use the Docker image in Part D (pgvector).

### E3. Create login user (L2, basic auth)

```powershell
python scripts\create_test_user.py
```

Default credentials:

| Field | Value |
|-------|-------|
| Email | `hr.test@malomatia.com` |
| Password | `ChangeMe123!` |

### E4. Start the API

From **repository root** (important for reload paths):

```powershell
cd "D:\QuantHire AI"
$env:PYTHONPATH = "apps;apps\api;apps\agents;apps\agents\agents;apps\quantchat"
cd apps\api
.\.venv\Scripts\Activate.ps1
python run.py
```

**Success:** console shows Uvicorn on `http://0.0.0.0:8000`.

Leave this terminal **open**.

**Quick test (new browser tab):**  
http://localhost:8000/healthz → should show `"status":"healthy"`.

---

## Part F — Frontend setup (step-by-step, Windows)

### F1. Open terminal 2 — PowerShell

```powershell
cd "D:\QuantHire AI\apps\web"
npm ci --legacy-peer-deps
npm run dev
```

**Success:** `ready on http://localhost:3000`

Leave this terminal **open**.

---

## Part G — Use the application

1. Open browser: **http://localhost:3000**  
2. **L1:** Dashboard may work without login if `AUTH_MODE=none`.  
3. **L2:** Go to **Login** → `hr.test@malomatia.com` / `ChangeMe123!`  
4. Explore: **Jobs**, **Candidates**, **Match**, **QuantChat** (L3 needs Azure keys).

**Always use port 3000 in the browser** — not http://localhost:8000 for normal use.

---

## Part H — Verify everything

| Step | URL | Expected |
|------|-----|----------|
| 1 | http://localhost:8000/healthz | JSON healthy |
| 2 | http://localhost:3000/api/health | JSON from backend via BFF |
| 3 | http://localhost:3000/login | Login page (L2) |
| 4 | http://localhost:3000/dashboard | After login (L2) |
| 5 | Generate JD / upload resume / chat | Works on L3 with Azure configured |

**Note:** http://localhost:8000/readyz may return **503** without DB — that is normal on L1. Use `/healthz` until L2 is done.

---

## Part I — Daily workflow (two terminals)

| Terminal | Commands |
|----------|----------|
| **1 — API** | `cd "D:\QuantHire AI"` → set `$env:PYTHONPATH` (as E4) → `cd apps\api` → activate venv → `python run.py` |
| **2 — Web** | `cd "D:\QuantHire AI\apps\web"` → `npm run dev` |

Browser: **http://localhost:3000**

---

## Part J — Optional: Docker Compose (if your zip includes it)

If you have `docker-compose.dev.yml` or `docker-compose.complete.yml` and a **powerful PC**:

1. Read comments inside the compose file for required env vars.  
2. Prefer **postgres-only** in Docker and still run **web + API natively** (see `docs\LOCAL-SETUP-GUIDE.md`).  

Full app Docker builds are **large**; Malomatia handover standard is **native** (Parts E–F).

---

## Part K — Troubleshooting

| Problem | Solution |
|---------|----------|
| API hangs on startup | Set `MILVUS_ENABLED=false` and `MILVUS_AUTO_LOAD=false` in root `.env` |
| `502` on `/api/health` | Start backend (Terminal 1); check `BFF_BACKEND_URL=http://localhost:8000` |
| `ModuleNotFoundError: agents` | Set full `PYTHONPATH` from repo root (step E4) |
| `401` after login | Check `AUTH_MODE=basic`, user created, `JWT_SECRET_KEY` length ≥ 32 |
| Alembic / `vector` error | Use `pgvector/pgvector:pg16` container |
| JD / chat fails | Complete L3 Azure variables; confirm keys with platform team |
| `npm ci` errors | Use Node **20**; run from `apps\web` |
| Port 3000 in use | Stop other app or `npm run dev -- -p 3001` and open that port |
| Zip `venv` / `node_modules` broken | Delete them; rerun E1 and F1 |

---

## Part L — Run tests (optional)

From repo root, PowerShell:

```powershell
cd "D:\QuantHire AI"
$env:JWT_SECRET_KEY="test-jwt-secret-key-with-32-chars-minimum"
$env:APP_ENV="testing"
$env:AUTH_MODE="none"
$env:MILVUS_ENABLED="false"
$env:PYTHONPATH="apps;apps\api;apps\agents;apps\agents\agents;apps\quantchat"
pytest tests\unit -q
```

---

## Part M — Where documentation lives in your folder

After unzip, all markdown guides are under:

```text
D:\QuantHire AI\docs\
```

| File | Topic |
|------|--------|
| **RUN-LOCALLY-STEP-BY-STEP-HANDOVER.md** | This guide |
| **LOCAL-SETUP-GUIDE.md** | Extended local setup + macOS/Linux |
| **CONSOLIDATED-TECHNICAL-DOCUMENTATION.md** | Architecture and features |
| **QUANTHIRE-BUSINESS-REQUIREMENTS-DOCUMENT-BRD.md** | BRD |
| **nonprod-deploy-handover-guide.md** | Deploy to Azure Non-Prod |

---

## Part N — Getting help

When reporting an issue, send:

1. Level (L1 / L2 / L3)  
2. Windows version  
3. Step letter (E, F, …) where it failed  
4. Last **20 lines** from API or web terminal  

---

## Quick reference card (printable)

```text
1. Unzip → D:\QuantHire AI
2. Delete old .env, venv, node_modules (recommended)
3. Create D:\QuantHire AI\.env (L1+L2 blocks)
4. Create apps\web\.env.local → BFF_BACKEND_URL=http://localhost:8000
5. Docker: pgvector/pgvector:pg16 on port 5432
6. apps\api: venv, pip install, alembic upgrade head, create_test_user.py
7. Terminal 1: PYTHONPATH + python run.py
8. Terminal 2: apps\web → npm ci --legacy-peer-deps → npm run dev
9. Browser: http://localhost:3000
```

---

*End of step-by-step handover guide — QuantHire AI local run from Teams zip / Azure DevOps.*
