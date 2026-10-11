# Session 3 — AI components, agentic workflows & observability (complete reference)

**QuantHire AI — KT Session 3**  
**Covers:** QuantChat (routing → RAG → generation), JD / resume / matching workflows, LLM configuration, evaluation & feedback, observability.  
**Line numbers:** verified against repo branch `cursor/jd-generation-architecture-doc-b100` (use IDE “Go to line”).  
**Companions:** `docs/agentic-systems-quick-reference.md`, `docs/session-3-ai-agents-observability-presenter-pack.md`

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)  
2. [QuantChat chatbot](#2-quantchat-chatbot)  
3. [Agentic workflows — JD generation](#3-agentic-workflows--jd-generation)  
4. [Agentic workflows — resume parsing](#4-agentic-workflows--resume-parsing)  
5. [Agentic workflows — job matching](#5-agentic-workflows--job-matching)  
6. [Model & prompt configuration](#6-model--prompt-configuration)  
7. [Evaluation & feedback](#7-evaluation--feedback)  
8. [Observability](#8-observability)  
9. [Gaps & engineering follow-ups](#9-gaps--engineering-follow-ups)  
10. [Suggested demo order (60–90 min)](#10-suggested-demo-order-6090-min)  
11. [Master symbol index (all tables combined)](#11-master-symbol-index-all-tables-combined)

**Table columns:** `Area` | `File` | `Function / symbol` | `Line` | `Brief`

---

## 1. Architecture overview

QuantHire AI runs **agents inside the FastAPI process**. QuantChat is a **read-only RAG pipeline** (`QueryRouter`). JD, resume, and matching are **write/workflow pipelines** invoked from versioned API routers.

```text
Browser → Next.js BFF → FastAPI
                           ├── quantchat.py      → QueryRouter (apps/quantchat)
                           ├── jd_generation.py  → JD orchestrator + LangGraph
                           ├── resume_parsing.py → ParsingAgent + pgvector ingest
                           └── job_matching.py   → JobMatchingOrchestrator
                           └── create_chat_llm() ← apps/agents/agents/llm/chat_factory.py
                           └── PostgreSQL + pgvector (NPD)
```

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Lifecycle | `apps/api/app/core/query_router_lifecycle.py` | `ensure_query_router` | 15 | Lazy singleton init; sets `QUERY_ROUTER_AVAILABLE` |
| Singleton | `apps/quantchat/__init__.py` | `get_query_router` | 37 | Returns process-wide `QueryRouter` instance |
| LLM factory | `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm` | 211 | Shared chat model for agents and QuantChat LLM paths |
| Config | `apps/api/app/config.py` | `Settings` | 11 | App env: auth, deployment target, Azure defaults, DB |

---

## 2. QuantChat chatbot

### 2.1 Narrative — end-to-end path

1. User message → **`POST /v1/quantchat/chat`** (`ai_chat`).  
2. API binds **user id** (JWT when enforced), appends to **in-memory** `conversation_histories`, syncs into **`ConversationMemory`**.  
3. **`route_query`** runs in **`asyncio.to_thread`** (blocking RAG/LLM off the event loop).  
4. **Normalize** query → load **conversation history** + **tracked entities** → **classify intent** (LLM or regex fallback).  
5. **Branch:** general knowledge | full document | comparison | **RAG pipeline** (default for HR Q&A).  
6. RAG: **filters** → **query expansion** → **vector + keyword** retrieval per variation → **RRF** → **rerank** → optional **relaxed filters** → **context build** → **RAG generate** + validation → format sources.  
7. **Memory** records turn; **observability** completes trace (latency, cost estimate, heuristic quality scores).

### 2.2 API & memory

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | 90 | Chat entry; ensures QueryRouter; thread pool for `route_query` |
| API | `apps/api/app/api/v1/quantchat.py` | `_sync_router_memory_from_api_history` | 43 | Hydrates router memory from API history after restart |
| API | `apps/api/app/api/v1/quantchat.py` | `get_quantchat_status` | 199 | Router / component health for ops |
| Frontend | `apps/web/src/components/QuantChat.tsx` | `processQuery` | 59 | POST chat message via BFF |
| Frontend | `apps/web/src/components/QuantChat.tsx` | `handleSubmit` | 133 | Form submit → `processQuery` |
| Memory | `apps/quantchat/memory/conversation_memory.py` | `get_history` | 81 | Formatted prior turns for classifier/context |
| Memory | `apps/quantchat/memory/conversation_memory.py` | `add_turn` | 39 | Stores user/assistant pair + entity tracking |

### 2.3 Query routing & branches

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Router | `apps/quantchat/core/query_router.py` | `QueryRouter.__init__` | 72 | Wires normalizer, retrievers, RRF, reranker, generators, observability |
| Router | `apps/quantchat/core/query_router.py` | `route_query` | 109 | Main orchestrator: cache, intent, branch, memory, metrics |
| Router | `apps/quantchat/core/query_router.py` | `_handle_rag_pipeline` | 280 | Hybrid retrieve → fuse → rerank → context → generate |
| Router | `apps/quantchat/core/query_router.py` | `_handle_full_document` | 452 | Full resume/JD document path |
| Router | `apps/quantchat/core/query_router.py` | `_handle_general_knowledge` | 509 | Non-RAG general LLM path |
| Router | `apps/quantchat/core/query_router.py` | `_handle_comparison` | 532 | Multi-entity comparison RAG |
| Router | `apps/quantchat/core/query_router.py` | `_handle_error` | 550 | User-safe error payload on pipeline failure |
| Normalizer | `apps/quantchat/core/query_normalizer.py` | `normalize` | 61 | Cleanup / normalize user text |
| Normalizer | `apps/quantchat/core/query_normalizer.py` | `enhance_with_context` | 101 | Inject tracked entities into query |

### 2.4 Intent classification

**Intents:** `RAG_QA`, `SECTION_QUERY`, `FULL_DOCUMENT`, `GENERAL_KNOWLEDGE`, `COMPARISON`.  
**Domains:** `resume`, `jd`, `both`, `general`.

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Intent | `apps/quantchat/core/intent_classifier.py` | `classify` | 94 | LLM classify with conversation context |
| Intent | `apps/quantchat/core/intent_classifier.py` | `_llm_classify` | 125 | LLM JSON intent + entities + section |
| Intent | `apps/quantchat/core/intent_classifier.py` | `_fallback_classify` | 210 | Regex/keyword fallback if LLM unavailable |
| Filters | `apps/quantchat/retrieval/metadata_filter.py` | `build_filters` | 42 | pgvector filters from intent (domain, entity, section) |
| Filters | `apps/quantchat/retrieval/metadata_filter.py` | `build_relaxed_filters` | 137 | Widen search when too few chunks |

### 2.5 Retrieval pipeline (vector, keyword, expansion)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Expansion | `apps/quantchat/retrieval/query_expander.py` | `expand` | 45 | Synonym / multi-query variations |
| Vector | `apps/quantchat/retrieval/vector_retriever.py` | `retrieve` | 85 | Embedding search (pgvector on NPD) |
| Keyword | `apps/quantchat/retrieval/keyword_retriever.py` | `retrieve` | 59 | Lexical / keyword search |
| PG backend | `apps/quantchat/retrieval/pgvector_retriever.py` | `retrieve` | 57 | Postgres pgvector implementation detail |
| Full doc | `apps/quantchat/retrieval/full_doc_retriever.py` | `retrieve_full_document` | 52 | Assemble full document for FULL_DOCUMENT intent |

### 2.6 Fusion & reranking

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Fusion | `apps/quantchat/fusion/rrf_fusion.py` | `fuse` | 33 | Reciprocal rank fusion of vector + keyword lists |
| Rerank | `apps/quantchat/reranking/reranker.py` | `rerank` | 51 | Re-score top fused chunks for query relevance |

**Settings (limits, RRF_K, rerank flags):** `apps/quantchat/config/settings.py` (e.g. `MAX_CHUNKS_PER_RETRIEVER`, `RRF_K`, `ENABLE_RERANKING`, `ENABLE_MULTI_QUERY`).

### 2.7 Context building & response generation

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Context | `apps/quantchat/context/context_builder.py` | `build_context` | 65 | Assemble prompt context + conversation history |
| RAG gen | `apps/quantchat/generation/rag_generator.py` | `generate` | 28 | Grounded answer; confidence + validation |
| RAG gen | `apps/quantchat/generation/rag_generator.py` | `_build_rag_prompt` | 206 | Prompt template for standard RAG |
| RAG gen | `apps/quantchat/generation/rag_generator.py` | `_validate_response` | 111 | Hallucination checks vs context |
| RAG gen | `apps/quantchat/generation/rag_generator.py` | `_fallback_response` | 350 | Context summary if LLM fails |
| LLM core | `apps/quantchat/generation/llm_generator.py` | `generate` | 55 | Low-level LLM call wrapper for QuantChat |
| General | `apps/quantchat/generation/general_generator.py` | `generate` | 28 | Non-RAG answers |
| Format | `apps/quantchat/generation/formatter.py` | `format_rag_response` | 20 | Final response shaping + sources |

### 2.8 QuantChat config & fallbacks

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Config | `apps/quantchat/config/settings.py` | `ENABLE_FALLBACKS` | 100 | Global fallback toggles |
| Config | `apps/quantchat/config/settings.py` | `ENABLE_OBSERVABILITY` | 116 | In-process AgentObservabilityManager |
| Config | `apps/quantchat/config/settings.py` | `LLM_MODEL` | 89 | Default model name for QuantChat LLM calls |
| Cache | `apps/quantchat/utils/cache.py` | (RAG result cache) | — | Exact-query cache for `session_id=default` in `route_query` |

---

## 3. Agentic workflows — JD generation

### 3.1 Narrative — orchestration & decisions

1. UI **`handleGenerate`** → async or sync JD API.  
2. **`_execute_jd_generation_core`** runs **`orchestrator.generate_job_description`** in a worker thread.  
3. **LangGraph** (`state_machine.run`) executes nodes: initialize → gather context → **generate → refine → validate** → customize → **prepare_jd** (assign `job_id`) → routing:  
   - **Azure / pgvector:** `_route_after_prepare` → **`complete`** (skip in-graph Milvus/embed).  
   - **Legacy local:** → **generate_embeddings** → **store_in_milvus** (often deferred) → complete.  
4. API applies **`_apply_hr_inputs_to_jd`** and **`store_jd`** (Postgres + pgvector on NPD).  
5. **Async:** `jd_generation_tasks` + `asyncio.create_task` (in-memory poll, not Celery).

**Decision points:** validator node quality gates; HR overlay overrides business fields; graph routing skips local vector storage when `should_skip_local_vector_storage()` (NPD).

### 3.2 API & async tasks

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `handleGenerate` | 451 | Validates HR matrix; async poll or sync generate |
| API | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description_async` | 1454 | 202 + task id |
| API | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description` | 1512 | Synchronous generate |
| API | `apps/api/app/api/v1/jd_generation.py` | `_run_async_generation_task` | 1420 | Background worker for async JD |
| API | `apps/api/app/api/v1/jd_generation.py` | `_execute_jd_generation_core` | 1240 | Orchestrator + HR merge + `store_jd` |
| API | `apps/api/app/api/v1/jd_generation.py` | `_apply_hr_inputs_to_jd` | 974 | Stamp salary, location, matrix fields |
| Tasks | `apps/api/app/services/jd_generation_tasks.py` | `create_task` | 53 | In-memory task registry (1h TTL) |
| Persist | `apps/api/app/services/jd_pipeline_service.py` | `store_jd` | 157 | Job row + JD vectors |

### 3.3 Orchestrator & crew (LLM steps)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Orchestrator | `apps/agents/agents/jd_generation/orchestrator.py` | `generate_job_description` | 118 | Validates input; invokes LangGraph `run` |
| Crew | `apps/agents/agents/jd_generation/crew_agents.py` | `JDGeneratorAgent.generate_jd` | 2378 | Primary JD section generation (LLM) |
| Crew | `apps/agents/agents/jd_generation/crew_agents.py` | `JDRefinerAgent.refine_jd` | 3286 | Refinement pass (LLM) |
| Crew | `apps/agents/agents/jd_generation/crew_agents.py` | `JDValidatorAgent.validate_jd` | 3891 | Validation pass (LLM) |

### 3.4 LangGraph workflow (`state_machine.py`)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `initialize_state` | 276 | Seed workflow state |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `gather_context` | 295 | Similar jobs / market context |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `generate_jd` | 371 | Generator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `refine_jd` | 441 | Refiner node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `validate_jd` | 516 | Validator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `customize_jd` | 598 | User edits / customization |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `prepare_jd` | 636 | Assign `job_id` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `generate_embeddings` | 666 | Local embedding step (legacy path) |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `store_in_milvus` | 748 | Deferred; NPD uses API `store_jd` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `complete_workflow` | 793 | Mark workflow complete |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_build_graph` | 807 | Nodes, edges, conditional routes |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_route_after_prepare` | 852 | Azure: skip Milvus → `complete` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `run` | 863 | Invoke compiled graph |

---

## 4. Agentic workflows — resume parsing

### 4.1 Narrative — orchestration & decisions

1. **`upload_resume`** validates file, optional Blob, **`extract_resume_text`**.  
2. **`parse_and_store`** calls **`ParsingAgent.run_with_tracking`** → core **`execute`** (structured JSON).  
3. Candidate upsert + **`add_resume`** (chunk + embed + pgvector).  
**Decision:** validation at upload (type/size), extraction (min text length), agent parse success, Pydantic resume schema.

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Frontend | `apps/web/src/components/ResumeUpload.tsx` | `uploadResume` | 145 | POST multipart to resume API |
| API | `apps/api/app/api/v1/resume_parsing.py` | `upload_resume` | 322 | Validate, extract, pipeline |
| Extract | `apps/api/app/services/pdf_extraction.py` | `extract_resume_text` | 169 | DI-first universal extraction |
| Pipeline | `apps/api/app/services/resume_pipeline_service.py` | `parse_and_store` | 60 | Agent + DB + vector ingest |
| Agent base | `apps/agents/agents/base/agent.py` | `run_with_tracking` | 208 | Retries, timeouts, audit wrapper |
| Agent | `apps/agents/agents/parsing/agent.py` | `execute` | 262 | LLM structured parse |
| Vectors | `apps/api/app/services/pgvector_ingestion.py` | `add_resume` | 293 | QuantChat/matching index write |

---

## 5. Agentic workflows — job matching

### 5.1 Narrative — orchestration & decisions

1. UI launches **`match_stream`** (SSE) or **`match`** (JSON).  
2. **`amatch`**: load candidate/JD → optional weight calibration → **`_run_swarm`** (parallel specialists) → **EvidenceVerifier** (deterministic quote check) → optional **BiasAuditor** → **`_run_debate`** (Synthesizer → Critic → Arbitrator) → insights / **`MatchResult`**.  
**Final decision:** **Arbitrator** with dimension scores + debate context; specialists only produce dimension evidence.

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Frontend | `apps/web/src/app/dashboard/job-matching/page.tsx` | `JobMatchingPageContent` | 93 | Starts stream via `useMatchStream` |
| API | `apps/api/app/api/v1/job_matching.py` | `match` | 254 | POST → `orchestrator.amatch` |
| API | `apps/api/app/api/v1/job_matching.py` | `match_stream` | 283 | GET SSE agent thoughts + result |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `amatch` | 228 | Full async pipeline |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `stream` | 265 | SSE event generator |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_swarm` | 389 | Parallel specialist agents |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_debate` | 493 | Synthesizer → Critic → Arbitrator |
| Data | `apps/agents/agents/job_matching/data_access_pg.py` | `get_candidate_pg` | 271 | Load candidate profile |
| Data | `apps/agents/agents/job_matching/data_access_pg.py` | `get_jd_pg` | 279 | Load JD / job opening |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `BaseSpecialistAgent.run` | 132 | One dimension score + rationale |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `build_swarm` | 553 | Factory for specialists + risk + bias |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `BiasAuditorAgent.run` | 484 | Bias audit before debate |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `SynthesizerAgent.run` | 95 | Draft match narrative |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `CriticAgent.run` | 204 | Challenge synthesis |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `ArbitratorAgent.run` | 290 | Final fit decision |
| Verify | `apps/agents/agents/job_matching/evidence_verifier.py` | `verify_swarm` | 330 | Strip ungrounded evidence quotes |

---

## 6. Model & prompt configuration

### 6.1 Provider setup (NPD vs local)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Env load | `apps/agents/agents/llm/chat_factory.py` | `ensure_llm_env` | 63 | Load `.env` without overriding K8s env |
| Provider | `apps/agents/agents/llm/chat_factory.py` | `llm_provider` | 80 | `openai` \| `azure_openai` \| `vertexai` |
| Model | `apps/agents/agents/llm/chat_factory.py` | `primary_llm_model` | 94 | Primary model/deployment name |
| Model | `apps/agents/agents/llm/chat_factory.py` | `fallback_llm_model` | 109 | Fallback model env |
| Model | `apps/agents/agents/llm/chat_factory.py` | `fast_llm_model` | 85 | Lower-latency model tier |
| Azure | `apps/agents/agents/llm/chat_factory.py` | `_build_azure_chat_openai` | 175 | Azure OpenAI chat client |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm` | 211 | Unified constructor (json_mode, retries) |
| Health | `apps/agents/agents/llm/chat_factory.py` | `llm_status` | 283 | Runtime LLM config snapshot |
| App defaults | `apps/api/app/config.py` | `llm_provider_from_env` | 218 | NPD defaults to `azure_openai` |

**QuantChat** reads the same provider via `apps/quantchat/config/settings.py` (`LLM_MODEL`, `LLM_PROVIDER`).

### 6.2 Prompts & fallback behaviour

| Mechanism | Where | Behaviour |
|-----------|--------|-----------|
| JD prompts | `crew_agents.py`, `state_machine.py` | Large inline system/role prompts per crew agent |
| RAG prompts | `rag_generator.py` (`_build_*_prompt`) | Intent-specific grounded prompts |
| Matching prompts | `swarm_agents.py`, `debate_agents.py` | Dimension and debate role prompts |
| Intent fallback | `intent_classifier._fallback_classify` | Regex when LLM missing |
| Empty retrieval | `query_router._handle_rag_pipeline` | User message to rephrase; relaxed filters |
| RAG LLM failure | `rag_generator._fallback_response` | Return context excerpt, low confidence |
| JD embedding failure | `state_machine.generate_embeddings` | Zero-vector fallback for legacy Milvus path |
| Graph routing | `_route_after_prepare` | Skip embed/Milvus when pgvector API stores JD |

### 6.3 Tracing decorators (LangSmith)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Tracing | `apps/quantchat/utils/tracing.py` | `traceable` | 42 | LangSmith span decorator |
| Tracing | `apps/quantchat/utils/tracing.py` | `trace_metadata` | 62 | Attach metadata to active trace |

Enable via `LANGCHAIN_TRACING_V2`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.

---

## 7. Evaluation & feedback

### 7.1 QuantChat — automatic RAG quality (online)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Evaluator | `apps/quantchat/monitoring/agent_observability.py` | `RAGEvaluator.evaluate` | 227 | Faithfulness, relevance, groundedness (heuristic) |
| Hook | `apps/quantchat/monitoring/agent_observability.py` | `complete_trace` | 472 | Runs evaluator on RAG responses; sets hallucination_risk |
| Generation | `apps/quantchat/generation/rag_generator.py` | `_validate_response` | 111 | Pre-response validation vs context |

**No extra LLM judge** for eval in the hot path — suitable for real-time alerts.

### 7.2 QuantChat — user feedback (chat)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| In-process | `apps/quantchat/monitoring/agent_observability.py` | `record_feedback` | 545 | Attach rating/comment to trace id |
| Summary | `apps/quantchat/monitoring/agent_observability.py` | `get_feedback_summary` | 848 | Aggregate thumbs stats |
| Client (planned) | `apps/web/src/lib/api.ts` | `observability.submitFeedback` | 320 | POST `/v1/quantchat/feedback` — **API route not mounted yet** |
| Gap | `apps/api/app/api/v1/quantchat.py` | `ai_chat` response | 173 | Does not return `obs_trace_id` for UI feedback |

**Conversation “feedback”** today = **next user message** in `conversation_histories` / `ConversationMemory` (not thumbs).

### 7.3 Hiring feedback (match quality loop — separate from chat)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/api/app/api/v1/feedback.py` | `create_feedback` | 185 | Persist recruiter hiring feedback |
| API | `apps/api/app/api/v1/feedback.py` | `analyze_feedback` | 358 | Drift analysis via FeedbackAgent (≥5 records) |
| Agent | `apps/agents/agents/feedback/agent.py` | `FeedbackAgent` | 94 | Model drift / retraining recommendations |
| Agent | `apps/agents/agents/feedback/agent.py` | `execute` | 121 | Batch analysis entry |
| Model | `apps/api/app/models/feedback.py` | `Feedback` | 18 | DB schema for outcomes + ratings |

### 7.4 JD / resume / matching quality gates

| System | Mechanism | File / symbol |
|--------|-----------|----------------|
| JD | Validator graph node + crew validator | `validate_jd` L516; crew L3891 |
| Resume | Pydantic `ParsedResume` in parsing agent | `parsing/agent.py` `execute` |
| Matching | Evidence verifier + debate critic | `evidence_verifier.verify_swarm`; `CriticAgent.run` |

---

## 8. Observability

### 8.1 QuantChat in-process observability

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Hub | `apps/quantchat/monitoring/agent_observability.py` | `AgentObservabilityManager` | 326 | Traces, eval, cost, alerts, feedback log |
| Trace start | `apps/quantchat/monitoring/agent_observability.py` | `start_trace` | 374 | Per-query trace id |
| Intent audit | `apps/quantchat/monitoring/agent_observability.py` | `record_intent` | 400 | Pipeline route + entities |
| Retrieval | `apps/quantchat/monitoring/agent_observability.py` | `record_retrieval` | 418 | Chunk counts per stage |
| LLM cost | `apps/quantchat/monitoring/agent_observability.py` | `record_llm_call` | 443 | Token/cost estimates |
| Latency | `apps/quantchat/monitoring/agent_observability.py` | `record_step_latency` | 465 | Step timings (normalize, RRF, etc.) |
| Alerts | `apps/quantchat/monitoring/agent_observability.py` | `_check_alerts` | 585 | Latency/quality/cost thresholds |
| Dashboard data | `apps/quantchat/monitoring/agent_observability.py` | `get_full_dashboard` | 1034 | Aggregated dashboard payload |
| Performance | `apps/quantchat/monitoring/agent_observability.py` | `get_performance_metrics` | 704 | Latency percentiles |
| Quality | `apps/quantchat/monitoring/agent_observability.py` | `get_quality_metrics` | 729 | Faithfulness/relevance aggregates |
| Cost | `apps/quantchat/monitoring/agent_observability.py` | `get_cost_metrics` | 768 | Estimated spend |
| Decisions | `apps/quantchat/monitoring/agent_observability.py` | `get_agent_decisions` | 805 | Intent routing audit log |
| Prometheus | `apps/quantchat/monitoring/agent_observability.py` | `get_prometheus_metrics` | 976 | Metrics text export |
| Health | `apps/quantchat/monitoring/agent_observability.py` | `get_health` | 940 | Observability subsystem health |
| Legacy monitor | `apps/quantchat/monitoring/rag_monitor.py` | `track_query` | 25 | Simpler RAG metrics if observability off |

**Env toggles:** `ENABLE_OBSERVABILITY`, `OBSERVABILITY_*` in `apps/quantchat/config/settings.py` (lines 116–130).

### 8.2 System logs & API visibility

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| QuantChat logs | `apps/quantchat/config/logging_config.py` | `setup_logger` | 6 | Module loggers (`query_router`, etc.) |
| Trace complete log | `apps/quantchat/monitoring/agent_observability.py` | `complete_trace` | 533 | INFO: latency, confidence, cost, quality |
| API logging | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | 112 | Request id + user + query prefix |
| Health | `apps/api/app/api/health.py` | (quantchat path) | 44 | Documents chat route |

### 8.3 Dashboards (UI vs backend)

| Layer | Status | Notes |
|-------|--------|-------|
| `AgentObservabilityManager.get_full_dashboard()` | **Implemented** in Python | In-memory on API pod |
| `apps/web/src/lib/api.ts` `observability.*` | **Client defined** | Expects `/v1/quantchat/observability/*` |
| FastAPI routes for observability | **Not mounted** in `quantchat.py` | Wire manager methods to REST for UI |
| K8s / Azure Monitor | **Platform** | Pod logs + team APM configuration |
| LangSmith | **Optional** | `@traceable` on router, retrievers, JD orchestrator |

### 8.4 Job matching observability (UX)

Live **agent thoughts** stream to the dashboard via SSE (`match_stream` + `AgentThought` events) — primary “observability” for matching for HR users.

---

## 9. Gaps & engineering follow-ups

1. Mount **observability REST** on FastAPI → expose `get_full_dashboard`, feedback, export traces.  
2. Return **`obs_trace_id`** from `ai_chat`; add thumbs in QuantChat UI → `record_feedback`.  
3. Persist **conversation_histories** (Redis/DB).  
4. Offline **eval datasets** (golden QuantChat queries, JD schema tests, matching fixtures).  
5. Central **prompt registry** / versioning for crew and RAG prompts.

---

## 10. Suggested demo order (60–90 min)

| Step | Show | Message |
|------|------|---------|
| 1 | `query_router.route_query` + `_handle_rag_pipeline` | Single RAG pipeline invariant |
| 2 | Intent classify + vector/keyword/RRF/rerank lines | Why hybrid retrieval |
| 3 | `rag_generator.generate` + `_validate_response` | Grounding + confidence |
| 4 | `state_machine._build_graph` + `_route_after_prepare` | JD control flow + NPD storage skip |
| 5 | `orchestrator._run_swarm` + `_run_debate` | Matching decision ladder |
| 6 | `chat_factory.create_chat_llm` | One factory for all agents |
| 7 | `complete_trace` + `RAGEvaluator.evaluate` | Quality without LLM judge |
| 8 | `feedback.py` vs chat feedback gap | Two feedback loops |

---

## 11. Master symbol index (all tables combined)

Sorted by **Area**, then **Line**. Use as a single cheat sheet for IDE navigation.

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Agent | `apps/agents/agents/parsing/agent.py` | `execute` | 262 | Resume LLM parse |
| Agent base | `apps/agents/agents/base/agent.py` | `run_with_tracking` | 208 | Retries/timeouts wrapper |
| API | `apps/api/app/api/v1/feedback.py` | `create_feedback` | 185 | Hiring feedback persist |
| API | `apps/api/app/api/v1/feedback.py` | `analyze_feedback` | 358 | Drift analysis |
| API | `apps/api/app/api/v1/jd_generation.py` | `_apply_hr_inputs_to_jd` | 974 | HR field overlay |
| API | `apps/api/app/api/v1/jd_generation.py` | `_execute_jd_generation_core` | 1240 | JD core execution |
| API | `apps/api/app/api/v1/jd_generation.py` | `_run_async_generation_task` | 1420 | Async JD background task |
| API | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description_async` | 1454 | Async JD 202 |
| API | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description` | 1512 | Sync JD |
| API | `apps/api/app/api/v1/job_matching.py` | `match` | 254 | JSON match |
| API | `apps/api/app/api/v1/job_matching.py` | `match_stream` | 283 | SSE match |
| API | `apps/api/app/api/v1/quantchat.py` | `_sync_router_memory_from_api_history` | 43 | Memory hydrate |
| API | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | 90 | QuantChat entry |
| API | `apps/api/app/api/v1/quantchat.py` | `get_quantchat_status` | 199 | Router status |
| API | `apps/api/app/api/v1/resume_parsing.py` | `upload_resume` | 322 | Resume upload |
| Config | `apps/api/app/config.py` | `Settings` | 11 | Global settings |
| Context | `apps/quantchat/context/context_builder.py` | `build_context` | 65 | RAG context assembly |
| Crew | `apps/agents/agents/jd_generation/crew_agents.py` | `JDGeneratorAgent.generate_jd` | 2378 | JD generate LLM |
| Crew | `apps/agents/agents/jd_generation/crew_agents.py` | `JDRefinerAgent.refine_jd` | 3286 | JD refine LLM |
| Crew | `apps/agents/agents/jd_generation/crew_agents.py` | `JDValidatorAgent.validate_jd` | 3891 | JD validate LLM |
| Data | `apps/agents/agents/job_matching/data_access_pg.py` | `get_candidate_pg` | 271 | Load candidate |
| Data | `apps/agents/agents/job_matching/data_access_pg.py` | `get_jd_pg` | 279 | Load JD |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `SynthesizerAgent.run` | 95 | Match synthesis |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `CriticAgent.run` | 204 | Critique synthesis |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `ArbitratorAgent.run` | 290 | Final decision |
| Eval | `apps/agents/agents/feedback/agent.py` | `FeedbackAgent` | 94 | Hiring feedback agent |
| Eval | `apps/agents/agents/feedback/agent.py` | `execute` | 121 | Feedback analysis run |
| Eval | `apps/quantchat/monitoring/agent_observability.py` | `RAGEvaluator.evaluate` | 227 | RAG heuristic scores |
| Extract | `apps/api/app/services/pdf_extraction.py` | `extract_resume_text` | 169 | Resume text extract |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `ensure_llm_env` | 63 | Load env |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `llm_provider` | 80 | Provider selection |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `fast_llm_model` | 85 | Fast model tier |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `primary_llm_model` | 94 | Primary model |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `fallback_llm_model` | 109 | Fallback model |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `_build_azure_chat_openai` | 175 | Azure client |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm` | 211 | Create chat LLM |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `llm_status` | 283 | LLM health dict |
| Feedback | `apps/quantchat/monitoring/agent_observability.py` | `record_feedback` | 545 | Chat feedback on trace |
| Feedback | `apps/quantchat/monitoring/agent_observability.py` | `get_feedback_summary` | 848 | Feedback aggregates |
| Filters | `apps/quantchat/retrieval/metadata_filter.py` | `build_filters` | 42 | Intent filters |
| Filters | `apps/quantchat/retrieval/metadata_filter.py` | `build_relaxed_filters` | 137 | Relaxed search |
| Format | `apps/quantchat/generation/formatter.py` | `format_rag_response` | 20 | Format RAG answer |
| Frontend | `apps/web/src/components/QuantChat.tsx` | `processQuery` | 59 | Send chat |
| Frontend | `apps/web/src/components/QuantChat.tsx` | `handleSubmit` | 133 | Chat form |
| Frontend | `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `handleGenerate` | 451 | JD generate UI |
| Frontend | `apps/web/src/components/ResumeUpload.tsx` | `uploadResume` | 145 | Resume upload UI |
| Frontend | `apps/web/src/app/dashboard/job-matching/page.tsx` | `JobMatchingPageContent` | 93 | Matching UI |
| Fusion | `apps/quantchat/fusion/rrf_fusion.py` | `fuse` | 33 | RRF fusion |
| General | `apps/quantchat/generation/general_generator.py` | `generate` | 28 | General answers |
| Intent | `apps/quantchat/core/intent_classifier.py` | `classify` | 94 | Intent entry |
| Intent | `apps/quantchat/core/intent_classifier.py` | `_llm_classify` | 125 | LLM intent |
| Intent | `apps/quantchat/core/intent_classifier.py` | `_fallback_classify` | 210 | Regex fallback |
| Keyword | `apps/quantchat/retrieval/keyword_retriever.py` | `retrieve` | 59 | Keyword retrieval |
| Lifecycle | `apps/api/app/core/query_router_lifecycle.py` | `ensure_query_router` | 15 | Init QueryRouter |
| LLM | `apps/quantchat/generation/llm_generator.py` | `generate` | 55 | QuantChat LLM call |
| Memory | `apps/quantchat/memory/conversation_memory.py` | `add_turn` | 39 | Save turn |
| Memory | `apps/quantchat/memory/conversation_memory.py` | `get_history` | 81 | Read history |
| Normalizer | `apps/quantchat/core/query_normalizer.py` | `normalize` | 61 | Normalize query |
| Normalizer | `apps/quantchat/core/query_normalizer.py` | `enhance_with_context` | 101 | Entity enhancement |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `start_trace` | 374 | Begin trace |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `record_intent` | 400 | Log routing decision |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `record_retrieval` | 418 | Retrieval stats |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `record_llm_call` | 443 | LLM usage/cost |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `record_step_latency` | 465 | Step timing |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `complete_trace` | 472 | Finish + evaluate |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `_check_alerts` | 585 | Threshold alerts |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `get_performance_metrics` | 704 | Perf dashboard |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `get_quality_metrics` | 729 | Quality dashboard |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `get_cost_metrics` | 768 | Cost dashboard |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `get_agent_decisions` | 805 | Intent audit list |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `get_health` | 940 | Obs health |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `get_prometheus_metrics` | 976 | Prometheus export |
| Observability | `apps/quantchat/monitoring/agent_observability.py` | `get_full_dashboard` | 1034 | Full dashboard JSON |
| Observability | `apps/quantchat/monitoring/rag_monitor.py` | `track_query` | 25 | Legacy RAG monitor |
| Orchestrator | `apps/agents/agents/jd_generation/orchestrator.py` | `generate_job_description` | 118 | JD entry |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `amatch` | 228 | Match pipeline |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `match` | 256 | Sync wrapper |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `stream` | 265 | SSE stream |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_swarm` | 389 | Specialist swarm |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_debate` | 493 | Debate chain |
| Persist | `apps/api/app/services/jd_pipeline_service.py` | `store_jd` | 157 | Save JD + vectors |
| Persist | `apps/api/app/services/pgvector_ingestion.py` | `add_resume` | 293 | Index resume |
| Pipeline | `apps/api/app/services/resume_pipeline_service.py` | `parse_and_store` | 60 | Resume pipeline |
| RAG gen | `apps/quantchat/generation/rag_generator.py` | `generate` | 28 | Grounded generation |
| RAG gen | `apps/quantchat/generation/rag_generator.py` | `_validate_response` | 111 | Answer validation |
| RAG gen | `apps/quantchat/generation/rag_generator.py` | `_build_rag_prompt` | 206 | RAG prompt |
| RAG gen | `apps/quantchat/generation/rag_generator.py` | `_fallback_response` | 350 | LLM failure fallback |
| Retrieval | `apps/quantchat/retrieval/query_expander.py` | `expand` | 45 | Query variations |
| Retrieval | `apps/quantchat/retrieval/pgvector_retriever.py` | `retrieve` | 57 | PG vector backend |
| Retrieval | `apps/quantchat/retrieval/full_doc_retriever.py` | `retrieve_full_document` | 52 | Full document |
| Rerank | `apps/quantchat/reranking/reranker.py` | `rerank` | 51 | Rerank chunks |
| Router | `apps/quantchat/core/query_router.py` | `QueryRouter.__init__` | 72 | Component wiring |
| Router | `apps/quantchat/core/query_router.py` | `route_query` | 109 | Main router |
| Router | `apps/quantchat/core/query_router.py` | `_handle_rag_pipeline` | 280 | RAG pipeline |
| Router | `apps/quantchat/core/query_router.py` | `_handle_full_document` | 452 | Full doc branch |
| Router | `apps/quantchat/core/query_router.py` | `_handle_general_knowledge` | 509 | General branch |
| Router | `apps/quantchat/core/query_router.py` | `_handle_comparison` | 532 | Comparison branch |
| Router | `apps/quantchat/core/query_router.py` | `_handle_error` | 550 | Error handling |
| Singleton | `apps/quantchat/__init__.py` | `get_query_router` | 37 | QueryRouter singleton |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `BaseSpecialistAgent.run` | 132 | Dimension agent |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `BiasAuditorAgent.run` | 484 | Bias audit |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `build_swarm` | 553 | Build agent set |
| Tasks | `apps/api/app/services/jd_generation_tasks.py` | `create_task` | 53 | JD async task id |
| Tracing | `apps/quantchat/utils/tracing.py` | `traceable` | 42 | LangSmith decorator |
| Tracing | `apps/quantchat/utils/tracing.py` | `trace_metadata` | 62 | Trace metadata |
| Vector | `apps/quantchat/retrieval/vector_retriever.py` | `retrieve` | 85 | Vector retrieval |
| Verify | `apps/agents/agents/job_matching/evidence_verifier.py` | `verify_swarm` | 330 | Evidence grounding |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `initialize_state` | 276 | JD init node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `gather_context` | 295 | JD context node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `generate_jd` | 371 | Generator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `refine_jd` | 441 | Refiner node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `validate_jd` | 516 | Validator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `customize_jd` | 598 | Customize node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `prepare_jd` | 636 | Assign `job_id` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `generate_embeddings` | 666 | Embedding node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `store_in_milvus` | 748 | Milvus node (deferred) |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `complete_workflow` | 793 | Complete node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_build_graph` | 807 | Graph definition |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_route_after_prepare` | 852 | Azure: skip Milvus → `complete` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `run` | 863 | Execute graph |

---

*End of Session 3 complete reference.*
