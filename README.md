# QuantHire AI

AI-native hiring platform for Malomatia — JD generation, resume parsing, candidate–job matching, and QuantChat (RAG).

**Non-Prod URL:** https://quanthire-npd.malomatia.com  
**Current image tag:** `0.1.5`

## Repository layout

| Path | Purpose |
|------|---------|
| `apps/api/` | FastAPI backend (auth, CRUD, AI orchestration) |
| `apps/web/` | Next.js frontend + BFF (`/api/*` proxy) |
| `apps/agents/` | LangGraph / CrewAI agents (JD, matching, parsing) |
| `apps/quantchat/` | QuantChat RAG (retrieval, intent, formatting) |
| `infra/kubernetes/nonprod/` | AKS manifests (NPD) |
| `tests/unit/` | Automated unit tests (~320 tests) |
| `scripts/` | Validation and E2E scripts |
| `output/hazim_review/` | Platform sanity review pack |

## Quick start (local validation — no Docker)

```bat
cd /d "d:\QuantHire AI"
set PYTHONPATH=apps;apps\api;apps\agents;apps\agents\agents;apps\quantchat
set JWT_SECRET_KEY=test-jwt-secret-key-with-32-chars-minimum
set APP_ENV=testing
set AUTH_MODE=none
python -m pytest tests\unit -q
python scripts\validate_sso_implementation.py
python scripts\validate_hr_recruiter_sso.py
python apps\api\scripts\validate_all_phases.py
```

Or run all checks: `scripts\validate_hazim_pre_review.cmd`

## Docker build (from repo root)

```bat
docker build -f Dockerfile.backend --target production -t quanthire-backend:0.1.5 .
docker build -f Dockerfile.frontend --target production -t quanthire-frontend:0.1.5 .
```

## Deploy (NPD)

See `infra/kubernetes/nonprod/quanthire.yaml` and `.github/workflows/deploy-nonprod.yml`.

Post-deploy: `kubectl exec deploy/quanthire-nonprod-api -n quanthire-nonprod -- alembic upgrade head`

## Review documentation

Platform sanity review pack for Hazim: [`output/hazim_review/HAZIM_SANITY_REVIEW_PACK.md`](output/hazim_review/HAZIM_SANITY_REVIEW_PACK.md)

## Secrets

Never commit real credentials. Use `infra/kubernetes/nonprod/quanthire-secrets.yaml` placeholders and AKS secrets / Key Vault for NPD.
