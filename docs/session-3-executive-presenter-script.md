# Session 3 — Executive presenter script (AI, agents & observability)

**Use this as your spoken script** for Session 3 KT.  
**Companion (keep open):** `docs/session-3-quick-reference.md` for line numbers · `docs/session-3-ai-components-complete.md` for depth.

**Goal:** Farhaan (and the team) leave knowing **where AI runs**, **how decisions are made**, and **how we measure and observe quality**.

---

## Pre-session (5 minutes)

**Verify (silent checklist):**

- [ ] IDE repo open at `apps/quantchat/core/query_router.py` and `state_machine.py`
- [ ] Tab: `docs/session-3-quick-reference.md`
- [ ] Optional: NPD QuantChat or job-matching page for a 2-minute live ping

**Mindset:** You are explaining **systems you built or own**, not reading a manual.

---

## OPENING (2 minutes)

**Script:**

“Welcome to **Session 3: AI components, agentic workflows, and observability**.

Sessions 1 and 2 covered **architecture** and **code layout**. Today we go **inside the AI**: how **QuantChat** routes and retrieves answers, how **JD generation**, **resume parsing**, and **job matching** orchestrate agents, how **models are configured**, how we **evaluate quality**, and what **observability** exists today — including what’s **not wired yet** so you know where to extend.

Everything runs **in the FastAPI process** — agents and QuantChat are **libraries**, not separate microservices on Non-Prod.

I’ll follow the official agenda. **Stop me for questions**, but I’ll save deep dives for the end.

Let’s start with the **one picture** of how AI is organized in this repo.”

---

## BLOCK 1 — Map (5 minutes)

**Script:**

“Open `apps/` mentally as four AI zones:

1. **`quantchat`** — read path only. **One** `QueryRouter`. All chat RAG goes here.  
2. **`agents/agents/jd_generation`** — LangGraph workflow + crew LLM steps.  
3. **`agents/agents/parsing`** — resume structured extract.  
4. **`agents/agents/job_matching`** — swarm plus debate.

The API layer is thin: `quantchat.py`, `jd_generation.py`, `resume_parsing.py`, `job_matching.py` — they **call** these modules.

**Every LLM** should go through **`create_chat_llm`** in `chat_factory.py` line **211**. That’s our provider switch: Azure OpenAI on NPD, OpenAI or Vertex locally.

**Data:** Postgres plus **pgvector** for chunks. Ingestion on write; QuantChat reads those chunks on query.

**[Show quick reference § Flow at a glance]**”

---

## BLOCK 2 — QuantChat (18 minutes)

**Script:**

“QuantChat is **not** a separate service. The browser hits **`ai_chat`** — line **90** in `quantchat.py`. That function:

- Resolves the **QueryRouter singleton** via `ensure_query_router`.  
- Binds **conversation history** to the **authenticated user id** — we don’t trust client-supplied user ids when auth is on.  
- Runs **`route_query`** in a **worker thread** so a long RAG call doesn’t block health checks.

Jump to **`route_query`** line **109** in `query_router.py`.

**Step 1 — Understand the query:** normalize, pull **conversation history** and **tracked entities**, enhance the query.

**Step 2 — Intent:** **`classify`** line **94** in `intent_classifier.py`. Intents include **RAG**, **section query**, **full document**, **general knowledge**, and **comparison**. If the LLM is down, **`_fallback_classify`** at **210** uses regex — that’s an important fallback to mention.

**Step 3 — Branch.** Most HR questions hit **`_handle_rag_pipeline`** line **280**. That’s the demo spine.

Walk the RAG pipeline in order — this is the agenda item on **retrieval, fusion, reranking, context, generation**:

1. **Metadata filters** from intent — resume vs JD, entity names, sections.  
2. **Query expansion** — multiple query variations for recall.  
3. **Vector retrieve** line **85** and **keyword retrieve** line **59** — **both**, every variation.  
4. **RRF fuse** line **33** — reciprocal rank fusion. Neither vector nor keyword alone is enough for names and skills.  
5. **Rerank** line **51**.  
6. If we’re starved for chunks, **relaxed filters** and retry.  
7. **`build_context`** line **65** — includes conversation history.  
8. **`RAGAnswerGenerator.generate`** line **28** — grounded prompt, low temperature, **`_validate_response`** against context.

If generation fails, we have a **fallback response** from context — not a silent hallucination.

**Other branches** for completeness: general knowledge **509**, full document **452**, comparison **532**.

**Invariant for engineers:** do **not** add a second RAG path in product code. Writes go through ingestion; reads go through QueryRouter.

**[Optional live:** one QuantChat question on a known candidate.]”

---

## BLOCK 3 — JD generation (12 minutes)

**Script:**

“JD generation is **agentic workflow** plus **API truth**.

UI: **`handleGenerate`** line **451**. API core: **`_execute_jd_generation_core`** line **1240**. That calls the orchestrator and then **`_apply_hr_inputs_to_jd`** line **974** — salary, location, HR matrix fields are **not** left to the model alone.

The workflow engine is **`state_machine.py`**. Open **`_build_graph`** line **807** — nodes and edges.

The narrative nodes:

- **`generate_jd`** **371** — first draft  
- **`refine_jd`** **441**  
- **`validate_jd`** **516**  
- **`prepare_jd`** **636** — assigns **`job_id`**

Then **`_route_after_prepare`** line **852**. On **Azure Non-Prod**, we **skip** in-graph Milvus and embedding storage — persistence is **`store_jd`** line **157** in the API pipeline to **Postgres and pgvector**. That routing function is the key ‘why NPD behaves differently’ detail.

**`run`** line **863** executes the graph.

Async JD uses an **in-memory task table** — not Celery — poll status after **`generate_job_description_async`**.

**Decision logic:** validator node plus HR overlay plus graph routing for storage backend.”

---

## BLOCK 4 — Resume parsing (6 minutes)

**Script:**

“Resume is a **linear pipeline**, not a debate.

**`upload_resume`** **322** validates and extracts text via **`extract_resume_text`** **169**.

**`parse_and_store`** **60** calls the parsing agent through **`run_with_tracking`**, core logic in **`execute`** **262** — structured JSON.

Then **`add_resume`** **293** indexes chunks for QuantChat and matching.

**Decisions:** file validation at API, minimum text length at extraction, schema validation in the agent.”

---

## BLOCK 5 — Job matching (12 minutes)

**Script:**

“Matching is the most **visible** multi-agent flow because the UI streams **thoughts**.

**`match_stream`** line **283** — SSE. Orchestrator **`_run_swarm`** **389** runs **specialists in parallel** — skills, experience, and so on — each **`BaseSpecialistAgent.run`** **132**.

Then **`EvidenceVerifier.verify_swarm`** **330** — **deterministic** — strips quotes that aren’t in the resume or JD. Zero LLM cost.

Optional bias auditor, then **`_run_debate`** **493**: **Synthesizer**, **Critic**, **Arbitrator**. The **final hiring-style decision** is **`ArbitratorAgent.run`** **290**.

**JSON match** is the same pipeline via **`amatch`** on POST **`match`** **254**.

**Decision ladder:** specialists produce evidence → verifier grounds it → debate synthesizes conflict → arbitrator decides.”

---

## BLOCK 6 — Models, prompts, fallbacks (8 minutes)

**Script:**

“**Provider:** `llm_provider` line **80**, models via **`primary_llm_model`**, **`fallback_llm_model`** **109**, construction via **`create_chat_llm`** **211**.

NPD: **`LLM_PROVIDER=azure_openai`**, deployments from env. QuantChat reads **`LLM_MODEL`** in `quantchat/config/settings.py` line **89**.

**Prompts** live **inline** in crew agents, RAG generator, swarm and debate modules — there is no central prompt registry yet; that’s a good follow-up project.

**Fallback stack:**

- Intent regex fallback  
- Empty retrieval → user message  
- RAG LLM failure → context summary  
- JD graph skips legacy Milvus on Azure  

**LangSmith:** `@traceable` in `quantchat/utils/tracing.py` line **42** when tracing env vars are set.”

---

## BLOCK 7 — Evaluation & feedback (8 minutes)

**Script:**

“Two different ‘feedback’ loops — don’t mix them.

**QuantChat automatic quality:** on each RAG trace complete, **`RAGEvaluator.evaluate`** **227** scores **faithfulness, relevance, groundedness** — **heuristics**, no second LLM judge. Hooked in **`complete_trace`** **472**. Generation also runs **`_validate_response`** **111**.

**QuantChat user thumbs:** **`record_feedback`** **545** exists **in memory**, but we do **not** yet return **`obs_trace_id`** from **`ai_chat`** and we have **no REST route** — client stubs exist in `api.ts`. Conversation ‘feedback’ today is the **next user message** in history.

**Hiring feedback:** REST **`create_feedback`** **185** and **`analyze_feedback`** **358** with **`FeedbackAgent`** — match accuracy, drift — **Postgres**, separate from chat.

**JD/resume/matching:** validator nodes, Pydantic parse, evidence verifier — quality **gates**, not offline benchmarks yet.”

---

## BLOCK 8 — Observability (8 minutes)

**Script:**

“**In-process hub:** **`AgentObservabilityManager`**. **`start_trace`** **374**, step latencies, retrieval counts, **`record_llm_call`** for cost estimates, **`complete_trace`** **472** with quality scores and **INFO logs** at line **533**.

Aggregates: **`get_full_dashboard`** **1034**, performance, quality, cost helpers in the same file. Toggle **`ENABLE_OBSERVABILITY`** line **116**.

**API today:** **`get_quantchat_status`** **199** for router health. **Pod logs** in AKS for operations.

**Matching observability for users** is the **SSE thought stream** — that’s the product-facing ‘show your work’.

**Gap to implement:** mount **`/v1/quantchat/observability/*`** so the web **`observability.*`** client calls work. That’s a natural first PR for the new engineer.”

---

## CLOSING (3 minutes)

**Script:**

“Summary:

- **QuantChat** — one router, hybrid RAG, grounded generate.  
- **JD** — LangGraph plus HR API plus pgvector store.  
- **Resume** — parse agent plus ingest.  
- **Matching** — swarm, verify, debate, arbitrator.  
- **One LLM factory.**  
- **Quality** — heuristic RAG eval plus hiring feedback API.  
- **Obs** — rich in-process; REST dashboard wiring next.

Your cheat sheet is **`docs/session-3-quick-reference.md`**. Full line index is **`session-3-ai-components-complete.md`**.

What should we prioritize first on your side — observability routes, chat feedback, or eval fixtures?

Thank you.”

---

## Timeboxing cheat sheet

| Block | Min |
|-------|-----|
| Open + map | 7 |
| QuantChat | 18 |
| JD | 12 |
| Resume | 6 |
| Matching | 12 |
| LLM | 8 |
| Eval | 8 |
| Observability | 8 |
| Close | 3 |
| **Total** | **~82** (trim QuantChat to 12 if needed for 60 min) |

---

*End of Session 3 presenter script*
