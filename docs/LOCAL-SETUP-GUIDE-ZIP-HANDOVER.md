# QuantHire AI — Run locally from the ZIP handover (step-by-step)

**Audience:** Malomatia team who received the **QuantHire AI** folder via Teams (zip)  
**Platform:** Windows laptop (primary); notes for macOS/Linux where different  
**Time (first setup):** about 1–3 hours depending on level (see §2)  
**Use Non-Prod without local setup:** https://quanthire-npd.malomatia.com (Entra/TAMM access)

---

## Document map

| If you need… | Section |
|--------------|---------|
| What was in the zip | §1 |
| Choose how much to install (L1/L2/L3) | §2 |
| Install software | §3 |
| Unzip and clean the folder | §4 |
| Configure `.env` (what to change) | §5 |
| Start database | §6 |
| Start backend (API) | §7 |
| Start frontend (UI) | §8 |
| Open the app and test | §9 |
| Optional: Docker Compose (if files present) | §10 |
| Daily workflow | §11 |
| Troubleshooting | §12 |
| Folder structure explained | §13 |

---

## 1. What you received

The zip is the **full project root**, for example:

```text
D:\QuantHire AI\          ← unzip here (path may differ on your PC)
├── apps\                 ← main application code (web + api + agents)
├── docs\                 ← handover .md guides (LOCAL-SETUP-GUIDE, BRD, etc.)
├── infra\                ← Kubernetes / deploy manifests (for NPD, not required locally)
├── tests\                ← unit tests
├── Dockerfile.backend
├── Dockerfile.frontend
├── .env.example          ← template — copy to .env
├── docker-compose*.yml   ← may be present (optional local Docker stack)
├── venv\                 ← may be in zip — do NOT rely on it (§4)
├── node_modules\         ← may be in zip — recreate on your machine (§4)
└── …
```

**Important:** The zip is for **development on your laptop**. Production runs on **Azure AKS** (Non-Prod URL above).

---

## 2. Choose your setup level

| Level | Goal | You will configure |
|-------|------|-------------------|
| **L1 — Smoke test** | API + UI load; BFF talks to API | `.env` with auth off, Milvus off; no database |
| **L2 — Product UI** | Login, jobs, candidates, dashboard | L1 + **PostgreSQL** + migrations + test user |
| **L3 — Full AI** | JD generate, resume parse, QuantChat, matching | L2 + **Azure OpenAI** (+ Document Intelligence keys from platform team) |

**Recommendation:** Do **L1 → L2 → L3**. Do not skip L1 (confirms Node/Python/BFF before DB and Azure).

---

## 3. Install prerequisites (once per laptop)

Install **before** unzipping or right after:

| Software | Version | Download / check |
|----------|---------|------------------|
| **Node.js** | **20.x LTS** | https://nodejs.org — then `node -v` |
| **Python** | **3.11.x** (64-bit) | https://www.python.org — tick “Add to PATH” |
| **Git** | Optional for zip handover | Useful if you also use Azure DevOps |
| **Docker Desktop** | Optional | Only if you use §10 (Postgres or full compose) |
| **PostgreSQL + pgvector** | L2+ | Easiest: Docker image in §6 |

**Windows:** If `pip install` fails, install **Visual Studio Build Tools** (C++ workload).

---

## 4. Unzip and prepare the folder

### 4.1 Unzip

1. Save the Teams zip (e.g. `QuantHire AI.zip`).
2. Extract to a short path, for example:  
   **`D:\QuantHire AI`**  
   (Avoid very long paths under OneDrive sync during first setup.)

3. Open **PowerShell** or **Command Prompt**:

```bat
cd /d "D:\QuantHire AI"
dir apps\web apps\api Dockerfile.backend
```

If those exist, you are in the correct root.

### 4.2 Do not use the sender’s virtual environments (critical)

The zip may contain:

- **`venv`** or **`.venv`** (Python from Pradeep’s machine)  
- **`node_modules`** (Node packages tied to that machine/OS)

**On your laptop you must recreate them:**

| In zip | Action on your PC |
|--------|-------------------|
| `venv` / `.venv` | **Ignore or delete** — create new venv in §7 |
| `node_modules` at root or under `apps\web` | **Delete `apps\web\node_modules`** if present — run `npm ci` in §8 |

Using bundled `venv`/`node_modules` often causes **import errors, wrong Python version, or native module crashes**.

### 4.3 Documentation inside the zip

Handover markdown is under:

```text
D:\QuantHire AI\docs\
```

Key files:

- **`LOCAL-SETUP-GUIDE.md`** — same flow as this doc (repo clone variant)  
- **`CONSOLIDATED-TECHNICAL-DOCUMENTATION.md`**  
- **`QUANTHIRE-BUSINESS-REQUIREMENTS-DOCUMENT-BRD.md`**  
- **`nonprod-deploy-handover-guide.md`** — deploy to Azure (not local)

---

## 5. Configure environment (what to change)

The API reads **`.env` at the project root** first (`apps\api\app\main.py`), then `apps\api\.env` if root is missing.

### 5.1 Create root `.env`

```bat
cd /d "D:\QuantHire AI"
copy .env.example .env
notepad .env
```

### 5.2 L1 — minimum (paste and save)

Use this block to **start the API without Postgres** and **without Milvus** (avoids hanging on port 19530):

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

Leave Vertex/GCP keys empty for L1 unless you intentionally use Google AI locally.

### 5.3 L2 — add database and login

**Append** to the same `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quanthire
JWT_SECRET_KEY=local-dev-jwt-secret-at-least-32-characters-long
AUTH_MODE=basic
```

Change `postgres:postgres` if you used different credentials in §6.

### 5.4 L3 — Malomatia Non-Prod parity (Azure AI)

Get secrets from **platform / Key Vault / your lead** — never commit real keys.

**Append** (example names — use values your team provides):

```env
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://aif-ail-npd-we-01.openai.azure.com/
AZURE_OPENAI_API_KEY=<paste-secret-here>
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://di-ail-npd-we-01.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=<paste-secret-here>

# Optional: resume files to Azure Blob like NPD
# STORAGE_TYPE=azure_blob
# AZURE_STORAGE_CONNECTION_STRING=<paste-secret-here>
```

**Note:** Root `.env.example` may show **Vertex AI** defaults. For Malomatia NPD parity, use **`LLM_PROVIDER=azure_openai`** as above.

### 5.5 Frontend environment (separate file)

```bat
cd /d "D:\QuantHire AI\apps\web"
copy .env.example .env.local
notepad .env.local
```

**Required:**

```env
BFF_BACKEND_URL=http://localhost:8000
```

Do **not** add `/api` at the end. Save and close.

---

## 6. Start PostgreSQL (L2 and L3 only)

### Option A — Docker (recommended)

Install Docker Desktop, then:

```powershell
docker run -d --name quanthire-pg -p 5432:5432 `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=quanthire `
  pgvector/pgvector:pg16
```

Verify:

```powershell
docker ps
```

### Option B — Local PostgreSQL install

Install PostgreSQL 14+ and **pgvector** extension, create database `quanthire`, set `DATABASE_URL` in `.env` accordingly.

### Skip this section for L1 only

---

## 7. Backend (API) — step by step

### 7.1 One-time: Python virtual environment

```powershell
cd "D:\QuantHire AI\apps\api"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 7.2 One-time: database migrations (L2+)

With venv still active and **`D:\QuantHire AI\.env`** containing `DATABASE_URL`:

```powershell
cd "D:\QuantHire AI\apps\api"
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

Expect migrations to create tables and `vector` extension (requires pgvector in §6).

### 7.3 One-time: create login user (L2+, basic auth)

```powershell
cd "D:\QuantHire AI\apps\api"
.\.venv\Scripts\Activate.ps1
python scripts\create_test_user.py
```

Default credentials:

| Field | Value |
|-------|--------|
| Email | `hr.test@malomatia.com` |
| Password | `ChangeMe123!` |

### 7.4 Every time: start the API

Open **PowerShell window #1**:

```powershell
cd "D:\QuantHire AI"
$env:PYTHONPATH = "apps;apps\api;apps\agents;apps\agents\agents;apps\quantchat"
cd apps\api
.\.venv\Scripts\Activate.ps1
python run.py
```

**Success signs:**

- Message that Uvicorn is listening on **port 8000**  
- Open browser: http://localhost:8000/healthz → JSON with `"status":"healthy"`

Leave this window **open**.

---

## 8. Frontend (UI + BFF) — step by step

Open **PowerShell window #2**:

```powershell
cd "D:\QuantHire AI\apps\web"
```

If `node_modules` came from the zip, remove and reinstall:

```powershell
Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
npm ci --legacy-peer-deps
npm run dev
```

**Success signs:**

- `ready started server on 0.0.0.0:3000` (or similar)  
- http://localhost:3000/api/health returns JSON (proxied from API)

Leave this window **open**.

---

## 9. Use the application on your laptop

### 9.1 URLs

| URL | Purpose |
|-----|---------|
| **http://localhost:3000** | **Main app** — always use this in the browser |
| http://localhost:3000/login | Login (L2+, basic auth) |
| http://localhost:3000/dashboard | After login |
| http://localhost:8000/docs | API Swagger (optional) |
| http://localhost:8000/healthz | API alive (L1) |

### 9.2 Verification checklist

| Step | Action | Expected |
|------|--------|----------|
| 1 | http://localhost:8000/healthz | `healthy` |
| 2 | http://localhost:3000/api/health | `healthy` via BFF |
| 3 | L2: login at /login | Dashboard loads |
| 4 | L3: Generate JD / upload resume / QuantChat | Completes (may take minutes) |

### 9.3 Use hosted Non-Prod instead

If you only need to **use** the product (not develop code):

- URL: https://quanthire-npd.malomatia.com  
- Access: TAMM for **AIL-QUANTHIRE-NPD**, role **RECRUITER**  
- **No zip setup required**

---

## 10. Optional: run with Docker Compose (if your zip includes compose files)

Your folder may include files such as:

- `docker-compose.dev.yml`  
- `docker-compose.complete.yml`  
- `docker-compose.milvus.yml`  

**Malomatia Non-Prod uses pgvector in Postgres, not Milvus.** For parity with NPD, prefer **§6–§8 (native)** with `MILVUS_ENABLED=false`.

If your team still uses legacy compose for local experiments:

1. Read comments inside the yml file.  
2. Ensure `.env` matches what compose expects.  
3. From project root:

```powershell
cd "D:\QuantHire AI"
docker compose -f docker-compose.dev.yml up --build
```

**Warning:** Full compose stacks are **heavy** (RAM/disk). If Docker fails or the PC freezes, switch to **native setup (§7–§8)** and only run **Postgres** in Docker (§6).

---

## 11. Daily workflow (two terminals)

| Terminal | Commands |
|----------|----------|
| **1 — API** | `cd "D:\QuantHire AI"` → set `$env:PYTHONPATH` (§7.4) → `cd apps\api` → activate venv → `python run.py` |
| **2 — Web** | `cd "D:\QuantHire AI\apps\web"` → `npm run dev` |

Browser: **http://localhost:3000**

After pulling new code or unzipping an update:

```powershell
cd "D:\QuantHire AI\apps\api"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head

cd "D:\QuantHire AI\apps\web"
npm ci --legacy-peer-deps
```

---

## 12. Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| API stuck starting | Milvus | `MILVUS_ENABLED=false`, `MILVUS_AUTO_LOAD=false` in `.env` |
| `502` on `/api/health` | API not running | Start §7.4; check `BFF_BACKEND_URL=http://localhost:8000` |
| `ModuleNotFoundError: agents` | PYTHONPATH | Set full path in §7.4 |
| DB / alembic errors | Postgres or pgvector | §6 Option A image `pgvector/pgvector:pg16` |
| `401` on pages | Auth on | L1: `AUTH_MODE=none`; L2: login with test user |
| JD/chat/match fail | No Azure keys | Complete L3 §5.4 |
| npm errors | Wrong Node or old node_modules | Node 20; delete `node_modules`, `npm ci --legacy-peer-deps` |
| venv from zip broken | Wrong machine | Delete `apps\api\.venv`, redo §7.1 |
| `/readyz` returns 503 | No DB | Normal for L1; use `/healthz` until L2 |

When asking for help, send: **level (L1/L2/L3)**, **step number from this doc**, and **last 20 lines** from API and web terminals.

---

## 13. Folder structure (what matters for local run)

| Path | Role |
|------|------|
| `apps\web` | Next.js UI + BFF (`npm run dev`) |
| `apps\api` | FastAPI (`python run.py`), Alembic, `scripts\create_test_user.py` |
| `apps\agents` | JD, matching, parsing agents (loaded via PYTHONPATH) |
| `apps\quantchat` | QuantChat RAG (loaded via PYTHONPATH) |
| `docs\` | Handover documentation |
| `infra\` | NPD Kubernetes — not needed for local dev |
| `tests\` | `pytest tests\unit` from repo root with PYTHONPATH |
| `seed-data\` | Optional seed scripts — not required for first login |
| `frontend-instant\` | Legacy/experimental — **use `apps\web` for standard local run** |
| `models\`, `cache\`, `logs\` | Runtime/cache — can be empty on first run |

---

## Quick reference card (print or pin in Teams)

```text
1. Unzip → D:\QuantHire AI
2. Delete/recreate venv & apps\web\node_modules on YOUR machine
3. copy .env.example → .env (L1 block + L2/L3 as needed)
4. apps\web\.env.local → BFF_BACKEND_URL=http://localhost:8000
5. Docker: pgvector Postgres on 5432 (L2+)
6. Terminal 1: PYTHONPATH + apps\api + python run.py
7. Terminal 2: apps\web + npm run dev
8. Browser: http://localhost:3000
```

---

**Handover contact:** After following this guide, email/chat with step number and logs if blocked.

*End of ZIP handover local setup guide.*
