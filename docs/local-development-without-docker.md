# QuantHire AI — Local development without Docker

> **Handover deliverable:** The detailed local setup guide for Malomatia is **[LOCAL-SETUP-GUIDE.md](./LOCAL-SETUP-GUIDE.md)**. This file remains a concise reference; prefer the guide for onboarding.

**Audience:** Engineers running the app on a laptop (e.g. continuing QuantHire development).  
**Purpose:** Start **frontend + backend natively** — no full application Docker images.

Production images (`Dockerfile.backend`, `Dockerfile.frontend`) are for **ACR/Kubernetes**. They bundle a large Python stack (agents, RAG, PDF/OCR) and a production Next build, which often exhausts RAM when you build and run **both** containers locally. Day-to-day dev uses **Node 20 + Python 3.11** only.

---

## 1. What runs locally

```text
Browser  →  Next.js (port 3000)  →  BFF /api/*  →  FastAPI (port 8000)
                                                      │
                                    agents + quantchat (same process)
                                                      │
                                    PostgreSQL (+ pgvector)
                                    Azure OpenAI / Document Intelligence (for AI features)
```

| Component | Path | How to start |
|-----------|------|----------------|
| Frontend + BFF | `apps/web` | `npm run dev` |
| API | `apps/api` | `python run.py` |
| Agents / QuantChat | `apps/agents`, `apps/quantchat` | Imported by API (`PYTHONPATH`) — no separate server |

The browser should use **`http://localhost:3000`**. API calls go to **`/api/v1/...`** on Next, which proxies to the backend using **`BFF_BACKEND_URL`**.

---

## 2. Prerequisites

| Tool | Version |
|------|---------|
| Node.js | **20** (matches CI) |
| Python | **3.11** |
| PostgreSQL | **14+** (local install, or optional small Postgres container — see §5) |
| Git | Clone from your Azure Dev repo |

**Optional (for full AI parity with Non-Prod):**

- Azure OpenAI endpoint, API key, chat + embedding deployments  
- Azure Document Intelligence (resume scans / complex PDFs)  
- Azure Blob (raw resume storage on NPD; some dev paths continue if blob is skipped)  
- VPN / firewall rules if using **NPD Postgres** or **NPD API** from your laptop  

**Not required for current NPD architecture:** Milvus (vectors use **pgvector** in Postgres).

---

## 3. Choose your setup level

| Level | Goal | DB | AI / Azure |
|-------|------|-----|------------|
| **L1 — Wire-up** | UI loads, BFF reaches API | Optional | `AUTH_MODE=none`, LLM optional |
| **L2 — Product data** | Jobs, candidates, login | Local or NPD Postgres | As needed |
| **L3 — Full agents** | JD, resume, QuantChat, matching | Postgres + pgvector | Azure OpenAI + DI (mirror NPD env) |

Start at **L1**, then add **L2** and **L3** env vars.

---

## 4. Backend (FastAPI)

### 4.1 One-time setup

From the **repository root** (adjust paths if your clone layout differs):

**macOS / Linux**

```bash
cd apps/api
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.linux.txt
```

**Windows (PowerShell)**

```powershell
cd apps\api
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

Create **`apps/api/.env`** (or a **`.env` at repo root** — `Settings` loads `.env` from the API working directory; scripts also load repo root `.env` when present).

### 4.2 Environment variables (backend)

**L1 — minimal (API up, auth off)**

```env
APP_ENV=development
DEBUG=true
AUTH_MODE=none
DEPLOYMENT_TARGET=local
API_HOST=0.0.0.0
API_PORT=8000
MILVUS_ENABLED=false
MILVUS_AUTO_LOAD=false
```

**L2 — with database**

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quanthire
# Or sync URL if your tooling expects it:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/quanthire
JWT_SECRET_KEY=change-me-to-at-least-32-characters-long
AUTH_MODE=basic
```

Run migrations:

```bash
cd apps/api
source .venv/bin/activate   # or Windows activate
alembic upgrade head
```

Create a login user (basic auth):

```bash
cd apps/api
python scripts/create_test_user.py
# Default: hr.test@malomatia.com / ChangeMe123!  (override with --email --password)
```

**L3 — Non-Prod parity (agents + RAG on Azure)**

Use the env template your team provides (often aligned with K8s ConfigMap/Secrets). Typical keys:

```env
DEPLOYMENT_TARGET=azure-nonprod
APP_ENV=nonprod
AUTH_MODE=basic

VECTOR_STORE=pgvector
MILVUS_ENABLED=false

LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://<your-openai-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<secret>
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

POSTGRES_HOST=<host>
POSTGRES_DB=quanthire_ai
POSTGRES_USER=<user>
POSTGRES_PASSWORD=<secret>
POSTGRES_PORT=5432
POSTGRES_SSLMODE=require
# Or a single DATABASE_URL your team standardizes on

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<di>.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_API_KEY=<secret>

AZURE_STORAGE_CONNECTION_STRING=<optional for blob uploads>
```

Do **not** commit secrets. Copy values from your team’s secure store / NPD secret documentation.

See also repo root **`.env.example`** (Vertex/local alternate) and **`docs/session-2-code-walkthrough-complete.md`** §3.4.

### 4.3 PYTHONPATH and start the server

From **repo root**, set `PYTHONPATH` so agents and QuantChat import correctly:

**macOS / Linux**

```bash
export PYTHONPATH="apps:apps/api:apps/agents:apps/agents/agents:apps/quantchat"
cd apps/api
source .venv/bin/activate
python run.py
```

**Windows (PowerShell)**

```powershell
$env:PYTHONPATH = "apps;apps/api;apps/agents;apps/agents/agents;apps/quantchat"
cd apps\api
.\.venv\Scripts\Activate.ps1
python run.py
```

Alternative:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Verify:** open `http://localhost:8000/docs` (Swagger) or your health route.

---

## 5. Database options (without app Docker)

### Option A — Local PostgreSQL (recommended for dev)

Install Postgres 14+ locally, create database:

```sql
CREATE DATABASE quanthire;
```

Use `DATABASE_URL` pointing at `localhost` (see §4.2).

### Option B — Postgres only in Docker (small image)

If you want an isolated DB but not the full QuantHire images:

```bash
docker run -d --name quanthire-pg \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=quanthire \
  postgres:14
```

Then `DATABASE_URL=...@localhost:5432/quanthire`. Still run **web + API natively**.

### Option C — Azure Non-Prod Postgres

Point `POSTGRES_*` / `DATABASE_URL` at NPD. Requires network access (VPN), SSL, and credentials from your platform team. Run `alembic upgrade head` only if your team expects local migration against that DB (often **not** — confirm first).

---

## 6. Frontend (Next.js + BFF)

### 6.1 One-time setup

```bash
cd apps/web
cp .env.example .env.local
```

**`.env.local`** (required):

```env
BFF_BACKEND_URL=http://localhost:8000
```

For local basic-auth testing (optional):

```env
# AUTH_MODE is primarily an API setting; frontend may use Entra vars from .env.example for SSO experiments.
```

Install and run:

```bash
npm ci --legacy-peer-deps
npm run dev
```

**Verify:** `http://localhost:3000` — login (if `AUTH_MODE=basic`) and open dashboard routes.

Long AI calls (JD generate, resume upload, job-matching stream) rely on BFF timeouts in `apps/web/src/app/api/[...path]/route.ts` (~620s). Keep backend running locally; do not point the browser directly at `:8000` for normal use.

---

## 7. Optional: frontend only (no local Python)

If NPD API is reachable from your machine:

```env
# apps/web/.env.local
BFF_BACKEND_URL=https://<npd-api-host-or-gateway>
```

Run only `npm run dev`. Use for UI work; confirm CORS/auth/BFF rules with your team.

---

## 8. Daily workflow (cheat sheet)

| Terminal | Directory | Command |
|----------|-----------|---------|
| 1 | `apps/api` (venv active, `PYTHONPATH` set) | `python run.py` |
| 2 | `apps/web` | `npm run dev` |

Browser: **http://localhost:3000**

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| `502` / Backend unavailable | API not running or wrong URL | Start API; check `BFF_BACKEND_URL=http://localhost:8000` |
| `401` on API | Auth enforced | Set `AUTH_MODE=none` for L1, or login with test user for `basic` |
| DB connection errors | Postgres down / wrong URL | Check `DATABASE_URL`; start Postgres; run `alembic upgrade head` |
| Import errors for `agents` / `quantchat` | Missing `PYTHONPATH` | Set path as in §4.3 from repo root layout |
| Resume/JD/Chat `503` | QueryRouter / LLM not configured | Add Azure OpenAI (or valid `LLM_PROVIDER` + keys) for L3 |
| Upload timeout | Slow DI/LLM | Normal for large PDFs; ensure BFF timeout paths include your route |
| `pip install` fails on Windows | Heavy native deps | Use Python 3.11 x64; try `requirements.txt`; install Visual C++ build tools if needed |

---

## 10. Tests (same as CI, no Docker)

From repo root:

```bash
export JWT_SECRET_KEY="test-jwt-secret-key-with-32-chars-minimum"
export APP_ENV=testing
export AUTH_MODE=none
export PYTHONPATH=apps:apps/api:apps/agents:apps/agents/agents:apps/quantchat
pytest tests/unit -q
```

---

## 11. When to use Docker anyway

| Use case | Approach |
|----------|----------|
| Local dev | **Native** web + API (this guide) |
| Local DB only | Small **`postgres:14`** container (§5B) |
| Release / parity | Build from repo root: `Dockerfile.backend`, `Dockerfile.frontend` — prefer **CI or a larger VM** if local build runs out of memory |
| Deployed NPD | Images in ACR; manifest under `infra/kubernetes/nonprod/` |

---

## 12. Related docs

- **`docs/session-2-code-walkthrough-complete.md`** — §4.2 local development, BFF, env hierarchy  
- **`docs/agentic-systems-quick-reference.md`** — code tour for resume / JD / QuantChat / matching  
- Repo **`README.md`** — Non-Prod URL and image tag reference  

---

**Summary:** Run **`python run.py`** in `apps/api` and **`npm run dev`** in `apps/web` with **`BFF_BACKEND_URL=http://localhost:8000`**. Add Postgres and Azure env when you need persistence and AI features. Skip full application Docker on a constrained laptop.
