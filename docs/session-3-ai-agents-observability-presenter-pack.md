# Session 3 — AI components, agentic workflows & observability

**QuantHire AI — Knowledge transfer (presenter pack)**  
**Audience:** AI engineers continuing development (e.g. Farhaan)  
**Suggested duration:** 60–90 minutes  
**Prerequisites:** Session 1 (architecture), Session 2 (code walkthrough)  
**Companions:** `docs/session-3-ai-components-complete.md` (full tables + line index), `docs/agentic-systems-quick-reference.md`, `docs/session-2-agentic-code-tour.md`

---

## Session goal (say this upfront)

By the end, Farhaan should know:

1. **Where AI logic lives** (`apps/quantchat`, `apps/agents`, wired through `apps/api`)  
2. **How QuantChat routes a query** end-to-end (intent → retrieve → fuse → rerank → generate)  
3. **How the three agentic products orchestrate work** (JD LangGraph, resume pipeline, matching swarm/debate)  
4. **How models and prompts are configured** (single factory, env-driven provider)  
5. **How quality is measured today** (heuristic RAG eval, validators, hiring feedback — and what is **not** wired yet)  
6. **How to observe runs** (logs, in-process traces, LangSmith hooks, status endpoints)

---

## Recommended agenda (timeboxed)

| Block | Minutes | Topic |
|-------|---------|--------|
| 1 | 5 | Map: one API process, multiple AI subsystems |
| 2 | 20 | QuantChat: QueryRouter + RAG pipeline |
| 3 | 20 | Agentic workflows: JD, resume, matching |
| 4 | 10 | LLM / prompt configuration & fallbacks |
| 5 | 10 | Evaluation & feedback loops |
| 6 | 10 | Observability: logs, traces, metrics, dashboards |
| 7 | 5 | Gaps & next steps for engineering |

---

# 1. Architecture map (5 min)

```text
                    ┌─────────────────────────────────────┐
                    │  FastAPI (apps/api)                 │
                    │  quantchat.py → QueryRouter         │
                    │  jd_generation.py → JD orchestrator │
                    │  resume_parsing.py → ParsingAgent  │
                    │  job_matching.py → MatchOrchestrator│
                    └──────────────┬──────────────────────┘
                                   │ in-process imports
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
  apps/quantchat            apps/agents/agents          Postgres + pgvector
  (RAG read path)           (JD, parsing, matching)     (chunks, jobs, feedback)
         │                         │
         └──────── create_chat_llm / embeddings ────────┘
```

**Invariant (NPD):** QuantChat **reads** via **QueryRouter only** — no parallel RAG shortcuts in product APIs. **Writes** (resume/JD ingest) go through `pgvector_ingestion` / pipelines.

---

# 2. QuantChat (20 min)

## 2.1 Entry points

| Layer | File | Symbol | Line (approx.) |
|-------|------|--------|----------------|
| API | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | 90 |
| Core | `apps/quantchat/core/query_router.py` | `route_query` | 109 |
| Singleton | `apps/quantchat/__init__.py` | `get_query_router` | 37 |

API runs `route_query` in **`asyncio.to_thread`** so long RAG/LLM work does not block the event loop (health checks, other requests).

Conversation context:

- API **`conversation_histories[user_id]`** (in-memory)  
- Synced into **`ConversationMemory`** before each call (`_sync_router_memory_from_api_history`)  
- **`session_id=user_id`** on `route_query`

## 2.2 Query routing flow (whiteboard)

```text
User message
  → normalize + enhance with tracked entities
  → intent classify (LLM or regex fallback)
  → branch:
       GENERAL_KNOWLEDGE  → general LLM (no retrieval)
       FULL_DOCUMENT      → full-doc retriever
       COMPARISON         → comparison RAG handler
       else               → _handle_rag_pipeline (main HR path)
  → memory.add_turn (user + assistant + entities)
  → optional observability complete_trace (quality + cost)
```

**Intent types** (`intent_classifier.py`): `RAG_QA`, `SECTION_QUERY`, `FULL_DOCUMENT`, `GENERAL_KNOWLEDGE`, `COMPARISON`.  
**Domains:** `resume`, `jd`, `both`, `general`.

## 2.3 RAG pipeline (core demo — `_handle_rag_pipeline`)

Order in `query_router.py` (~280–420):

| Step | Component | Purpose |
|------|-----------|---------|
| 1 | `MetadataFilter.build_filters` | Scope by domain, entity, section from intent |
| 2 | `QueryExpander.expand` | Synonym / multi-query variations (`ENABLE_MULTI_QUERY`) |
| 3 | `VectorRetriever.retrieve` + `KeywordRetriever.retrieve` | Semantic + lexical hits per variation |
| 4 | `RRFFusion.fuse` | Merge ranked lists (RRF_K in settings) |
| 5 | `Reranker.rerank` | Cross-encoder style re-scoring |
| 5b | Relaxed filters | If too few chunks, drop section filter and retry |
| 6 | `ContextBuilder.build_context` | Prompt-ready context + conversation history |
| 7 | `RAGAnswerGenerator.generate` | Grounded LLM answer + validation |
| 8 | Format sources / confidence | Returned to API → `ChatResponse` |

**Config knobs:** `apps/quantchat/config/settings.py` — chunk limits, RRF, rerank, `MAX_CONTEXT_TOKENS`, `ENABLE_OBSERVABILITY`, fallbacks (`ENABLE_FALLBACKS`, `FALLBACK_TO_CHUNKS`).

## 2.4 Response generation & safety

`rag_generator.py`:

- Builds intent-specific prompts (`_build_rag_prompt`, section, full-doc)  
- **`LLMGenerator.generate`** with low temperature (~0.2)  
- **`_validate_response`** — entities/numbers vs context  
- On LLM failure → **`_fallback_response`** (context summary, low confidence)

## 2.5 What to demo live (if NPD/local up)

1. Open `query_router.py` → `_handle_rag_pipeline`  
2. Ask QuantChat a **named candidate** question (RAG) vs a **general** question (non-RAG)  
3. Show `processing_method` in UI (`VERIFIED_RAG::...`) from `quantchat.py`

---

# 3. Agentic workflows (20 min)

Use **`docs/agentic-systems-quick-reference.md`** for line numbers. Summary:

## 3.1 JD generation — LangGraph + crew

| Stage | Where | Decision logic |
|-------|--------|----------------|
| API | `jd_generation.py` → `_execute_jd_generation_core` | HR context merged; `asyncio.to_thread(orchestrator.generate_job_description)` |
| Orchestrator | `jd_generation/orchestrator.py` | Validates inputs, invokes workflow |
| Graph | `state_machine.py` — `generate_jd` → `refine_jd` → `validate_jd` | State machine transitions; crew agents do LLM work |
| HR overlay | `_apply_hr_inputs_to_jd` | Business fields not left to model alone |
| Persist | `jd_pipeline_service.store_jd` | Job row + vectors |

**Async:** in-memory task registry (`jd_generation_tasks.py`) + poll — not Celery on NPD.

**Talking point:** Graph = **control flow**; `JDGeneratorAgent` / refiner / validator = **prompted LLM steps**.

## 3.2 Resume parsing — pipeline agent

| Stage | Where | Decision logic |
|-------|--------|----------------|
| Extract | `pdf_extraction.extract_resume_text` | DI first, local PDF/DOCX fallbacks |
| Parse | `ParsingAgent.execute` | Structured JSON from text |
| Store | `resume_pipeline_service.parse_and_store` | Upsert candidate, `add_resume` vectors |

No multi-agent debate — single **enterprise parsing agent** with validation/retries via `BaseAgent.run_with_tracking`.

## 3.3 Job matching — HSS-D swarm + debate

| Layer | Where | How decision is reached |
|-------|--------|---------------------------|
| Data | `data_access_pg.get_candidate_pg` / `get_jd_pg` | Load profiles from Postgres/chunks |
| Swarm | `_run_swarm` + `BaseSpecialistAgent.run` | Parallel dimension scores (skills, experience, …) |
| Verify | `EvidenceVerifier` (optional) | Strip fabricated quotes — **deterministic**, no LLM |
| Governance | `BiasAgent` (optional) | Audit narrative |
| Debate | `_run_debate`: Synthesizer → Critic → Arbitrator | Iterative narrative + final fit |
| Output | `MatchResult` | Weighted dimensions + arbitrator conclusion |

**SSE:** `match_stream` exposes **agent thoughts** for the UI (`JobMatchingPageContent` + `useMatchStream`).

---

# 4. Model & prompt configuration (10 min)

## 4.1 Single factory (all agents + QuantChat LLM paths)

**File:** `apps/agents/agents/llm/chat_factory.py` — **`create_chat_llm`** (~211)

| Env | Provider |
|-----|----------|
| `LLM_PROVIDER=azure_openai` | Azure OpenAI deployments (NPD default when `DEPLOYMENT_TARGET=azure-nonprod`) |
| `LLM_PROVIDER=openai` | OpenAI API |
| `LLM_PROVIDER=vertexai` / `google` | Vertex AI (`GCP_PROJECT_ID`, ADC) |

Related env: `LLM_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_FAST_MODEL`, `AZURE_OPENAI_*`, `OPENAI_API_KEY`.

**Rule:** Production/NPD should get secrets from **env/Key Vault**, not hardcoded. `ensure_llm_env()` loads project `.env` with **`override=False`** so K8s env wins.

## 4.2 QuantChat-specific LLM settings

`apps/quantchat/config/settings.py` reads the same provider env; **`LLMGenerator`** used for intent, expansion, and generation in QuantChat.

## 4.3 Fallback behaviour (layers)

| Layer | Behaviour |
|-------|-----------|
| Intent | `_fallback_classify` regex if LLM unavailable |
| Retrieval | Empty hits → user message “rephrase”; relaxed metadata filters |
| RAG generate | LLM exception → chunk summary fallback |
| JD / agents | `ErrorRecovery` / retries in JD state machine; matching config timeouts |
| Provider | `chat_factory` raises if Azure not configured; API returns 503 on router init failure |

**Prompts:** Embedded in agent modules (`crew_agents.py`, `rag_generator.py`, `swarm_agents.py`, `debate_agents.py`) — no single central prompt registry yet; grep by agent name when changing behaviour.

---

# 5. Evaluation approach (10 min)

## 5.1 QuantChat — automatic (online, heuristic)

**`RAGEvaluator`** in `agent_observability.py`:

- **Faithfulness** — numbers/entities in answer vs context; hedging phrases penalized  
- **Relevance** — query/response term overlap  
- **Groundedness** — sentence-level support in context  

Runs inside **`complete_trace`** when `source` is RAG and not cached/error — **no extra LLM judge call**.

**Also:** `rag_generator._validate_response` at generation time; confidence capped on failure signals.

## 5.2 QuantChat — user feedback (designed, partially wired)

| Piece | Status |
|-------|--------|
| `AgentObservabilityManager.record_feedback(trace_id, rating, comment)` | Implemented in-process |
| `api.observability.submitFeedback` in `apps/web/src/lib/api.ts` | Client stub |
| `POST /v1/quantchat/feedback` + observability REST routes | **Not mounted** in `quantchat.py` today |
| `ai_chat` returns `obs_trace_id` | **No** — UI cannot link thumbs to trace yet |

**Hiring feedback (separate product loop):** `apps/api/app/api/v1/feedback.py` + **`FeedbackAgent`** — recruiter outcomes, match accuracy, drift analysis (`POST /feedback`, analyze with ≥5 records). This is **not** QuantChat chat thumbs.

## 5.3 Job matching — quality gates

- **Evidence verifier** — grounded quotes only  
- **Bias audit** — optional narrative check  
- **Debate** — critic challenges synthesizer before arbitrator  

## 5.4 JD / resume

- JD: **`validate_jd`** graph node + validator agents  
- Resume: **Pydantic `ParsedResume`** validation + completeness enrichment in pipeline  

**Talking point:** Evaluation today is **mostly heuristics + human hiring feedback**, not offline eval suites in CI — room for Farhaan to add LangSmith datasets / golden questions.

---

# 6. Observability (10 min)

## 6.1 In-process QuantChat observability

When `ENABLE_OBSERVABILITY=true` (`settings.py`):

**`AgentObservabilityManager`** tracks per query:

- Step latencies (normalize, intent, retrieval, RRF, rerank, context, LLM)  
- Retrieval counts, LLM calls, **estimated USD cost**  
- Intent audit trail  
- **Alerts** (latency, quality drop, error rate, hourly cost) — optional webhook  
- In-memory trace ring buffer (`OBSERVABILITY_MAX_TRACES`)  
- **Prometheus-style metrics** export helper in same module  

Logs: `logger.info` on trace complete with latency, confidence, cost, quality scores.

## 6.2 LangSmith / tracing decorators

**`@traceable`** on QueryRouter, retrievers, intent classifier (`quantchat/utils/tracing.py`).  
JD orchestrator optional LangSmith client.  
Controlled by env: `LANGCHAIN_TRACING_V2`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.

## 6.3 API-level visibility today

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/quantchat/status` | QueryRouter component health |
| `GET /api/health` | Includes quantchat path hint |
| Application logs | API + uvicorn + agent loggers |

**Gap:** Frontend **`api.observability.*`** expects `/v1/quantchat/observability/*` — implement by exposing `router.observability.get_dashboard()` (and siblings) from a new FastAPI router when building dashboards.

## 6.4 Platform / infra (mention only)

- K8s logs: `kubectl logs` on `quanthire-backend`  
- Azure Monitor / App Insights if wired at deploy (team-specific)  
- No separate QuantChat microservice to trace — spans are inside API pods  

---

# 7. Engineering gaps & good first tasks (5 min)

Be explicit — builds trust:

1. **Wire observability HTTP API** to `AgentObservabilityManager` (dashboard, feedback submit, export traces).  
2. **Return `obs_trace_id`** from `ai_chat` + thumbs in QuantChat UI.  
3. **Persist conversation history** (Redis/Postgres) instead of API in-memory dict.  
4. **Eval harness:** golden QuantChat questions + expected entity hits; JD JSON schema tests; matching fixture pairs.  
5. **Prompt registry / versioning** for crew and RAG prompts.

---

# 8. One-page cheat sheet (for your notes)

| System | Orchestration | “Decision” |
|--------|---------------|------------|
| QuantChat | `QueryRouter.route_query` | Intent branch + RAG scores + LLM with context validation |
| JD | LangGraph `state_machine.run` | Generate → refine → validate + HR stamp |
| Resume | `parse_and_store` | Single parsing agent JSON + DB/vector ingest |
| Matching | `JobMatchingOrchestrator.amatch` | Swarm scores → debate → arbitrator |

| Config | File |
|--------|------|
| LLM provider | `chat_factory.py`, `app/config.py`, `.env` |
| RAG limits | `quantchat/config/settings.py` |
| Observability toggles | `ENABLE_OBSERVABILITY`, `OBSERVABILITY_*` env |

| Evaluation | Where |
|------------|--------|
| RAG quality (auto) | `RAGEvaluator` in `complete_trace` |
| Chat user feedback | `record_feedback` (needs API + UI) |
| Hiring feedback | `/api/v1/feedback` + `FeedbackAgent` |

---

# 9. Suggested closing Q&A prompts

- “Where would you add a new intent type?” → `Intent` enum + classifier prompt + `route_query` branch.  
- “Where would you change retrieval?” → retrievers + `pgvector_ingestion` visibility clauses.  
- “How do we swap model on NPD?” → `AZURE_OPENAI_CHAT_DEPLOYMENT` / `LLM_MODEL`, redeploy API.  
- “Why hybrid vector + keyword?” → recall: semantic misses exact IDs/titles; keyword misses paraphrases; RRF merges both.

---

**Presenter reminder:** You own the **design and implementation story**; frame as team platform where others contribute infra and HR policy. Point to repo docs and `agentic-systems-quick-reference.md` for deep code dives.
