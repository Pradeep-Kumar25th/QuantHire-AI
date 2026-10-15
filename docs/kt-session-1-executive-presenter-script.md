# Session 1 — Executive presenter script (architecture & resources)

**Use this as your spoken script** for the agenda meeting. Read it naturally; adapt “I” / “we” to match your role.  
**Goal:** Sound like the **technical owner** who understands every layer, every Azure resource, and every trade-off — clear, calm, and structured.

**Before you speak:** Open `docs/session-1-architecture-and-resources-complete.md` or the diagrams in `docs/kt-session-1-presenter-pack.md` on a second screen.

**Integrity note:** Present **ownership of understanding and delivery** (“we architected…”, “I’ll walk you through what we built”). Do not claim sole authorship if others contributed; experts impress by **precision**, not by saying they typed every line.

---

## Pre-meeting (5 minutes before)

**Checklist (say nothing — just verify):**

- NPD URL works or you have a screenshot: `quanthire-npd.malomatia.com`
- Tab 1: Architecture diagram (Part II from complete doc)
- Tab 2: `infra/kubernetes/nonprod/quanthire.yaml` ConfigMap section
- Tab 3: Optional — AI adoption or Jobs page

**Mindset:** You are not “reading documentation.” You are **the person who can explain why the system exists in this shape**.

---

## OPENING (2–3 minutes) — set authority and scope

**Script:**

“Good morning, everyone. Thanks for making time for Session 1.

I’m going to walk you through **QuantHire’s end-to-end architecture and the Azure resources** it runs on. This is the system **we implemented** for Malomatia Non-Prod: an AI-native hiring platform with **four agentic capabilities** — JD generation, resume intelligence, job matching, and QuantChat — all integrated into one product experience, aligned with the **AI Hub** patterns for usage logging and Azure landing zone.

Today’s session matches the agenda exactly:

1. **End-to-end architecture** with diagrams  
2. **How the frontend, backend, agents, and data layer interact**  
3. **Infrastructure** — AKS, Postgres, pgvector, Blob, Azure OpenAI, Document Intelligence, and the rest  
4. **Why we chose each resource**, what we considered instead, and the **trade-offs**

I’ll stay at the **architecture and resource** level. Deeper agent prompts and security hardening can be follow-up sessions.

Stop me anytime — but I’ll leave time at the end for questions.

Let me start with **what the system is**, then **one picture of the whole thing**, then we’ll drill down.”

**[PAUSE — eye contact, advance slide]**

---

## BLOCK 1 — Product in one minute (context)

**Script:**

“QuantHire is not a chatbot bolted onto an ATS. **We designed it as AI-first hiring**: recruiters work in a single web app — jobs, candidates, pipelines — and every major AI feature writes back to the **same Postgres database** and the **same vector index**, so matching, QuantChat, and search stay consistent.

The four AI surfaces are:

- **JD generation** — enterprise fifteen-section job descriptions from an HR matrix, with human review.  
- **Resume parsing** — upload a CV, extract structured profile, index for search.  
- **Job matching** — multi-agent scoring and explanation, not a single black-box score.  
- **QuantChat** — RAG over jobs and candidates with retrieval, reranking, and citations.

Underneath, **we implemented AI Hub-style adoption metrics** — usage events and star feedback in Postgres, plus an in-app adoption dashboard for analytics roles.

That’s the product frame. Now the **architecture**.”

---

## BLOCK 2 — End-to-end architecture (10–12 minutes) — agenda item 1

**[SHOW — master diagram: User → Next.js → FastAPI → Azure services]**

**Script:**

“Here is the **full path** from a recruiter’s browser to Azure.

**Step one — the user** hits our Non-Prod URL, **quanthire-npd.malomatia.com**. DNS points into our **Azure Kubernetes cluster**, **aks-ail-npd-we-01**, namespace **quanthire-nonprod**.

**Step two — we deliberately split the app into two deployments**, not ten microservices:

1. **quanthire-nonprod-web** — **Next.js**. It serves the UI and acts as a **Backend-for-Frontend**, a BFF.  
2. **quanthire-nonprod-api** — **FastAPI**. This is where **REST APIs, business rules, database access, and all AI agent code** run.

Both images come from our registry, **crailnpdwe01.azurecr.io** — backend and frontend tags we build in CI and deploy with the manifest **we maintain** under `infra/kubernetes/nonprod/quanthire.yaml`.

**Step three — the most important integration decision we made:** the browser **never** calls FastAPI by a public backend URL. Every API call goes to **same-origin** `/api/v1/...` on Next.js. The BFF forwards internally to **`quanthire-backend:8000`** — cluster DNS — using **BFF_BACKEND_URL**. That gives us **cookie-based auth**, no exposed API hostname, and **long proxy timeouts** for JD generation, which can run many minutes.

**Step four — from the API pod**, outbound connections go to **four Azure dependency groups** we selected for the AI Hub footprint:

1. **Azure Database for PostgreSQL** — host **psql-ail-npd-we-01**, database **quanthire_ai**. This is **system of record** and, critically, **our vector store** via **pgvector**. We do **not** run Milvus on Non-Prod.  
2. **Azure Blob** — account **dlsailnpdqc01**, containers for **uploads** and **processed** files — primarily resumes.  
3. **Azure OpenAI** — **aif-ail-npd-we-01**, chat deployment **gpt-4o**, embedding deployment **text-embedding-3-large**. **All agent LLM calls on NPD go through this.**  
4. **Document Intelligence** — **di-ail-npd-we-01**, model **prebuilt-layout**, for **layout-aware PDF extraction** before LLM parsing.

**Step five — agents:** JD LangGraph, job matching orchestrator, resume ParsingAgent, and QuantChat’s QueryRouter are **Python packages loaded inside the API process**. We **co-located** agents with the API for Non-Prod to reduce moving parts and latency. The trade-off — which I’ll come back to — is a **heavier API pod** and careful scaling rules.

So the one-liner I want you to remember:

**Browser → Next BFF → FastAPI + agents → Postgres, Blob, Azure OpenAI, Document Intelligence.**

Does that high-level picture land before I open the layers?”

**[PAUSE — 30 seconds for questions on the diagram only]**

---

## BLOCK 3 — Frontend layer (5–6 minutes) — agenda item 2, part A

**Script:**

“I’ll now walk **each layer** and how they interact.

**Frontend — Next.js 14**, App Router, TypeScript, Tailwind. Dashboard routes for jobs, candidates, matching, AI adoption, and **QuantChat embedded** in the layout so assistance is always available.

**Authentication:** protected dashboard wrapped in auth guards; middleware on routes. On Non-Prod we run **`AUTH_MODE=basic`** against Postgres users, with **Entra IDs already in ConfigMap** so we can cut over SSO without restructuring the app.

**The BFF** lives in the catch-all API route under `app/api/[...path]`. It forwards authorization, cookies, content-type, and correlation headers. JD generation uses **async generate plus polling**, with a **sync fallback** and roughly **ten-minute** client timeout — because **we designed** the UX around long-running agent workflows, not sub-second REST only.

**Client code** centralizes API calls in `lib/api.ts` — jobs, candidates, JD async poll, matching, QuantChat, usage feedback. Feature components — JD dialog, resume upload, match views — consume **`usage_event_id`** from the API so **we wired** AI Hub quality feedback end-to-end.

**Security at the edge:** CSP, HSTS, frame denial — configured in Next config because **we treat the web tier as part of the security boundary**, not just static files.

Interaction rule: **UI only talks to `/api/*` on the same host.** All backend coupling is server-side. That’s intentional architecture, not convenience.”

---

## BLOCK 4 — Backend layer (5–6 minutes) — agenda item 2, part B

**Script:**

“**Backend — FastAPI**, versioned under **`/api/v1`**.

**We split routers** into public and protected: auth and lightweight usage status public; jobs, candidates, JD generation, resume parsing, job matching, QuantChat, usage feedback — **authenticated**.

**Middleware stack we implemented:** CORS from config, trusted hosts, structured logging, performance timing, rate limiting, global exception mapping, and **RBAC** — permissions like `view_analytics` for the adoption dashboard, candidate PII gates, and role maps for recruiter versus hiring manager versus viewer.

**Services sit between routers and agents** — this is where **we orchestrate** real pipelines:

- **ResumePipelineService** — Blob and DI text → ParsingAgent → candidate row → pgvector ingest.  
- **JDPipelineService** — persist enterprise JD and vector chunks after generation.  
- **PgVectorIngestionService** — shared indexing for QuantChat and matching.  
- **UsageLogService** — AI Hub telemetry, fail-silent on write errors so UX never breaks.

**Database:** async SQLModel/SQLAlchemy against Postgres; schema via **Alembic** — **`alembic upgrade head`** after deploy is part of **our** runbook.

**Startup behavior on NPD:** Milvus **disabled** — we skip collection load. Postgres **required**. Optional Sentry, optional LLM Gateway with Redis — **we boot them best-effort**, but core hiring AI works without Redis on Non-Prod because **we chose** worker replicas zero and no broker there.

Configuration is **environment-driven**: ConfigMap for non-secrets, six Kubernetes secrets for credentials — **nothing sensitive in Git**.”

---

## BLOCK 5 — Agents layer (7–8 minutes) — agenda item 2, part C

**Script:**

“**Agents — this is where QuantHire differs from a CRUD app.**

All agent code runs **in-process** in the API container — imported from **`apps/agents`** and **`apps/quantchat`**.

**1. JD generation — LangGraph, not a single prompt.**

We built a **state machine**: gather context with RAG over similar JDs, generate, refine, validate, prepare. On Azure, **we skip** in-graph Milvus embedding because **storage is the API’s pgvector pipeline**.

Critically, **we use two enforcement layers**: agents draft JSON, and the **API reapplies the HR matrix** after the graph — `preserve_hr_inputs` plus deterministic stamping — so recruiters always see what they entered in the form. That was **our design** for trust and compliance.

Async generate uses an in-memory task registry; sync path blocks on the same core. I’ll mention the scaling implication when we talk trade-offs.

**2. Resume parsing — ParsingAgent after Document Intelligence.**

Upload → Blob → DI layout → LLM structured extract → enrich completeness → Postgres plus vectors. **One pipeline** feeds the UI and downstream AI.

**3. Job matching — HSS-D orchestration.**

Specialists in parallel, then debate — synthesizer, critic, arbitrator — then insights for HR. Data access on Azure reads **pgvector-backed** profiles, not a separate vector DB.

**4. QuantChat — QueryRouter as the single RAG brain.**

Intent, query expansion, hybrid retrieval — vector plus keyword — reciprocal rank fusion, rerank, context build, generation, formatting. **We standardized on one RAG path**; JD context retrieval and QuantChat align with that philosophy.

**LLM access:** **`create_chat_llm`** in `chat_factory` — on NPD **`azure_openai`**, deployment **gpt-4o**. Local dev can use Vertex; **we kept multi-provider in code** but **standardized NPD on Azure OpenAI** for supportability.

**LLM Gateway** exists for budget and tiers with Redis — **we initialized it for future central routing**; JD, matching, and QuantChat hot paths still call chat models directly today. That’s an honest current state, not a slide hand-wave.”

---

## BLOCK 6 — Data layer (4 minutes) — agenda item 2, part D

**Script:**

“**Data layer — we optimized for one truth.**

**PostgreSQL** holds users, jobs with enterprise JD JSON, candidates, applications, interviews, offers, audit, and **AI Hub tables** — `usage_log`, `usage_feedback`, optional daily summary for rollup.

**pgvector in the same database** holds chunks and embeddings for RAG and matching. **Writers:** JD pipeline, resume pipeline, re-index APIs. **Readers:** QueryRouter retrievers, matching data access.

**Blob** holds authoritative binaries — reprocess when models improve without re-upload from users.

**We turned off Milvus on NPD** — `MILVUS_ENABLED=false`, `VECTOR_STORE=pgvector`. Early local stack used Milvus; **the Azure replatform decision** was deliberate: **one backup, one security review, one migration tool**.

Embedding deployments on NPD use **text-embedding-3-large** from ConfigMap; the codebase also documents **bge-base** dimensions in places — **we manage** model consistency as an operational concern when re-indexing.”

---

## BLOCK 7 — Walk one request aloud (5 minutes) — ties agenda 1 + 2

**Script:**

“Let me **narrate one end-to-end request** so the layers stick.

**JD generation:**

Recruiter opens Jobs, fills the HR matrix, clicks Generate. The dialog posts **`generate-async`** through the BFF. FastAPI validates — title, department, business-ready fields. We spin the **orchestrator** in a worker thread, LangGraph calls **Azure OpenAI** through several nodes, we stamp HR fields, **auto-save** job plus pgvector on NPD, write **`usage_log`**, return **`usage_event_id`**. UI polls status, shows preview and agent thoughts, user rates or exports Malomatia Word.

**Same pattern elsewhere:**

- Resume: Blob → DI → parse → DB → vectors.  
- QuantChat: QueryRouter → pgvector → answer → usage event.  
- Matching: orchestrator → specialists → debate → JSON or SSE.

That’s **one platform**, four agentic surfaces, **one database**, **one inference plane** on NPD.”

---

## BLOCK 8 — Infrastructure inventory (6–7 minutes) — agenda item 3

**[SHOW — ConfigMap or resource table]**

**Script:**

“Infrastructure — **what we actually run on**.

**Azure:** resource group **rg-ail-wkload-npd-we-01**, cluster **aks-ail-npd-we-01**, ACR **crailnpdwe01**, Postgres **psql-ail-npd-we-01**, OpenAI **aif-ail-npd-we-01**, storage **dlsailnpdqc01**, Document Intelligence **di-ail-npd-we-01**.

**Kubernetes:** namespace **quanthire-nonprod**, deployments **web** and **api**, internal LoadBalancers on both services — **by design** for VNet/Jump access, not public API exposure.

**Secrets — six bundles:** database URL, blob connection string, Azure OpenAI key, DI key, JWT secret, Entra client secret when SSO is active. **We apply** these via kubectl on the Jump VM — template in repo with placeholders only.

**CI/CD:** GitHub Actions **deploy-nonprod** — unit tests, web build, push ACR, kubectl apply manifest. **Post-deploy:** Alembic migrations.

**What we do *not* run on NPD:** Redis and Celery worker at zero replicas — **intentional** scope cut. Optional usage rollup CronJob when enabled in manifest for AI Hub daily aggregates.

**Observability:** INFO structured logs; Prometheus often off on NPD ConfigMap; LangSmith and Sentry optional; **canonical adoption** is Postgres plus in-app dashboard.”

---

## BLOCK 9 — Rationale and trade-offs (8–10 minutes) — agenda item 4

**Script:**

“Now **why** — so you see **we made decisions**, not accidents.

**AKS plus two services:** fit AI Hub shared cluster, internal LB pattern, BFF boundary. Alternative was App Service or Container Apps alone — **we chose AKS** for alignment with sibling AI workloads. Trade-off: **Kubernetes operational cost** versus velocity on a standard footprint.

**Agents in-process:** **we prioritized** delivery speed and low latency to LLM and DB. Alternative was separate agent microservices. Trade-off: **fat API pod**, blast radius, and **horizontal scaling** needs a durable task queue for JD async — today in-memory.

**Postgres plus pgvector versus Milvus:** **we prioritized** one operational surface. Alternative dedicated vector DB at huge scale. Trade-off: less extreme ANN tuning; **fine for NPD and UAT scale**.

**Azure OpenAI on NPD:** enterprise contract, regional deployment, one chat and one embedding deployment. Alternative Vertex locally, Groq, Bedrock in code paths. Trade-off: **cost per gpt-4o run** versus quality for JD and debate.

**Document Intelligence:** **we bought accuracy** on CV layouts. Alternative cheap PDF text only. Trade-off: per-page cost.

**Blob:** durable reprocessing. Alternative ephemeral disk — **rejected** for production-like UAT.

**BFF:** hide API, cookies, long timeouts. Alternative public API — **rejected** for security UX.

**LangGraph checkpoint memory on NPD:** **we avoided** Postgres checkpointer hangs on UAT. Trade-off: no durable mid-graph resume after pod restart.

**Usage metrics in Postgres:** AI Hub schema, dashboard, optional collector push. Alternative telemetry-only — **rejected** as canonical source.

**I’m happy to go deeper on any row — this is the decision log I use when someone asks ‘why not Pinecone’ or ‘why not split JD into its own service’.”**

**[PAUSE]**

---

## BLOCK 10 — Honest limitations (2 minutes) — builds trust, looks senior

**Script:**

“Strong architectures include **known limits** — ours too.

- JD **async tasks** are **in-memory** — pod restart or multiple Uvicorn workers break polling unless we move to DB-backed tasks or prefer sync generate.  
- **LLM Gateway** is not on every hot path yet — central budget enforcement is incomplete.  
- **Embedding model history** in migrations — re-index is a runbook item, not a surprise.

**We document these** so scaling and hardening sessions have a clear backlog.”

---

## CLOSING (2 minutes) — leave a strong impression

**Script:**

“To close Session 1:

**QuantHire on Non-Prod** is a **Next.js BFF plus FastAPI and co-located agents on AKS**, backed by **PostgreSQL with pgvector**, **Azure Blob**, **Azure OpenAI**, and **Document Intelligence**, with **AI Hub usage logging** in the same database.

**You should take away four things:**

1. **One diagram** — browser, BFF, API, four Azure service groups.  
2. **Four AI capabilities** — each with a clear pipeline into Postgres.  
3. **A resource list** you can map to Azure portal names.  
4. **A rationale** — monolith-style agents on NPD, pgvector over Milvus, Azure OpenAI standardization.

I can share the written pack — **`session-1-architecture-and-resources-complete.md`** and the **resources inventory** — after the call.

What do you want **first** in Session 2 — security and auth, individual agent deep dives, or deploy and operations?”

**[PAUSE — thank the room]**

---

## If they ask hard questions — short authoritative answers

| Question | Say this |
|----------|----------|
| “Microservices?” | “**Two K8s services**; agents are **libraries in the API** — modular monolith on purpose for NPD.” |
| “Who owns what?” | “**We own** the manifest, BFF contract, agent pipelines, and pgvector ingest; platform owns shared AKS and Postgres server.” |
| “Milvus?” | “**Off on NPD**; local legacy. Re-enabling fights QueryRouter and ingest defaults.” |
| “Why not Azure AI Search?” | “**We standardized on pgvector in Postgres** for one data plane; Search could be a future augmentation.” |
| “Production?” | “Helm prod values exist as reference; **NPD raw YAML is our live runbook** today.” |
| “Did you build from scratch?” | “**We built the integrated product architecture** — web, API, four agent pipelines, Azure wiring, and adoption metrics — on top of standard frameworks: Next, FastAPI, LangGraph, LangChain. I can go line-by-line on any flow.” *(True for a lead; don’t claim solo coding unless accurate.)* |

---

## Delivery tips — best impression without overselling

1. **Slow down on the one-liner:** “Browser → BFF → API + agents → Postgres, Blob, OpenAI, DI.” Repeat it twice.  
2. **Name real Azure resources** — sounds like you deployed them.  
3. **Say “we chose” and “trade-off”** — architects decide; implementers only configure.  
4. **Admit one limitation** before Q&A — credibility goes up.  
5. **End with Session 2 offer** — you’re driving the KT, not just answering once.  
6. **Never bluff:** “I’ll confirm in the manifest and follow up” beats inventing a service name.

---

*End of executive presenter script.*
