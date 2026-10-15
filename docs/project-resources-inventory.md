# QuantHire AI — Project resources inventory

Complete list of **infrastructure, cloud services, data stores, AI/LLM resources, secrets, and major platform dependencies** used or supported by this repository.

**Legend**

| Status | Meaning |
|--------|---------|
| **NPD active** | Used in Malomatia Azure Non-Prod (`DEPLOYMENT_TARGET=azure-nonprod`) |
| **Local dev** | Typical developer laptop / docker setup |
| **Optional** | Supported in code or Helm; not required for NPD |
| **Reference** | Terraform/Helm for staging/prod; not the canonical NPD kubectl path |
| **Legacy** | Retained for migration/local; disabled on NPD |

**Canonical NPD deploy:** `infra/kubernetes/nonprod/quanthire.yaml`  
**Public NPD URL:** https://quanthire-npd.malomatia.com  
**Image registry (NPD):** `crailnpdwe01.azurecr.io`

---

## 1. Azure cloud resources (Non-Prod — active)

| Resource type | Name / identifier | Purpose | Config / manifest reference |
|---------------|-------------------|---------|----------------------------|
| Resource group | `rg-ail-wkload-npd-we-01` | Workload grouping | `.github/workflows/deploy-nonprod.yml`, `apps/api/app/config.py` |
| AKS cluster | `aks-ail-npd-we-01` | Runs web + API containers | Same |
| Azure Container Registry | `crailnpdwe01.azurecr.io` | `quanthire-backend`, `quanthire-frontend` images | `infra/kubernetes/nonprod/quanthire.yaml` |
| PostgreSQL Flexible Server | `psql-ail-npd-we-01.postgres.database.azure.com` | App DB + **pgvector** | ConfigMap `POSTGRES_*`, secret `quanthire-db-secret` |
| PostgreSQL database | `quanthire_ai` | Schema + migrations (Alembic) | ConfigMap |
| Azure OpenAI (AIServices) | `https://aif-ail-npd-we-01.openai.azure.com/` | Chat + embeddings for agents | ConfigMap + `quanthire-aoai-secret` |
| Azure OpenAI deployment | `gpt-4o` (chat) | JD, matching, QuantChat, parsing LLM calls | `AZURE_OPENAI_CHAT_DEPLOYMENT` |
| Azure OpenAI deployment | `text-embedding-3-large` (embeddings) | Vector ingest on NPD (see also local `bge-base` in code paths) | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` |
| Storage account | `dlsailnpdqc01` | Resume/JD file storage | ConfigMap `AZURE_STORAGE_*` |
| Blob container | `quanthire-uploads` | Raw uploads | ConfigMap |
| Blob container | `quanthire-processed` | Processed artifacts | ConfigMap |
| Document Intelligence | `https://di-ail-npd-we-01.cognitiveservices.azure.com/` | PDF/layout extraction for resumes | ConfigMap + `quanthire-di-secret` |
| DI model | `prebuilt-layout` | Layout OCR | ConfigMap |
| Microsoft Entra ID (app reg) | Client ID `221c7e05-6581-4226-9a08-96a4011dd5ce` | SSO (prepared) | ConfigMap; secret `quanthire-entra-secret` |
| Entra tenant | `68bae048-c310-4ec2-934f-cbc2588f30fe` | Directory | ConfigMap |
| Subscription ID (documented) | `6c1005fd-2b1b-40be-a39b-e10615db8ee6` | Azure subscription context | `apps/api/app/config.py` |
| Internal Load Balancers | K8s Services `quanthire-frontend`, `quanthire-backend` | VNet/Jump VM access (`azure-load-balancer-internal: true`) | `quanthire.yaml` Services |
| DNS (public) | `quanthire-npd.malomatia.com` | User-facing frontend | README |

---

## 2. Kubernetes resources (namespace `quanthire-nonprod`)

| Resource | Name | Status | Purpose |
|----------|------|--------|---------|
| Namespace | `quanthire-nonprod` | NPD active | Isolation |
| ServiceAccount | `quanthire-nonprod` | NPD active | Pod identity |
| ConfigMap | `quanthire-nonprod-config` | NPD active | Non-secret env (LLM, Postgres host, vector store, etc.) |
| Deployment | `quanthire-nonprod-api` | NPD active | FastAPI + agents in-process |
| Deployment | `quanthire-nonprod-web` | NPD active | Next.js BFF + UI |
| Service | `quanthire-backend` (LB internal :8000) | NPD active | API target for BFF |
| Service | `quanthire-frontend` (LB internal :80) | NPD active | Web entry |
| CronJob | `quanthire-nonprod-usage-rollup` | Optional / Helm | AI Hub daily usage rollup (when enabled in manifest) |
| Worker Deployment | `quanthire-worker` | Optional | **Replicas 0 on NPD** — Celery not running |

---

## 3. Kubernetes secrets (NPD — values in cluster, not Git)

| Secret name | Keys (typical) | Purpose |
|-------------|----------------|---------|
| `quanthire-db-secret` | `DATABASE_URL` | Postgres connection string |
| `quanthire-blob-secret` | `AZURE_STORAGE_CONNECTION_STRING` | Blob access |
| `quanthire-aoai-secret` | `AZURE_OPENAI_API_KEY` | Azure OpenAI |
| `quanthire-di-secret` | `AZURE_DOCUMENT_INTELLIGENCE_KEY` | Document Intelligence |
| `quanthire-auth-secret` | `JWT_SECRET_KEY` | Session JWT signing |
| `quanthire-entra-secret` | `AZURE_AD_CLIENT_SECRET` | Entra backend / Graph (when SSO enabled) |

Template (placeholders only): `infra/kubernetes/nonprod/quanthire-secrets.yaml`

---

## 4. Data stores & persistence

| Technology | Status | Role in QuantHire |
|------------|--------|-------------------|
| **PostgreSQL** | NPD active | System of record: users, jobs, candidates, applications, interviews, offers, audit, AI Hub `usage_log` / `usage_feedback` / `usage_daily_summary` |
| **pgvector** (Postgres extension) | NPD active | Embeddings for RAG (QuantChat), JD/candidate chunks, matching data access |
| **Azure Blob Storage** | NPD active | Binary resume uploads and processed files |
| **Milvus** | Legacy / local | Vector DB for early/local dev; **`MILVUS_ENABLED=false`** on NPD |
| **Redis** | Optional | Celery broker, LLM Gateway budget cache, rate limiting — **disabled on NPD Helm values** |
| **Local filesystem** | Local dev | `STORAGE_TYPE=local` when not on Azure |

**Embedding models (codebase)**

| Model | Where | Notes |
|-------|-------|-------|
| `text-embedding-3-large` | NPD ConfigMap | Azure OpenAI embedding deployment |
| `BAAI/bge-base-en-v1.5` (768d) | Code default / QuantChat settings / migrations | Local or normalized metadata; documented standard in resume pipeline comments |

---

## 5. LLM & AI inference services

| Provider | Status | Use |
|----------|--------|-----|
| **Azure OpenAI** | NPD active | Primary inference on Non-Prod (`LLM_PROVIDER=azure_openai`) |
| **Google Vertex AI (Gemini)** | Local dev | Default in `.env.example`; ADC / `GCP_PROJECT_ID` |
| **OpenAI API** | Optional | `OPENAI_API_KEY`, `LLM_PROVIDER=openai` |
| **Anthropic API** | Optional | In requirements / some agent configs |
| **Groq** | Optional | `GROQ_API_KEY` — fast inference fallback in factory |
| **Amazon Bedrock** | Optional | Config in JD/matching/resume parser settings; not NPD default |

**In-app LLM abstraction:** `apps/agents/agents/llm/chat_factory.py` (`create_chat_llm`)  
**LLM Gateway (Redis, budgets, tiers):** `apps/agents/agents/llm/gateway.py` — **optional**; JD/matching/QuantChat hot paths often bypass it

---

## 6. AI / agent frameworks & libraries

| Resource | Purpose |
|----------|---------|
| **LangGraph** | JD generation workflow state machine |
| **LangChain** | Chat models, prompts, chains across agents |
| **LangSmith** | Optional tracing (`LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`) |
| **CrewAI** | Legacy/experimental JD collaboration — not production hot path |
| **QueryRouter** (`apps/quantchat`) | QuantChat RAG orchestration |
| **sentence-transformers** | Optional local embeddings when not using AOAI |
| **MLflow** | Optional experiment tracking (`MLFLOW_TRACKING_URI`, `ENABLE_MLFLOW`) |

---

## 7. Document & export services

| Resource | Status | Purpose |
|----------|--------|---------|
| Azure Document Intelligence | NPD active | Resume PDF → text/layout |
| **Malomatia JD Word export** | App feature | `malomatia_jd_export` service + template under `apps/api/app/templates/malomatia/` |
| **jsPDF** (frontend) | App | Client-side PDF generation where used |

---

## 8. Authentication & security

| Resource | Status | Purpose |
|----------|--------|---------|
| **JWT** (HS256) | NPD active | API sessions (`JWT_SECRET_KEY`) |
| **Basic auth mode** | NPD active | `AUTH_MODE=basic` on Non-Prod ConfigMap |
| **Microsoft Entra ID / MSAL** | Optional / prepared | `@azure/msal-browser`, Entra env vars; staging Helm `entra_sso` |
| **RBAC** | App | Permission enums in `apps/api/app/middleware/rbac.py` |
| **PII pseudonymization** | App | Usage logs, HMAC user refs (`PII_PSEUDONYM_KEY` / JWT secret) |

---

## 9. Observability, metrics & AI adoption

| Resource | Status | Purpose |
|----------|--------|---------|
| **Structured logging** | NPD active | API middleware, `LOG_LEVEL` |
| **Prometheus** | Optional | `PROMETHEUS_ENABLED`; infra `infra/monitoring/prometheus.yml` |
| **Grafana** | Reference | `infra/monitoring/grafana/` |
| **Sentry** | Optional | `SENTRY_DSN` — production Helm example |
| **Application Insights** | Optional | OTLP / connection string in `apps/api/app/observability/tracing.py`; web `ApplicationInsightsInit` |
| **OpenTelemetry** | Optional | `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT` (AI Hub docs pattern) |
| **AI Hub usage logging** | NPD active (when enabled) | Postgres `usage_log`, adoption dashboard, optional `USAGE_ROLLUP_COLLECTOR_URL` |
| **LangSmith** | Optional | Agent trace visibility |

---

## 10. CI/CD & repository tooling

| Resource | Purpose |
|----------|---------|
| **GitHub Actions** | `ci.yml`, `deploy-nonprod.yml`, `deploy-staging.yml`, `deploy-production.yml`, `security-scan.yml` |
| **GitHub (remote)** | `Pradeep-Kumar25th/QuantHire-AI` |
| **Docker** | `Dockerfile.backend`, `Dockerfile.frontend` (production targets) |
| **Helm chart** | `infra/kubernetes/helm/quanthire/` — reference; NPD uses raw YAML |
| **Terraform (Azure)** | `infra/terraform/azure/` — modules: network, AKS, Postgres, Redis, storage, Key Vault, monitoring, ACR |
| **External Secrets Operator** | Reference prod pattern — Key Vault → K8s (`infra/kubernetes/external-secrets/`) |
| **pytest** | Unit tests (`tests/unit`) |
| **Alembic** | DB migrations (`apps/api/alembic`) |

---

## 11. Application runtime stack

| Layer | Technology | Location |
|-------|------------|----------|
| Frontend | **Next.js 14**, React 18, TypeScript, Tailwind, Radix UI | `apps/web` |
| BFF | Next.js Route Handlers `/api/[...path]` | `apps/web/src/app/api/` |
| Backend | **FastAPI**, Python 3.11, SQLModel, asyncpg | `apps/api` |
| Agents | Python packages (JD, matching, parsing) | `apps/agents/agents` |
| QuantChat / RAG | Python package | `apps/quantchat` |
| Background worker | **Celery** (optional) | `apps/worker` |
| MCP (calendar) | MCP server stub | `apps/mcp_servers/calendar/` |

---

## 12. External integrations (supported or planned in code)

| Integration | Env / config | Status |
|-------------|--------------|--------|
| **Microsoft Graph** | `MICROSOFT_CLIENT_ID`, tenant, secret | Calendar/email — optional |
| **SMTP email** | `SMTP_*`, `EMAIL_FROM` | Optional notifications |
| **Google OAuth** | `GOOGLE_CLIENT_ID` | Optional |
| **AWS S3** | `STORAGE_TYPE=s3` | Alternative object storage |
| **Pinecone / Qdrant** | `vector_store_type` in settings | Optional vector backends (not NPD) |
| **AI Hub metrics collector** | `USAGE_ROLLUP_COLLECTOR_URL`, `USAGE_ROLLUP_COLLECTOR_TOKEN` | Optional platform export |
| **Prefect / LiteLLM / etc.** | Transitive in `requirements.txt` | Dependency tree; not all are runtime-critical |

---

## 13. Staging / production reference resources (not NPD defaults)

| Resource | Example from repo | Notes |
|----------|-------------------|-------|
| ACR (prod example) | `quanthireprodacr.azurecr.io` | `infra/kubernetes/helm/values-production.yaml` |
| Region (prod example) | `qatarcentral` | Helm production values |
| PostgreSQL (staging example) | `quanthire-staging-postgres.postgres.database.azure.com` | `values-staging.yaml` |
| Azure OpenAI (staging example) | `oai-aihub-staging.openai.azure.com` | Staging Helm |
| Key Vault (prod example) | `quanthire-prod-kv.vault.azure.net` | External secrets manifest |
| Redis | Terraform module + prod Helm | Celery / caching when enabled |

---

## 14. Environment variables index (high level)

Grouped env vars appear in:

- `.env.example` (root — Vertex/local)
- `apps/web/.env.example` (BFF)
- `apps/agents/agents/jd_generation/.env.example` (LangSmith)
- `infra/kubernetes/nonprod/quanthire.yaml` ConfigMap (NPD non-secrets)
- `infra/kubernetes/helm/quanthire/templates/configmap.yaml` (Helm)

**NPD-critical groups:** `DEPLOYMENT_TARGET`, `DATABASE_URL`, `LLM_PROVIDER`, `AZURE_OPENAI_*`, `AZURE_STORAGE_*`, `AZURE_DOCUMENT_INTELLIGENCE_*`, `VECTOR_STORE` / `MILVUS_ENABLED`, `BFF_BACKEND_URL`, `JWT_SECRET_KEY`, `AUTH_MODE`, `USAGE_LOGGING_ENABLED` (when adoption enabled).

---

## 15. Quick matrix: NPD vs local dev

| Resource | NPD | Local dev (typical) |
|----------|-----|---------------------|
| Compute | AKS | `uvicorn` + `next dev` |
| Database | Azure PostgreSQL | Local Postgres |
| Vectors | pgvector | pgvector and/or **Milvus** |
| LLM | Azure OpenAI | Vertex or OpenAI key |
| Files | Azure Blob | Local disk |
| Resume OCR | Document Intelligence | May use text-only / PyPDF paths |
| Auth | basic (+ Entra IDs ready) | `AUTH_MODE=none` or basic |
| Redis / Celery | Off | Optional localhost Redis |
| Registry | ACR | N/A |

---

## 16. Related documentation in repo

| Document | Topic |
|----------|--------|
| `docs/kt-session-1-architecture-and-resources.md` | KT architecture reference |
| `docs/kt-session-1-presenter-pack.md` | KT script + diagrams |
| `docs/jd-generation-architecture.md` | JD subsystem |
| `README.md` | NPD URL and image tag |
| `infra/kubernetes/nonprod/quanthire.yaml` | Live NPD manifest |

---

*Last updated from repository state: Non-Prod manifest `quanthire.yaml`, `apps/api/app/config.py`, Helm/Terraform trees. If platform team renames Azure resources, update ConfigMap and this doc together.*
