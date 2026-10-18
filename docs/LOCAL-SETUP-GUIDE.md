# QuantHire AI — Local Setup Guide

**Document type:** Developer onboarding / local environment  
**Audience:** Malomatia engineering (e.g. Shraddha’s team) — clone from **Azure DevOps** or GitHub and run on a laptop  
**Goal:** Run **frontend + backend** locally without building full production Docker images  
**Non-Prod URL (hosted app — no local setup required to use):** https://quanthire-npd.malomatia.com  

**Related:** [CONSOLIDATED-TECHNICAL-DOCUMENTATION.md](./CONSOLIDATED-TECHNICAL-DOCUMENTATION.md) · [nonprod-deploy-handover-guide.md](./nonprod-deploy-handover-guide.md)  

---

## Table of contents

1. [Before you start](#1-before-you-start)  
2. [Clone the repository](#2-clone-the-repository)  
3. [Architecture of local dev](#3-architecture-of-local-dev)  
4. [Setup levels (L1 / L2 / L3)](#4-setup-levels-l1--l2--l3)  
5. [Install prerequisites](#5-install-prerequisites)  
6. [Database setup](#6-database-setup)  
7. [Backend setup (FastAPI)](#7-backend-setup-fastapi)  
8. [Frontend setup (Next.js + BFF)](#8-frontend-setup-nextjs--bff)  
9. [Verify the installation](#9-verify-the-installation)  
10. [Optional configurations](#10-optional-configurations)  
11. [Daily developer workflow](#11-daily-developer-workflow)  
12. [Run tests](#12-run-tests)  
13. [Troubleshooting](#13-troubleshooting)  
14. [When to use Docker](#14-when-to-use-docker)  
15. [Getting help](#15-getting-help)  

---

## 1. Before you start

| Question | Answer |
|----------|--------|
| Do I need local setup to **use** QuantHire? | **No** — use NPD URL + Entra/TAMM access |
| Do I need local setup to **change code**? | **Yes** — follow this guide |
| Why not run full Docker locally? | Backend + frontend images are large; native Node + Python is faster for daily dev |
| What matches Non-Prod? | **L3** setup + Azure OpenAI, Document Intelligence, pgvector |

**Estimated time:**

| Level | Time (first time) |
|-------|-------------------|
| L1 — UI + API wire-up | 30–60 minutes |
| L2 — DB + login | +30 minutes |
| L3 — Full AI features | +1–2 hours (depends on Azure credential access) |

---

## 2. Clone the repository

### From Azure DevOps (Malomatia)

Use the URL and branch your project lead provided (typically **`main`**).

```bash
git clone <your-azure-devops-repo-url>
cd QuantHire-AI   # or folder name used in ADO
git checkout main
git pull
```

### From GitHub (mirror)

```bash
git clone https://github.com/Pradeep-Kumar25th/QuantHire-AI.git
cd QuantHire-AI
git checkout main
```

**Confirm documentation is present:**

```bash
ls docs/LOCAL-SETUP-GUIDE.md docs/CONSOLIDATED-TECHNICAL-DOCUMENTATION.md
```

If `docs/` is missing, sync from `main` or request an updated push to Azure DevOps.

---

## 3. Architecture of local dev

```text
┌─────────────┐     http://localhost:3000      ┌──────────────────┐
│   Browser   │ ─────────────────────────────► │  Next.js (web)   │
└─────────────┘     /api/v1/* same origin      │  BFF proxy       │
                                               └────────┬─────────┘
                                                        │ BFF_BACKEND_URL
                                                        ▼
                                               ┌──────────────────┐
                                               │ FastAPI (api)    │
                                               │  + agents        │
                                               │  + quantchat     │
                                               └────────┬─────────┘
                                                        │
                        ┌───────────────────────────────┼───────────────────────────────┐
                        ▼                               ▼                               ▼
                 PostgreSQL                      Azure OpenAI                      Document Intelligence
                 (local or remote)               (L3 optional)                     (L3 optional)
```

| Process | Directory | Default port |
|---------|-----------|--------------|
| Frontend + BFF | `apps/web` | **3000** |
| API | `apps/api` | **8000** |

**Important:** Use the browser at **`http://localhost:3000`**. Do not use `http://localhost:8000` as the main UI origin (cookies / BFF / auth expect same-origin `/api`).

---

## 4. Setup levels (L1 / L2 / L3)

| Level | You can… | Requires |
|-------|----------|----------|
| **L1** | Load UI, hit health/docs, smoke BFF → API | Node, Python, env with `AUTH_MODE=none` |
| **L2** | Login, CRUD jobs/candidates, applications | L1 + PostgreSQL + migrations + test user or Entra |
| **L3** | JD generation, resume parse, QuantChat, matching | L2 + Azure OpenAI (+ DI, blob optional) |

**Recommendation:** Complete **L1 → L2 → L3** in order.

---

## 5. Install prerequisites

| Tool | Version | Verify command |
|------|---------|----------------|
| **Git** | 2.x | `git --version` |
| **Node.js** | **20.x** | `node --version` |
| **npm** | 10.x (with Node 20) | `npm --version` |
| **Python** | **3.11.x** | `python --version` or `py -3.11 --version` |
| **PostgreSQL** | **14+** | `psql --version` (L2+) |

**Windows notes:**

- Install Python 3.11 **64-bit** from python.org or Microsoft Store.  
- If `pip install` fails on native extensions, install **Visual Studio Build Tools** (C++ workload).  
- Use **PowerShell** for commands below unless you prefer CMD.

**macOS / Linux:**

- Use `python3.11 -m venv` and `requirements.linux.txt` for backend deps.

---

## 6. Database setup

### Option A — Local PostgreSQL (recommended)

1. Install PostgreSQL 14+.  
2. Create database and user:

```sql
CREATE USER quanthire WITH PASSWORD 'your_local_password';
CREATE DATABASE quanthire OWNER quanthire;
```

3. Connection string for `.env`:

```env
DATABASE_URL=postgresql+asyncpg://quanthire:your_local_password@localhost:5432/quanthire
```

### Option B — Postgres in Docker (DB only)

```bash
docker run -d --name quanthire-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=quanthire postgres:14
```

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quanthire
```

### Option C — Azure Non-Prod Postgres

Only if platform team approves direct access (VPN, firewall, SSL). Use their `DATABASE_URL`. **Confirm whether you may run Alembic against NPD** before migrating.

### Enable pgvector (L3 / QuantChat vectors locally)

If extensions are required for parity, install pgvector on your local Postgres or use a team-provided image. NPD uses pgvector on Azure Flexible Server.

---

## 7. Backend setup (FastAPI)

### 7.1 Create virtual environment

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

### 7.2 Create environment file

Create **`apps/api/.env`** (or **`.env` at repo root** — settings loader checks API directory first).

**L1 — minimal (API only):**

```env
APP_ENV=development
DEBUG=true
AUTH_MODE=none
DEPLOYMENT_TARGET=local
API_HOST=0.0.0.0
API_PORT=8000
```

**L2 — add database and auth:**

```env
DATABASE_URL=postgresql+asyncpg://quanthire:your_local_password@localhost:5432/quanthire
JWT_SECRET_KEY=change-me-to-at-least-32-characters-long
AUTH_MODE=basic
```

**L3 — Azure OpenAI (align with NPD; values from platform team):**

```env
DEPLOYMENT_TARGET=azure-nonprod
VECTOR_STORE=pgvector
MILVUS_ENABLED=false
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://aif-ail-npd-we-01.openai.azure.com/
AZURE_OPENAI_API_KEY=<from secure store>
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://di-ail-npd-we-01.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=<from secure store>
AZURE_STORAGE_CONNECTION_STRING=<optional for blob uploads>
```

Never commit `.env` files with real secrets.

### 7.3 Run migrations (L2+)

With venv active in `apps/api`:

```bash
alembic upgrade head
```

### 7.4 Create a test user (L2, basic auth)

```bash
python scripts/create_test_user.py
# Default: hr.test@malomatia.com / ChangeMe123!
```

### 7.5 Set PYTHONPATH and start API

From **repository root** (adjust path separators on Windows):

**PowerShell:**

```powershell
$env:PYTHONPATH = "apps;apps/api;apps/agents;apps/agents/agents;apps/quantchat"
cd apps\api
.\.venv\Scripts\Activate.ps1
python run.py
```

**bash:**

```bash
export PYTHONPATH="apps:apps/api:apps/agents:apps/agents/agents:apps/quantchat"
cd apps/api && source .venv/bin/activate && python run.py
```

**Success indicators:**

- Console shows Uvicorn listening on `0.0.0.0:8000`  
- Open http://localhost:8000/docs (if Swagger enabled)  
- http://localhost:8000/healthz returns OK  

---

## 8. Frontend setup (Next.js + BFF)

### 8.1 Install dependencies

```bash
cd apps/web
cp .env.example .env.local
```

Edit **`apps/web/.env.local`:**

```env
BFF_BACKEND_URL=http://localhost:8000
```

For Entra SSO experiments (optional):

```env
# AZURE_AD_CLIENT_ID=221c7e05-6581-4226-9a08-96a4011dd5ce
# AZURE_AD_TENANT_ID=68bae048-c310-4ec2-934f-cbc2588f30fe
```

(SSO also requires API `AUTH_MODE=entra` and configured secrets.)

### 8.2 Install and run

```bash
npm ci --legacy-peer-deps
npm run dev
```

**Success:** http://localhost:3000 loads the application.

---

## 9. Verify the installation

### Checklist

| # | Check | How |
|---|-------|-----|
| 1 | API health | http://localhost:8000/healthz |
| 2 | BFF health | http://localhost:3000/api/health |
| 3 | Login (L2) | Sign in with test user at http://localhost:3000/login |
| 4 | Dashboard | `/dashboard` loads after login |
| 5 | Jobs list | `/dashboard/jobs` |
| 6 | QuantChat (L3) | `/dashboard/chat` — send a message |
| 7 | JD generate (L3) | Jobs → generate JD (may take minutes) |

### Common smoke commands

```bash
curl -s http://localhost:8000/healthz
curl -s http://localhost:3000/api/health
```

---

## 10. Optional configurations

### Frontend-only (UI against NPD API)

If NPD API is reachable from your network:

```env
# apps/web/.env.local
BFF_BACKEND_URL=https://<npd-api-host-as-approved-by-platform>
```

Run only `npm run dev`. Confirm CORS and auth with your team.

### Entra SSO locally

1. API: `AUTH_MODE=entra`, `azure_ad_client_id`, `azure_ad_tenant_id`, client secret.  
2. Web: MSAL client/tenant in `.env.local`.  
3. Entra app registration redirect URI: `http://localhost:3000`.  
4. User must have app role on **AIL-QUANTHIRE-NPD**.

### IDE (Cursor / VS Code)

Open **repo root** as workspace. Recommended Quick Open docs: `LOCAL-SETUP-GUIDE`, `CONSOLIDATED-TECHNICAL`.

---

## 11. Daily developer workflow

| Terminal | Location | Command |
|----------|----------|---------|
| 1 | `apps/api` (venv + PYTHONPATH) | `python run.py` |
| 2 | `apps/web` | `npm run dev` |

Browser: **http://localhost:3000**

After pulling git changes:

```bash
# Backend deps (if requirements changed)
pip install -r requirements.txt

# Frontend deps
cd apps/web && npm ci --legacy-peer-deps

# DB schema
cd apps/api && alembic upgrade head
```

---

## 12. Run tests

From **repo root** (matches CI):

**bash:**

```bash
export JWT_SECRET_KEY="test-jwt-secret-key-with-32-chars-minimum"
export APP_ENV=testing
export AUTH_MODE=none
export PYTHONPATH=apps:apps/api:apps/agents:apps/agents/agents:apps/quantchat
pytest tests/unit -q
```

**PowerShell:**

```powershell
$env:JWT_SECRET_KEY="test-jwt-secret-key-with-32-chars-minimum"
$env:APP_ENV="testing"
$env:AUTH_MODE="none"
$env:PYTHONPATH="apps;apps/api;apps/agents;apps/agents/agents;apps/quantchat"
pytest tests/unit -q
```

Frontend typecheck/build (CI):

```bash
cd apps/web && npx tsc --noEmit && npm run build
```

---

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `502` / Backend unavailable | API not running | Start `python run.py`; check `BFF_BACKEND_URL` |
| `401 Unauthorized` | Auth enabled, no login | `AUTH_MODE=none` for L1, or use test user |
| DB connection error | Postgres down / wrong URL | Verify `DATABASE_URL`; start Postgres |
| `ModuleNotFoundError: agents` | Missing PYTHONPATH | Set PYTHONPATH from repo root (§7.5) |
| JD / chat / match `503` | LLM not configured | Complete L3 Azure env vars |
| Upload timeout | Long DI/LLM | Expected for large PDFs; keep BFF running |
| `npm ci` fails | Node version | Use Node **20** |
| Port 3000 in use | Other app | Stop other process or change Next port |
| CORS errors pointing at :8000 | Bypassing BFF | Use localhost:**3000** only |

---

## 14. When to use Docker

| Scenario | Approach |
|----------|----------|
| Daily coding | **This guide** (native) |
| Local DB only | Small `postgres:14` container (§6B) |
| Release to NPD | `Dockerfile.backend` / `Dockerfile.frontend` + [nonprod-deploy-handover-guide.md](./nonprod-deploy-handover-guide.md) |
| Full stack in Docker on laptop | Not recommended (resource heavy) |

---

## 15. Getting help

When contacting the previous team or platform support, include:

1. Setup level (L1 / L2 / L3)  
2. OS (Windows / macOS / Linux)  
3. Exact command run  
4. Last 30 lines of API or web terminal log  
5. Whether using local DB or Azure NPD services  

**Reference docs:**

- [session-2-code-walkthrough-complete.md](./session-2-code-walkthrough-complete.md) — repo layout and config hierarchy  
- [agentic-systems-quick-reference.md](./agentic-systems-quick-reference.md) — code paths for AI features  

---

*End of local setup guide.*
