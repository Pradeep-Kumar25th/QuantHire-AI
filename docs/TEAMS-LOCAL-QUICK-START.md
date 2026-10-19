# QuantHire AI — Local quick start (1 page)

**For:** Team unzipping the handover package from Teams  
**Full guide:** `docs\RUN-LOCALLY-STEP-BY-STEP-HANDOVER.md`  
**Use app without install:** https://quanthire-npd.malomatia.com (TAMM / Entra **AIL-QUANTHIRE-NPD**)

---

## Prerequisites

- **Node.js 20** · **Python 3.11** · **Docker Desktop** (for Postgres only)  
- Folder e.g. `D:\QuantHire AI` (unzipped)

---

## 5-minute checklist

| # | Action |
|---|--------|
| 1 | Unzip; **delete** any `.env` from sender — create your own (step 2) |
| 2 | Create **`D:\QuantHire AI\.env`** with at least: `AUTH_MODE=none`, `DEBUG=true`, `MILVUS_ENABLED=false`, `MILVUS_AUTO_LOAD=false` |
| 3 | For login + DB add: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quanthire`, `AUTH_MODE=basic`, `JWT_SECRET_KEY=` (32+ chars) |
| 4 | Create **`apps\web\.env.local`**: `BFF_BACKEND_URL=http://localhost:8000` |
| 5 | Start DB: `docker run -d --name quanthire-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=quanthire pgvector/pgvector:pg16` |
| 6 | **Terminal 1 (API):** see box below |
| 7 | **Terminal 2 (web):** `cd apps\web` → `npm ci --legacy-peer-deps` → `npm run dev` |
| 8 | Browser: **http://localhost:3000** · Login: `hr.test@malomatia.com` / `ChangeMe123!` (after step 6 migrations + create user) |

---

## Terminal 1 — API (PowerShell)

```powershell
cd "D:\QuantHire AI\apps\api"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python scripts\create_test_user.py

cd "D:\QuantHire AI"
$env:PYTHONPATH = "apps;apps\api;apps\agents;apps\agents\agents;apps\quantchat"
cd apps\api
.\.venv\Scripts\Activate.ps1
python run.py
```

---

## Terminal 2 — Web

```powershell
cd "D:\QuantHire AI\apps\web"
npm ci --legacy-peer-deps
npm run dev
```

---

## Health checks

- http://localhost:8000/healthz  
- http://localhost:3000/api/health  

---

## AI features (JD, resume, QuantChat)

Add Azure OpenAI + Document Intelligence keys to root `.env` — see full guide **Part C (L3)**. Request secrets via platform team (not in zip).

---

## Stuck?

Open **`docs\RUN-LOCALLY-STEP-BY-STEP-HANDOVER.md`** → **Part K Troubleshooting**.  
Reply with step number + terminal error text.
