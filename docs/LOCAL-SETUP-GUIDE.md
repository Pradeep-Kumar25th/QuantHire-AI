# QuantHire AI — Local Setup Guide

**Document type:** Developer onboarding / local environment  
**Audience:** Malomatia engineering — clone from **Azure DevOps** or GitHub and run on a laptop  
**Verified against:** Repository `main` (FastAPI `app.main`, Next BFF, Alembic, CI env)  
**Goal:** Run **frontend + backend** locally without full production Docker images  

**Hosted app (no local setup required to use):** https://quanthire-npd.malomatia.com  

**Related:** [CONSOLIDATED-TECHNICAL-DOCUMENTATION.md](./CONSOLIDATED-TECHNICAL-DOCUMENTATION.md) · [nonprod-deploy-handover-guide.md](./nonprod-deploy-handover-guide.md)  

---

## Table of contents

1. [Before you start](#1-before-you-start)  
2. [Clone the repository](#2-clone-the-repository)  
3. [Architecture of local dev](#3-architecture-of-local-dev)  
4. [Setup levels (L1 / L2 / L3)](#4-setup-levels-l1--l2--l3)  
5. [Install prerequisites](#5-install-prerequisites)  
6. [Environment file (important)](#6-environment-file-important)  
7. [Database setup (L2+)](#7-database-setup-l2)  
8. [Backend setup (FastAPI)](#8-backend-setup-fastapi)  
9. [Frontend setup (Next.js + BFF)](#9-frontend-setup-nextjs--bff)  
10. [Verify the installation](#10-verify-the-installation)  
11. [Optional configurations](#11-optional-configurations)  
12. [Daily developer workflow](#12-daily-developer-workflow)  
13. [Run tests](#13-run-tests)  
14. [Troubleshooting](#14-troubleshooting)  
15. [When to use Docker](#15-when-to-use-docker)  
16. [Getting help](#16-getting-help)  

---

## 1. Before you start

| Question | Answer |
|----------|--------|
| Need local setup to **use** QuantHire? | **No** — use NPD + Entra/TAMM access |
| Need local setup to **change code**? | **Yes** — follow this guide |
| Why not full app Docker locally? | Images are large; native Node + Python matches CI dev workflow |
| What matches Non-Prod AI? | **L3** + `LLM_PROVIDER=azure_openai` + Azure keys + pgvector |

**Estimated time (first time):** L1 ~45 min · L2 +30 min · L3 +1–2 h (Azure credentials)  

---

## 2. Clone the repository

### Azure DevOps (Malomatia)

```bash
git clone <your-azure-devops-repo-url>
cd "QuantHire AI"    # or your folder name — Windows: cd /d "d:\QuantHire AI"
git checkout main
git pull
```

### GitHub (mirror)

```bash
git clone https://github.com/Pradeep-Kumar25th/QuantHire-AI.git
cd QuantHire-AI
git checkout main
```

**Sanity check:**

```bash
dir Dockerfile.backend Dockerfile.frontend    # Windows
# ls Dockerfile.backend Dockerfile.frontend   # macOS/Linux
dir docs\LOCAL-SETUP-GUIDE.md               # Windows
```

---

## 3. Architecture of local dev

```text
Browser  →  http://localhost:3000  (Next.js + BFF)
              /api/v1/*  ──proxy──►  http://localhost:8000  (FastAPI)
                                         │
                         agents + quantchat (same Python process)
                                         │
                                    PostgreSQL (L2+; pgvector for L3)
                                    Azure OpenAI + DI (L3)
```

| Process | Directory | Port |
|---------|-----------|------|
| Frontend + BFF | `apps/web` | **3000** |
| API | `apps/api` | **8000** |

**Rule:** Always use the browser at **`http://localhost:3000`**. Do not use `:8000` as the UI origin (auth cookies and BFF expect same-origin `/api`).

---

## 4. Setup levels (L1 / L2 / L3)

| Level | You can… | Requires |
|-------|----------|----------|
| **L1** | API liveness, Swagger, BFF health | Node, Python, `.env` with Milvus **off** |
| **L2** | Login (basic), dashboard, jobs/candidates CRUD | L1 + PostgreSQL + Alembic + test user |
| **L3** | JD generate, resume parse, QuantChat, matching | L2 + Azure OpenAI (+ Document Intelligence; blob optional) |

Complete **L1 → L2 → L3** in order.

---

## 5. Install prerequisites

| Tool | Version | Verify |
|------|---------|--------|
| Git | 2.x | `git --version` |
| **Node.js** | **20.x** | `node --version` |
| **Python** | **3.11.x** | `py -3.11 --version` (Windows) / `python3.11 --version` |
| **PostgreSQL** | **14+** with **pgvector** (L2+) | See §7 |

**Windows:** Python 3.11 **64-bit**; if `pip install` fails on native wheels, install **Visual Studio Build Tools** (C++).  

**Do not use Bun** for the web app — use **npm** (`npm ci --legacy-peer-deps`).

---

## 6. Environment file (important)

The API loads environment variables in this order (`apps/api/app/main.py`):

1. **Repository root** `.env` (preferred — one file for the whole monorepo)  
2. Else **`apps/api/.env`**

Create **`.env` at the repository root** (same folder as `Dockerfile.backend`).

### 6.1 Recommended local `.env` (copy and edit)

**Minimum for L1 (API + web wire-up):**

```env
# --- Local L1: API starts without Postgres / Milvus ---
APP_ENV=development
DEBUG=true
AUTH_MODE=none
DEPLOYMENT_TARGET=local

API_HOST=0.0.0.0
API_PORT=8000

# Prevent startup from connecting to Milvus (defaults would try localhost:19530)
MILVUS_ENABLED=false
MILVUS_AUTO_LOAD=false
VECTOR_STORE=pgvector
```

**Add for L2 (database + login):**

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quanthire
JWT_SECRET_KEY=local-dev-jwt-secret-at-least-32-characters-long
AUTH_MODE=basic
```

**Add for L3 (Azure OpenAI — same pattern as NPD; values from platform team):**

```env
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://aif-ail-npd-we-01.openai.azure.com/
AZURE_OPENAI_API_KEY=<secret>
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://di-ail-npd-we-01.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=<secret>
# or AZURE_DOCUMENT_INTELLIGENCE_API_KEY=<secret>

# Optional resume blob parity with NPD:
# STORAGE_TYPE=azure_blob
# AZURE_STORAGE_CONNECTION_STRING=<secret>
```

**Notes:**

- `DATABASE_URL` may use `postgresql://` or `postgresql+asyncpg://`; the app normalizes for asyncpg.  
- Alembic (migrations) reads the same `DATABASE_URL` and strips `+asyncpg` for sync migration runs.  
- Never commit real secrets to Git.  
- Root **`.env.example`** shows Vertex/GCP alternates; **NPD parity uses Azure OpenAI** as above.  

**Frontend env** is separate: `apps/web/.env.local` (§9).

---

## 7. Database setup (L2+)

Alembic migrations require PostgreSQL with the **`vector`** extension (pgvector).

### Option A — Postgres + pgvector via Docker (recommended)

```bash
docker run -d --name quanthire-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=quanthire \
  pgvector/pgvector:pg16
```

Use in root `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quanthire
```

### Option B — Native PostgreSQL

Install PostgreSQL 14+, then install **pgvector** for your OS (extension must exist before `alembic upgrade head`). Create DB:

```sql
CREATE DATABASE quanthire;
```

### Option C — Azure NPD Postgres

Only with platform approval (VPN/firewall). Confirm whether you may run **`alembic upgrade head`** against NPD.

---

## 8. Backend setup (FastAPI)

### 8.1 Virtual environment and dependencies

**Windows (PowerShell) — from repo root:**

```powershell
cd apps\api
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
cd apps/api
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.linux.txt
```

### 8.2 Run migrations (L2+)

Ensure root `.env` has `DATABASE_URL`. With venv active and **`apps/api` as current directory**:

```bash
alembic upgrade head
```

Expected: migrations apply including `CREATE EXTENSION IF NOT EXISTS vector`. If extension fails, use Option A (pgvector image) in §7.

### 8.3 Create test user (L2, `AUTH_MODE=basic`)

From **`apps/api`** with venv active:

```bash
python scripts/create_test_user.py
```

| Field | Default |
|-------|---------|
| Email | `hr.test@malomatia.com` |
| Password | `ChangeMe123!` |
| Role | `recruiter` |

Override: `python scripts/create_test_user.py --email you@malomatia.com --password YourPass123!`

### 8.4 PYTHONPATH and start the API

Agents and QuantChat are **not** installed as separate packages; Python must see monorepo paths.

**Windows (PowerShell) — from repo root:**

```powershell
$env:PYTHONPATH = "apps;apps/api;apps/agents;apps/agents/agents;apps/quantchat"
cd apps\api
.\.venv\Scripts\Activate.ps1
python run.py
```

**macOS / Linux — from repo root:**

```bash
export PYTHONPATH="apps:apps/api:apps/agents:apps/agents/agents:apps/quantchat"
cd apps/api && source .venv/bin/activate && python run.py
```

**What you should see:**

- Uvicorn on `http://0.0.0.0:8000`  
- With `DEBUG=true`, auto-reload watching `apps/api` and repo root  
- If DB is missing, a **warning** that DB init was skipped (OK for L1)  
- With `MILVUS_ENABLED=false`, no Milvus connection attempts  

**Alternative (same venv / PYTHONPATH):**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

(Run from `apps/api`.)

---

## 9. Frontend setup (Next.js + BFF)

### 9.1 Configure BFF

```bash
cd apps/web
cp .env.example .env.local
```

**Required in `apps/web/.env.local`:**

```env
BFF_BACKEND_URL=http://localhost:8000
```

Do not add `/api` to the end — the BFF normalizes the base URL.

### 9.2 Install and run

```bash
npm ci --legacy-peer-deps
npm run dev
```

App listens on **http://localhost:3000**.

The BFF proxies browser calls to `BFF_BACKEND_URL` (see `apps/web/src/app/api/[...path]/route.ts`). Long AI routes use extended timeouts (~620s).

---

## 10. Verify the installation

### 10.1 Checklist

| # | Check | URL / action | Expected |
|---|-------|----------------|----------|
| 1 | API liveness | http://localhost:8000/healthz | JSON `"status":"healthy"` |
| 2 | API health (BFF path) | http://localhost:8000/api/health | `"status":"healthy"` |
| 3 | BFF health | http://localhost:3000/api/health | Proxied JSON from API |
| 4 | Swagger (L1) | http://localhost:8000/docs | OpenAPI UI |
| 5 | Login (L2) | http://localhost:3000/login | Basic auth with test user |
| 6 | Dashboard (L2) | http://localhost:3000/dashboard | Loads after login |
| 7 | QuantChat (L3) | http://localhost:3000/dashboard/chat | Response from Azure OpenAI |
| 8 | JD generate (L3) | Jobs → Generate JD | Completes (may take minutes) |

### 10.2 `readyz` vs `healthz`

| Endpoint | Meaning locally |
|----------|-----------------|
| `/healthz` | Process is up — use for **L1** |
| `/readyz` | Includes DB/deps — may return **503** without Postgres; use after **L2** |

### 10.3 Quick curl

```bash
curl -s http://localhost:8000/healthz
curl -s http://localhost:3000/api/health
```

---

## 11. Optional configurations

### UI only against remote NPD API

If platform allows your IP/VPN:

```env
# apps/web/.env.local
BFF_BACKEND_URL=https://<approved-npd-api-host>
```

Run only `npm run dev` in `apps/web`. Confirm CORS and auth with your team.

### Entra SSO locally

1. Root `.env`: `AUTH_MODE=entra`, `AZURE_AD_CLIENT_ID`, `AZURE_AD_TENANT_ID`, `AZURE_AD_CLIENT_SECRET`  
2. `apps/web/.env.local`: same client/tenant (public IDs)  
3. Entra app **AIL-QUANTHIRE-NPD**: redirect URI `http://localhost:3000`  
4. User has app role (e.g. **RECRUITER**)  

### IDE (Cursor / VS Code)

Open **repository root**. Quick Open: `LOCAL-SETUP-GUIDE`.

---

## 12. Daily developer workflow

| Terminal | Where | Command |
|----------|-------|---------|
| 1 | Repo root → set `PYTHONPATH` → `apps/api` | `python run.py` (venv active) |
| 2 | `apps/web` | `npm run dev` |

Browser: **http://localhost:3000**

After `git pull`:

```bash
# Backend (if requirements changed)
cd apps/api && pip install -r requirements.txt   # or requirements.linux.txt

# Frontend
cd apps/web && npm ci --legacy-peer-deps

# Schema
cd apps/api && alembic upgrade head
```

---

## 13. Run tests

Matches `.github/workflows/deploy-nonprod.yml` validate job.

**bash (repo root):**

```bash
export JWT_SECRET_KEY="test-jwt-secret-key-with-32-chars-minimum"
export APP_ENV=testing
export AUTH_MODE=none
export MILVUS_ENABLED=false
export PYTHONPATH=apps:apps/api:apps/agents:apps/agents/agents:apps/quantchat
pytest tests/unit -q
```

**PowerShell (repo root):**

```powershell
$env:JWT_SECRET_KEY="test-jwt-secret-key-with-32-chars-minimum"
$env:APP_ENV="testing"
$env:AUTH_MODE="none"
$env:MILVUS_ENABLED="false"
$env:PYTHONPATH="apps;apps/api;apps/agents;apps/agents/agents;apps/quantchat"
pytest tests/unit -q
```

Frontend (CI):

```bash
cd apps/web && npm ci --legacy-peer-deps && npm run type-check && npm run build
```

---

## 14. Troubleshooting

| Symptom | Cause | Fix |
|---------|--------|-----|
| API hang on startup | Milvus connection | Set `MILVUS_ENABLED=false` and `MILVUS_AUTO_LOAD=false` in root `.env` |
| `502` on `/api/health` | API not running | Start `python run.py`; check `BFF_BACKEND_URL=http://localhost:8000` |
| `401` on dashboard | Auth on, not logged in | `AUTH_MODE=none` for L1, or login with test user (L2) |
| `ModuleNotFoundError: agents` / `quantchat` | PYTHONPATH | Set full PYTHONPATH from repo root (§8.4) |
| Alembic `vector` extension error | Postgres without pgvector | Use `pgvector/pgvector` Docker image (§7A) |
| DB connection refused | Postgres down / wrong URL | Start DB; fix `DATABASE_URL` |
| JD / chat / match errors | No LLM keys | L3 Azure vars; `LLM_PROVIDER=azure_openai` |
| `pip install` fails (Windows) | Missing build tools | VS Build Tools; Python 3.11 x64 |
| `npm ci` fails | Wrong Node version | Install Node **20** |
| Port 3000 in use | Other process | Free port or `next dev -p 3001` (remember to use that port in browser) |
| `/readyz` 503 on L1 | No database | Normal — use `/healthz` until L2 |

---

## 15. When to use Docker

| Scenario | Approach |
|----------|----------|
| Daily coding | **This guide** (native web + API) |
| Local database only | `pgvector/pgvector:pg16` container (§7A) |
| Release to NPD | [nonprod-deploy-handover-guide.md](./nonprod-deploy-handover-guide.md) |
| Full stack in Docker on laptop | Not recommended (RAM/disk) |

---

## 16. Getting help

Include: setup level (L1/L2/L3), OS, exact command, last 30 lines of API/web logs, and whether root `.env` uses Azure or local DB.

**Code references:**

- BFF proxy: `apps/web/src/app/api/[...path]/route.ts`  
- API entry: `apps/api/run.py`, `apps/api/app/main.py`  
- Settings: `apps/api/app/config.py`  
- Test user: `apps/api/scripts/create_test_user.py`  

---

## Appendix — Copy-paste quick start (L2, Windows)

```bat
cd /d "d:\QuantHire AI"

REM 1) Root .env — create manually with sections from §6 (L1+L2 blocks)

REM 2) Postgres (Docker)
docker run -d --name quanthire-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=quanthire pgvector/pgvector:pg16

REM 3) Backend
cd apps\api
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python scripts/create_test_user.py
cd ..\..

REM 4) Start API (new terminal)
set PYTHONPATH=apps;apps/api;apps/agents;apps/agents/agents;apps/quantchat
cd apps\api
.\.venv\Scripts\Activate.ps1
python run.py

REM 5) Frontend (new terminal)
cd apps\web
copy .env.example .env.local
npm ci --legacy-peer-deps
npm run dev
```

Browser: **http://localhost:3000** — login `hr.test@malomatia.com` / `ChangeMe123!`

---

*End of local setup guide — verified against application startup, config loaders, BFF health proxy, Alembic pgvector migrations, and CI test env.*
