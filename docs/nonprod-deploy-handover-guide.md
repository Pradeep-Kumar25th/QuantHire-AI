# QuantHire Non-Prod — build, push, and deploy (handover guide)

**Audience:** Engineers taking over QuantHire (e.g. post-KT) who need to ship a new backend/frontend to **Azure Non-Prod**.  
**Environment:** Malomatia AI Hub — AKS `aks-ail-npd-we-01`, ACR `crailnpdwe01`, namespace `quanthire-nonprod`.  
**Public URL:** https://quanthire-npd.malomatia.com  

This guide explains **what each step does**, **why it is required**, and **what can go wrong**. It matches the manual Windows batch flow used on the Jump VM and the automated pipeline in `.github/workflows/deploy-nonprod.yml`.

---

## 1. What you are doing (big picture)

QuantHire Non-Prod runs as **two containers** on AKS:

| Container | Image in ACR | Kubernetes deployment | Port |
|-----------|--------------|------------------------|------|
| **Backend** (FastAPI + agents + QuantChat) | `crailnpdwe01.azurecr.io/quanthire-backend:<tag>` | `quanthire-nonprod-api` | 8000 |
| **Frontend** (Next.js BFF + UI) | `crailnpdwe01.azurecr.io/quanthire-frontend:<tag>` | `quanthire-nonprod-web` | 3000 |

**Manual deploy flow:**

1. Authenticate to **Azure** and **Azure Container Registry (ACR)**.
2. **Build** Docker images from the **repo root** (not from `apps/web` alone).
3. **Push** images to ACR with a **tag** (today: `0.1.5`).
4. Point **kubectl** at the Non-Prod AKS cluster.
5. **Restart** API and web deployments so pods **pull** the new image digest (`imagePullPolicy: Always`).
6. Run **Alembic migrations** inside the API pod against Azure Postgres.

Config and secrets (DB URL, OpenAI keys, JWT, Entra secret) live in **Kubernetes ConfigMap + Secrets** — they are **not** baked into the image. See `infra/kubernetes/nonprod/quanthire.yaml` and `quanthire-secrets.yaml`.

---

## 2. Prerequisites

### 2.1 Tools (Jump VM or build machine)

| Tool | Purpose |
|------|---------|
| **Azure CLI** (`az`) | Login, ACR login, AKS credentials |
| **Docker Desktop** (or Docker Engine) | Build `Dockerfile.backend` / `Dockerfile.frontend` |
| **kubectl** | Restart deployments, exec migrations, logs |
| **Git** | Clone/checkout the release commit |

### 2.2 Azure permissions (typical)

Your account or service principal needs at least:

- **ACR:** `AcrPush` on `crailnpdwe01` (push images).
- **AKS:** `Azure Kubernetes Service Cluster User Role` on `aks-ail-npd-we-01` (get credentials + kubectl).
- Optional: read access to resource group `rg-ail-wkload-npd-we-01`.

If `az acr login` or `kubectl` fails with **403**, request access via your platform team (TAMM / AI Hub), not by changing repo scripts.

### 2.3 Repository layout

Clone the repo and use **repo root** as the Docker build context:

```text
QuantHire AI/          ← you must be HERE for docker build
├── Dockerfile.backend
├── Dockerfile.frontend
├── apps/api/          ← copied into backend image
├── apps/agents/
├── apps/quantchat/
├── apps/web/          ← copied into frontend image
└── infra/kubernetes/nonprod/quanthire.yaml
```

### 2.4 Image tag discipline

- **Current tag in README and manifest:** `0.1.5`  
- Manifest pins: `infra/kubernetes/nonprod/quanthire.yaml` lines `image: ...quanthire-backend:0.1.5` and `...quanthire-frontend:0.1.5`.

**Reusing tag `0.1.5`:** You can push a **new digest** for the same tag; restart deployments + `imagePullPolicy: Always` forces pods to pull the latest digest.

**Using a new tag (e.g. `0.1.6`):** You must:

1. Push images with the new tag.
2. Edit `quanthire.yaml` (both image lines) and `IMAGE_TAG` in `.github/workflows/deploy-nonprod.yml` / README.
3. `kubectl apply -f infra/kubernetes/nonprod/quanthire.yaml` **or** rely on restart if only digest changed under same tag.

---

## 3. Step-by-step (Windows CMD) — with explanations

Run these from an **elevated or normal CMD** on a machine that has Docker, `az`, and `kubectl`. Malomatia often uses a **Jump VM** with network access to AKS.

### Step 0 — Go to repo root

```bat
cd /d "d:\QuantHire AI"
```

**Why:** Both Dockerfiles expect build context `.` (repo root). Building from `apps\api` or `apps\web` will fail or produce broken images.

**Check:** `dir Dockerfile.backend` and `dir Dockerfile.frontend` must exist.

---

### Step 1 — Azure + ACR login

```bat
REM 1) Azure + ACR login
az login
az acr login --name crailnpdwe01
```

| Command | What it does |
|---------|----------------|
| `az login` | Opens browser (or device code) to authenticate your Azure AD user. Sets the default subscription if you have several — confirm the AI Hub subscription when prompted. |
| `az acr login --name crailnpdwe01` | Docker CLI logs in to **Azure Container Registry** `crailnpdwe01.azurecr.io` so `docker push` succeeds. |

**Success looks like:** `Login Succeeded` for ACR; `docker push` no longer returns `unauthorized`.

**Common failures:**

- Wrong subscription: `az account set --subscription "<subscription-id>"`.
- No ACR push role: contact platform team.
- Docker not running: start Docker Desktop.

---

### Step 2 — Build and push backend

```bat
REM 2) Build & push backend
docker build -f Dockerfile.backend --target production -t crailnpdwe01.azurecr.io/quanthire-backend:0.1.5 .
docker push crailnpdwe01.azurecr.io/quanthire-backend:0.1.5
```

| Part | Meaning |
|------|---------|
| `-f Dockerfile.backend` | Multi-stage file: builder installs Python deps; **production** stage copies `apps/api`, `apps/agents`, `apps/quantchat`, runs uvicorn. |
| `--target production` | Final slim image only (no compiler toolchain in runtime). |
| `-t crailnpdwe01.azurecr.io/quanthire-backend:0.1.5` | Full image name ACR expects; tag must match manifest unless you update YAML. |
| `.` | Build context = **current directory (repo root)**. |

**What is inside the backend image:** FastAPI app, all in-process agents (JD, matching, parsing), QuantChat QueryRouter, Alembic migrations under `/app`.

**Duration:** Often 5–15 minutes first time; faster with layer cache on repeat builds.

**After push:** In Azure Portal → ACR → Repositories → `quanthire-backend` → tag `0.1.5` should show a **new last modified time**.

---

### Step 3 — Build and push frontend

```bat
REM 3) Build & push frontend
docker build -f Dockerfile.frontend --target production -t crailnpdwe01.azurecr.io/quanthire-frontend:0.1.5 .
docker push crailnpdwe01.azurecr.io/quanthire-frontend:0.1.5
```

| Part | Meaning |
|------|---------|
| `Dockerfile.frontend` | `npm ci` + `npm run build` → Next.js **standalone** output; runtime is `node server.js` on port 3000. |
| Same tag/registry pattern | Web deployment pulls `quanthire-frontend:0.1.5`. |

**Note:** Frontend image does **not** embed Azure secrets. At runtime it reads `BFF_BACKEND_URL` from the ConfigMap (in-cluster URL to the API Service).

**Size:** Frontend build is heavy (node_modules + Next build). Ensure sufficient disk RAM for Docker.

---

### Step 4 — AKS context

```bat
REM 4) AKS context
az aks get-credentials --resource-group rg-ail-wkload-npd-we-01 --name aks-ail-npd-we-01 --overwrite-existing
```

**What it does:** Merges kubeconfig on your machine so `kubectl` talks to **Non-Prod AKS**.

**Verify:**

```bat
kubectl config current-context
kubectl get ns quanthire-nonprod
```

You should see namespace `quanthire-nonprod` and deployments if the app was deployed before.

**Security:** `--overwrite-existing` refreshes credentials; do not commit `kubeconfig` to Git.

---

### Step 5 — Restart deployments (pull fresh image)

```bat
REM 5) Restart both deployments (pull fresh :0.1.5 digest)
kubectl rollout restart deployment/quanthire-nonprod-api -n quanthire-nonprod
kubectl rollout restart deployment/quanthire-nonprod-web -n quanthire-nonprod

kubectl rollout status deployment/quanthire-nonprod-api -n quanthire-nonprod --timeout=10m
kubectl rollout status deployment/quanthire-nonprod-web -n quanthire-nonprod --timeout=10m
```

| Command | Why |
|---------|-----|
| `rollout restart` | Creates new ReplicaSet; old pods terminate. With `imagePullPolicy: Always`, new pods **pull** the current digest for `:0.1.5` from ACR. |
| `rollout status ... --timeout=10m` | Blocks until rollout succeeds or times out — avoids assuming deploy finished while pods are still crashing. |

**Watch pods:**

```bat
kubectl get pods -n quanthire-nonprod -w
```

**Readiness:** API uses `/readyz` (DB and dependencies); web uses `/api/health`. Failed readiness → check logs:

```bat
kubectl logs deploy/quanthire-nonprod-api -n quanthire-nonprod --tail=100
kubectl logs deploy/quanthire-nonprod-web -n quanthire-nonprod --tail=100
```

**When to `kubectl apply` instead of only restart:** First-time deploy, ConfigMap/env changes, **image tag change** in YAML, replica/resource changes. Command:

```bat
kubectl apply -f infra\kubernetes\nonprod\quanthire.yaml
```

Secrets are applied separately (once): `infra\kubernetes\nonprod\quanthire-secrets.yaml` — **never commit real secrets to Git**.

---

### Step 6 — Database migrations

```bat
REM 6) Migrations (safe even if no-op)
kubectl exec deploy/quanthire-nonprod-api -n quanthire-nonprod -- alembic upgrade head
```

**What it does:** Runs Alembic against **Azure Postgres** (`DATABASE_URL` from secret `quanthire-db-secret`) inside the running API container.

**Why after deploy:** New code may depend on new columns/enums; migrations must run before traffic hits new logic (rollout order: new pods start → run migrations when API is up; for breaking schema, coordinate downtime).

**Safe if no-op:** If there are no pending revisions, Alembic exits successfully with no changes.

**Failure signs:** Traceback in exec output — often DB connectivity, SSL, or permission. Fix secrets/network before retrying.

---

## 4. Full copy-paste script (Windows CMD)

```bat
cd /d "d:\QuantHire AI"

REM 1) Azure + ACR login
az login
az acr login --name crailnpdwe01

REM 2) Build & push backend
docker build -f Dockerfile.backend --target production -t crailnpdwe01.azurecr.io/quanthire-backend:0.1.5 .
docker push crailnpdwe01.azurecr.io/quanthire-backend:0.1.5

REM 3) Build & push frontend
docker build -f Dockerfile.frontend --target production -t crailnpdwe01.azurecr.io/quanthire-frontend:0.1.5 .
docker push crailnpdwe01.azurecr.io/quanthire-frontend:0.1.5

REM 4) AKS context
az aks get-credentials --resource-group rg-ail-wkload-npd-we-01 --name aks-ail-npd-we-01 --overwrite-existing

REM 5) Restart both deployments (pull fresh :0.1.5 digest)
kubectl rollout restart deployment/quanthire-nonprod-api -n quanthire-nonprod
kubectl rollout restart deployment/quanthire-nonprod-web -n quanthire-nonprod

kubectl rollout status deployment/quanthire-nonprod-api -n quanthire-nonprod --timeout=10m
kubectl rollout status deployment/quanthire-nonprod-web -n quanthire-nonprod --timeout=10m

REM 6) Migrations (safe even if no-op)
kubectl exec deploy/quanthire-nonprod-api -n quanthire-nonprod -- alembic upgrade head
```

---

## 5. Post-deploy validation

Run on the Jump VM (adjust frontend URL if your LoadBalancer IP differs):

```bat
infra\kubernetes\nonprod\validate-before-apply.cmd
```

Or manually:

| Check | Command / URL |
|-------|----------------|
| API ready | `kubectl exec deploy/quanthire-nonprod-api -n quanthire-nonprod -- curl -sf -H "Host: localhost" http://127.0.0.1:8000/readyz` |
| BFF health | `kubectl exec deploy/quanthire-nonprod-web -n quanthire-nonprod -- wget -qO- http://127.0.0.1:3000/api/health` |
| Browser | https://quanthire-npd.malomatia.com — login, load dashboard, smoke-test JD or QuantChat |

---

## 6. Alternative: GitHub Actions (recommended for repeatability)

Workflow: `.github/workflows/deploy-nonprod.yml`

- Triggers on **`main`** pushes under `apps/**`, `infra/kubernetes/**`, `Dockerfile.*`, or **manual** `workflow_dispatch`.
- Runs unit tests + frontend `tsc`/build, then build/push both images, `kubectl apply`, restart, migrations, smoke tests.

Use manual deploy (Section 3) when:

- CI secrets are unavailable,
- You need a hotfix from a branch not yet merged,
- Jump VM is the approved path for AI Hub.

---

## 7. Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `ImagePullBackOff` | Wrong tag, ACR auth on node, typo in image name | Verify tag in ACR; check AKS–ACR attachment; describe pod |
| API pod `CrashLoopBackOff` | Bad env, DB URL, missing secret | `kubectl logs` / `kubectl describe pod`; verify secrets applied |
| Web pod unhealthy | BFF cannot reach API Service | Check `BFF_BACKEND_URL` in ConfigMap → `http://quanthire-backend.quanthire-nonprod.svc.cluster.local:8000` |
| Migrations fail | Postgres firewall, SSL, enum drift | Compare Alembic versions; run fix scripts under `apps/api/scripts/` if documented |
| Old UI after deploy | Browser cache or rollout not finished | Hard refresh; confirm `rollout status` succeeded |
| Docker build OOM | Frontend build memory | Increase Docker memory; build on CI instead |

---

## 8. Reference map (files to know)

| File | Role |
|------|------|
| `Dockerfile.backend` | Backend production image |
| `Dockerfile.frontend` | Frontend production image |
| `infra/kubernetes/nonprod/quanthire.yaml` | Deployments, Services, ConfigMap (canonical NPD) |
| `infra/kubernetes/nonprod/quanthire-secrets.yaml` | Secret **templates** (apply with real values on cluster) |
| `.github/workflows/deploy-nonprod.yml` | Automated Non-Prod pipeline |
| `apps/api/alembic/` | Database migrations |
| `docs/local-development-without-docker.md` | Local dev without full Docker stack |

---

## 9. Handover checklist (sign-off)

- [ ] Can `az login` and `az acr login --name crailnpdwe01` on build machine  
- [ ] Can build and push **both** images without error  
- [ ] Can `kubectl get pods -n quanthire-nonprod`  
- [ ] Rollout restart completes within 10 minutes  
- [ ] `alembic upgrade head` succeeds  
- [ ] `validate-before-apply.cmd` (or manual health checks) passes  
- [ ] Know where secrets are stored (K8s secrets, not Git)  
- [ ] Know when to bump image tag vs reuse `0.1.5`  

---

*End of Non-Prod deploy handover guide.*
