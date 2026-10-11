# Session 3 — Quick Reference Guide

**QuantHire AI · Knowledge Transfer**

| | |
|---|---|
| **Session title** | AI Components, Agentic Workflows & Observability |
| **Audience** | AI engineers continuing QuantHire development |
| **Format** | Tables: **Area \| File \| Function / symbol \| Line \| Brief** |
| **Line numbers** | IDE “Go to line” (repo branch used for KT verification) |
| **Full reference** | [session-3-ai-components-complete.md](./session-3-ai-components-complete.md) |

---

## Session agenda → where in code

| Agenda topic | Primary section below |
|--------------|------------------------|
| QuantChat: routing, intent, retrieval, fusion, rerank, context, generation | §1 QuantChat |
| Agentic workflows: JD, resume, matching, orchestration, decisions | §2–§4 |
| Model & prompt configuration, provider, fallbacks | §5 LLM |
| Evaluation & user feedback | §6 Evaluation |
| Observability: logs, tracing, perf/cost, dashboards | §7 Observability |

---

## Flow at a glance

```text
QuantChat:  ai_chat → route_query → classify → _handle_rag_pipeline
            → vector + keyword → fuse → rerank → build_context → generate

JD:         handleGenerate → _execute_jd_generation_core → state_machine.run
            → generate_jd → refine_jd → validate_jd → prepare_jd → store_jd

Resume:     upload_resume → extract_resume_text → parse_and_store → execute

Matching:   match_stream → _run_swarm → verify_swarm → _run_debate → Arbitrator

LLM (all):  create_chat_llm  ←  LLM_PROVIDER / AZURE_OPENAI_* / GCP_*

Quality:    RAGEvaluator + complete_trace  |  hiring POST /feedback

Obs:        AgentObservabilityManager (in-process)  |  GET quantchat/status
```

---

## §1 QuantChat — query routing & RAG pipeline

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | 90 | Chat entry → QueryRouter (`asyncio.to_thread`) |
| Router | `apps/quantchat/core/query_router.py` | `route_query` | 109 | Normalize, intent, branch, memory, trace |
| Router | `apps/quantchat/core/query_router.py` | `_handle_rag_pipeline` | 280 | Main HR path: retrieve → fuse → rerank → answer |
| Intent | `apps/quantchat/core/intent_classifier.py` | `classify` | 94 | RAG / general / full doc / comparison |
| Intent | `apps/quantchat/core/intent_classifier.py` | `_fallback_classify` | 210 | Regex fallback if LLM unavailable |
| Vector | `apps/quantchat/retrieval/vector_retriever.py` | `retrieve` | 85 | Semantic search (pgvector on NPD) |
| Keyword | `apps/quantchat/retrieval/keyword_retriever.py` | `retrieve` | 59 | Lexical / keyword search |
| Fusion | `apps/quantchat/fusion/rrf_fusion.py` | `fuse` | 33 | Reciprocal rank fusion (vector + keyword) |
| Rerank | `apps/quantchat/reranking/reranker.py` | `rerank` | 51 | Re-score fused chunks |
| Context | `apps/quantchat/context/context_builder.py` | `build_context` | 65 | Context string + conversation history |
| Generate | `apps/quantchat/generation/rag_generator.py` | `generate` | 28 | Grounded LLM answer + confidence |

**Demo path (30 s):** L90 `ai_chat` → L109 `route_query` → L280 `_handle_rag_pipeline` → L28 `generate`

**Other branches (same router file):** `_handle_general_knowledge` L509 · `_handle_full_document` L452 · `_handle_comparison` L532

---

## §2 JD generation — LangGraph workflow

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| UI | `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `handleGenerate` | 451 | Async poll or sync generate |
| API | `apps/api/app/api/v1/jd_generation.py` | `_execute_jd_generation_core` | 1240 | Orchestrator + HR fields + save |
| API | `apps/api/app/api/v1/jd_generation.py` | `_apply_hr_inputs_to_jd` | 974 | HR matrix overlay on JD JSON |
| Orchestrator | `apps/agents/agents/jd_generation/orchestrator.py` | `generate_job_description` | 118 | Validates input; calls graph |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `generate_jd` | 371 | Generator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `refine_jd` | 441 | Refiner node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `validate_jd` | 516 | Validator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `prepare_jd` | 636 | Assign `job_id` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_build_graph` | 807 | Nodes, edges, conditional routes |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_route_after_prepare` | 852 | NPD: skip Milvus/embed → `complete` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `run` | 863 | Execute compiled graph |
| Persist | `apps/api/app/services/jd_pipeline_service.py` | `store_jd` | 157 | Postgres + pgvector |

**Demo path (30 s):** L451 → L1240 → L863

**Decision:** Validator + HR API overlay; graph skips local Milvus on Azure (`_route_after_prepare`).

---

## §3 Resume parsing — agent pipeline

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/api/app/api/v1/resume_parsing.py` | `upload_resume` | 322 | Validate file; run pipeline |
| Extract | `apps/api/app/services/pdf_extraction.py` | `extract_resume_text` | 169 | Azure DI / local extract |
| Pipeline | `apps/api/app/services/resume_pipeline_service.py` | `parse_and_store` | 60 | Agent, candidate upsert, ingest |
| Agent | `apps/agents/agents/parsing/agent.py` | `execute` | 262 | LLM → structured resume JSON |
| Vectors | `apps/api/app/services/pgvector_ingestion.py` | `add_resume` | 293 | Index for QuantChat / matching |

**Demo path (30 s):** L322 → L169 → L60 → L262

---

## §4 Job matching — swarm & debate (decision)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/api/app/api/v1/job_matching.py` | `match` | 254 | JSON result (`amatch`) |
| API | `apps/api/app/api/v1/job_matching.py` | `match_stream` | 283 | SSE agent thoughts + result |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_swarm` | 389 | Parallel dimension specialists |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_debate` | 493 | Synthesizer → Critic → Arbitrator |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `ArbitratorAgent.run` | 290 | **Final** fit decision |
| Verify | `apps/agents/agents/job_matching/evidence_verifier.py` | `verify_swarm` | 330 | Remove ungrounded quotes (no LLM) |

**Demo path (30 s):** L283 → L389 → L493 → L290

---

## §5 Model & prompt configuration

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Factory | `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm` | 211 | **Single** chat model factory (agents + QuantChat) |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `llm_provider` | 80 | Provider switch |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `fallback_llm_model` | 109 | Fallback deployment/name |
| Config | `apps/quantchat/config/settings.py` | `LLM_MODEL` | 89 | QuantChat model default |
| Config | `apps/quantchat/config/settings.py` | `ENABLE_FALLBACKS` | 100 | QuantChat fallback toggles |
| Config | `apps/api/app/config.py` | `Settings` | 11 | App/NPD defaults |

**NPD env (typical):** `DEPLOYMENT_TARGET=azure-nonprod` · `LLM_PROVIDER=azure_openai` · `AZURE_OPENAI_ENDPOINT` · `AZURE_OPENAI_API_KEY` · chat/embedding deployments · `VECTOR_STORE=pgvector`

**Prompts:** Inline in `crew_agents.py`, `rag_generator.py`, `swarm_agents.py`, `debate_agents.py` (no central registry yet).

**Fallbacks:** Intent `_fallback_classify` · empty RAG → rephrase message · `rag_generator._fallback_response` L350 · JD `_route_after_prepare` skips legacy Milvus on NPD.

---

## §6 Evaluation & feedback

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| RAG eval | `apps/quantchat/monitoring/agent_observability.py` | `RAGEvaluator.evaluate` | 227 | Heuristic faithfulness / relevance / groundedness |
| RAG eval | `apps/quantchat/monitoring/agent_observability.py` | `complete_trace` | 472 | Runs eval; logs quality on trace complete |
| RAG guard | `apps/quantchat/generation/rag_generator.py` | `_validate_response` | 111 | Generation-time context check |
| Hiring | `apps/api/app/api/v1/feedback.py` | `create_feedback` | 185 | Store recruiter hiring feedback (DB) |
| Hiring | `apps/api/app/api/v1/feedback.py` | `analyze_feedback` | 358 | Drift / retrain hints (`FeedbackAgent`) |
| Chat FB | `apps/quantchat/monitoring/agent_observability.py` | `record_feedback` | 545 | **In-process only** — no chat UI/API yet |

**Note:** Chat “feedback” today = **next user message** in conversation memory. Hiring feedback ≠ QuantChat thumbs.

---

## §7 Observability

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Trace | `apps/quantchat/monitoring/agent_observability.py` | `start_trace` | 374 | Open per-query trace |
| Trace | `apps/quantchat/monitoring/agent_observability.py` | `complete_trace` | 472 | Latency, cost estimate, quality scores |
| Metrics | `apps/quantchat/monitoring/agent_observability.py` | `get_full_dashboard` | 1034 | Dashboard JSON (in-memory) |
| Metrics | `apps/quantchat/monitoring/agent_observability.py` | `get_prometheus_metrics` | 976 | Prometheus text export |
| Logs | `apps/quantchat/monitoring/agent_observability.py` | `complete_trace` | 533 | INFO log: latency, cost, quality |
| Tracing | `apps/quantchat/utils/tracing.py` | `traceable` | 42 | LangSmith spans (optional) |
| API | `apps/api/app/api/v1/quantchat.py` | `get_quantchat_status` | 199 | QueryRouter health |
| Toggle | `apps/quantchat/config/settings.py` | `ENABLE_OBSERVABILITY` | 116 | Turn in-process obs on/off |
| Matching UI | `apps/api/app/api/v1/job_matching.py` | `match_stream` | 283 | Live “agent thoughts” (SSE) |

**Gap:** Web client defines `/v1/quantchat/observability/*` in `apps/web/src/lib/api.ts` — **mount FastAPI routes** to expose `get_full_dashboard()` etc.

---

## §8 All demo paths (one table)

| System | Open in order (line → symbol) |
|--------|-------------------------------|
| QuantChat | L90 `ai_chat` → L109 `route_query` → L280 `_handle_rag_pipeline` → L28 `generate` |
| JD | L451 `handleGenerate` → L1240 `_execute_jd_generation_core` → L863 `run` |
| Resume | L322 `upload_resume` → L169 `extract_resume_text` → L262 `execute` |
| Matching | L283 `match_stream` → L389 `_run_swarm` → L493 `_run_debate` |
| LLM | L211 `create_chat_llm` + env `LLM_PROVIDER` |
| Quality | L472 `complete_trace` + L185 `create_feedback` (hiring) |

---

## §9 Session 3 summary (one paragraph)

QuantChat uses a **single QueryRouter**: intent classification, **hybrid retrieval** (vector + keyword, **RRF**, rerank), **context build**, and **grounded generation**, with optional **AgentObservabilityManager** traces. **JD generation** is a **LangGraph** workflow (generate → refine → validate → prepare) with API **HR overlay** and **pgvector** persist on NPD. **Resume parsing** is a linear **ParsingAgent** pipeline into vectors. **Job matching** combines a **parallel swarm**, **evidence verification**, and a **debate** ending in the **Arbitrator**. All LLM calls go through **`create_chat_llm`**. Quality is measured by **heuristic RAG evaluation**, **response validation**, and **hiring feedback APIs**; chat thumbs and observability REST are the main extension points.

---

*End of Session 3 Quick Reference Guide*
