# QuantHire AI — technical handover to Malomatia (consolidated)

**Purpose:** Single reply to Hazim / Shraddha: what is delivered, how to **use the app today**, how to **run the repo locally**, and what must be requested separately (access, secrets, BRD).

**Last updated:** Handover week (Oct 2026)  
**Non-Prod (live):** https://quanthire-npd.malomatia.com  
**Code:** Azure DevOps repo (provided by Malomatia) + GitHub mirror `Pradeep-Kumar25th/QuantHire-AI`  

---

## 1. What to send “instantly” (checklist for Pradeep → team)

| # | Item | Where it lives | Send how |
|---|------|----------------|----------|
| 1 | **Three-document pack index** | `docs/HANDOVER-THREE-DOCUMENT-PACK.md` | **Send Hazim/Shraddha this + the three files below** |
| 2 | **Consolidated technical documentation** | `docs/CONSOLIDATED-TECHNICAL-DOCUMENTATION.md` | Architecture, stack, Azure, API, deploy |
| 3 | **Local setup guide** | `docs/LOCAL-SETUP-GUIDE.md` | **Primary doc for “repository up and running locally”** |
| 4 | **BRD** | `docs/QUANTHIRE-BUSINESS-REQUIREMENTS-DOCUMENT-BRD.md` | Business requirements (Hazim’s BRD ask) |
| 5 | **This consolidated handover** | `docs/TECHNICAL-HANDOVER-TO-MALOMATIA.md` | Email checklist + template |
| 6 | **KT documentation index** | `docs/KT-MASTER-INDEX.md` or root `OPEN-KT-DOCS-IN-CURSOR.md` | Session 1–3 deep dives |
| 7 | **Non-Prod deploy runbook** | `docs/nonprod-deploy-handover-guide.md` | For releases to AKS/ACR |
| 8 | **Environment templates** | `.env.example`, `apps/web/.env.example` | No secrets — variable names only |
| 9 | **K8s config (Non-Prod)** | `infra/kubernetes/nonprod/quanthire.yaml` | Shows URLs, Azure resource names, image tags |

**Do not email or commit:** database passwords, `JWT_SECRET_KEY`, Azure OpenAI keys, storage connection strings, Entra client secret. Those are already on **AKS secrets** for Non-Prod; for local dev, platform team must grant access or share via **Key Vault / TAMM**.

---

## 2. Business Requirements Document (BRD) — Hazim’s request

**Deliverable:** [`docs/QUANTHIRE-BUSINESS-REQUIREMENTS-DOCUMENT-BRD.md`](./QUANTHIRE-BUSINESS-REQUIREMENTS-DOCUMENT-BRD.md)

Export to PDF/Word for formal PMO submission if required. Malomatia product owner may sign the approval section in the BRD.

---

## 3. Fastest path: use the application **without** local setup

The team can **start using QuantHire today** on Non-Prod if they have **login access**:

| Step | Action |
|------|--------|
| 1 | Open https://quanthire-npd.malomatia.com |
| 2 | Sign in (Entra SSO when enabled, or basic auth per current NPD `AUTH_MODE` in cluster) |
| 3 | Use Recruiter flows: Jobs (JD), Candidates (resume), Job matching, QuantChat |

**Access:** Each user needs an **Entra app role** on enterprise app **`AIL-QUANTHIRE-NPD`** (e.g. **RECRUITER**). Raise **TAMM** with registration name, client ID, role, and user email — see KT email template from handover (client ID `221c7e05-6581-4226-9a08-96a4011dd5ce`).

**No local repo required** for UAT, demos, or recruiter training.

---

## 4. Local repository setup (Shraddha’s ask)

**Start here:** [`docs/LOCAL-SETUP-GUIDE.md`](./LOCAL-SETUP-GUIDE.md)

Summary for the team:

1. **Clone** from Azure DevOps (branch **`main`** or agreed default).
2. Install **Node 20**, **Python 3.11**, **PostgreSQL 14+** (or small Postgres container).
3. **Backend:** `apps/api` — venv, `pip install -r requirements.linux.txt` (Linux) or `requirements.txt` (Windows), set `DATABASE_URL`, `PYTHONPATH`, run `alembic upgrade head`, `python run.py`.
4. **Frontend:** `apps/web` — copy `.env.example` → `.env.local`, set `BFF_BACKEND_URL=http://localhost:8000`, `npm ci --legacy-peer-deps`, `npm run dev`.
5. Browser: **http://localhost:3000** (API via BFF, not direct :8000 from browser for auth cookies).

**Three levels (doc §3):**

- **L1:** UI + API wire-up (`AUTH_MODE=none` optional).
- **L2:** Real DB + login.
- **L3:** Full AI (Azure OpenAI + Document Intelligence like NPD) — needs **Azure keys/VPN** from platform team.

**Optional:** Full Docker images are for **ACR/AKS** only; see [`docs/nonprod-deploy-handover-guide.md`](./nonprod-deploy-handover-guide.md).

**Tests (same as CI):**

```bash
export JWT_SECRET_KEY="test-jwt-secret-key-with-32-chars-minimum"
export APP_ENV=testing AUTH_MODE=none
export PYTHONPATH=apps:apps/api:apps/agents:apps/agents/agents:apps/quantchat
pytest tests/unit -q
```

---

## 5. Azure DevOps: ensure the repo contains these paths

After upload, confirm the ADO repository includes at minimum:

```text
docs/KT-MASTER-INDEX.md
docs/LOCAL-SETUP-GUIDE.md
docs/CONSOLIDATED-TECHNICAL-DOCUMENTATION.md
docs/QUANTHIRE-BUSINESS-REQUIREMENTS-DOCUMENT-BRD.md
docs/HANDOVER-THREE-DOCUMENT-PACK.md
docs/nonprod-deploy-handover-guide.md
docs/TECHNICAL-HANDOVER-TO-MALOMATIA.md
OPEN-KT-DOCS-IN-CURSOR.md
.env.example
apps/web/.env.example
infra/kubernetes/nonprod/quanthire.yaml
Dockerfile.backend
Dockerfile.frontend
README.md
```

If KT docs were only on GitHub, **sync or copy** the `docs/` folder from `main` into Azure DevOps so Shraddha’s team has one clone URL.

---

## 6. Access & credentials the team must request (not in Git)

| Need | Who grants | Notes |
|------|------------|--------|
| **QuantHire Non-Prod login** | Identity / TAMM | App **AIL-QUANTHIRE-NPD**, role **RECRUITER** (or Admin) |
| **Azure DevOps repo** | Already provided | Read/write per project policy |
| **AKS / kubectl / ACR push** | AI Hub platform | Deploy guide; Jump VM |
| **NPD Postgres** (local connect) | DBA / platform | Usually VPN + firewall; prefer local Postgres for dev |
| **Azure OpenAI + Document Intelligence** | AI Hub | For L3 local parity |
| **Entra client secret** | Identity | Backend only; on cluster secret `quanthire-entra-secret` |

Reference secret **names** (values on cluster only): `infra/kubernetes/nonprod/quanthire-secrets.yaml`.

---

## 7. KT session materials (already prepared)

All listed in [`docs/KT-MASTER-INDEX.md`](./KT-MASTER-INDEX.md):

- **Session 1:** Architecture, Azure resources, presenter pack/script  
- **Session 2:** Code walkthrough, agentic quick reference (line numbers)  
- **Session 3:** AI components, observability, quick reference + presenter script  

---

## 8. Support after handover

| Topic | First doc / action |
|-------|---------------------|
| Local won’t start | `docs/LOCAL-SETUP-GUIDE.md` → § troubleshooting |
| Deploy NPD | `docs/nonprod-deploy-handover-guide.md` |
| Code navigation | `docs/session-2-code-walkthrough-complete.md` |
| AI / agents | `docs/session-3-quick-reference.md` |
| Production / staging | `.github/workflows/deploy-staging.yml`, `deploy-production.yml` (reference; NPD uses raw YAML) |

---

## 9. Suggested email body (copy to Hazim + Shraddha)

**Subject:** QuantHire AI — consolidated technical documentation + local setup + BRD

Hi Hazim, Shraddha,

Please find below the consolidated technical handover for QuantHire AI.

**1. Use the application now (no local setup)**  
Non-Prod: https://quanthire-npd.malomatia.com  
User access: TAMM request for Entra app **AIL-QUANTHIRE-NPD**, app role **RECRUITER** (or as needed).

**2. Consolidated technical documentation**  
**docs/CONSOLIDATED-TECHNICAL-DOCUMENTATION.md**

**3. Run the repository locally**  
**docs/LOCAL-SETUP-GUIDE.md** (Node 20, Python 3.11, PostgreSQL; Azure keys for full AI).

**4. Business Requirements Document (BRD)**  
**docs/QUANTHIRE-BUSINESS-REQUIREMENTS-DOCUMENT-BRD.md** (export to PDF if PMO requires).

**5. Pack index (all three)**  
**docs/HANDOVER-THREE-DOCUMENT-PACK.md**

**6. Additional KT & deploy**  
**docs/KT-MASTER-INDEX.md**, **docs/nonprod-deploy-handover-guide.md**, **OPEN-KT-DOCS-IN-CURSOR.md**

**7. Code**  
Frontend and backend are in the Azure DevOps repository you provided; branch **main** includes the documentation paths above.

Secrets (DB, API keys, JWT) are configured on Azure Non-Prod Kubernetes and are not included in email or Git. For local development against Azure services, please use the usual platform / TAMM process.

If anything blocks local setup after following the guide, reply with the step number and error log and we can troubleshoot.

Regards,  
Pradeep

---

*End of consolidated technical handover.*
