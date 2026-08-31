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


```


## Docker build (from repo root)

```bat
docker build -f Dockerfile.backend --target production -t quanthire-backend:0.1.5 .
docker build -f Dockerfile.frontend --target production -t quanthire-frontend:0.1.5 .
```

## Deploy (NPD)

See `infra/kubernetes/nonprod/quanthire.yaml` and `.github/workflows/deploy-nonprod.yml`.

Post-deploy: `kubectl exec deploy/quanthire-nonprod-api -n quanthire-nonprod -- alembic upgrade head`
