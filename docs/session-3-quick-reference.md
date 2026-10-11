# Session 3 — quick reference (AI, agents, observability)

Main symbols only. **Line** = go-to-line in IDE. Full detail: `docs/session-3-ai-components-complete.md`.

---

## QuantChat — one pipeline

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | 90 | Chat entry → QueryRouter (worker thread) |
| Router | `apps/quantchat/core/query_router.py` | `route_query` | 109 | Intent branch + memory + observability |
| Router | `apps/quantchat/core/query_router.py` | `_handle_rag_pipeline` | 280 | Hybrid RAG (main HR path) |
| Intent | `apps/quantchat/core/intent_classifier.py` | `classify` | 94 | RAG vs general vs full doc vs comparison |
| Vector | `apps/quantchat/retrieval/vector_retriever.py` | `retrieve` | 85 | Semantic search (pgvector) |
| Keyword | `apps/quantchat/retrieval/keyword_retriever.py` | `retrieve` | 59 | Lexical search |
| Fusion | `apps/quantchat/fusion/rrf_fusion.py` | `fuse` | 33 | Merge vector + keyword (RRF) |
| Rerank | `apps/quantchat/reranking/reranker.py` | `rerank` | 51 | Re-score top chunks |
| Context | `apps/quantchat/context/context_builder.py` | `build_context` | 65 | Prompt context + history |
| Generate | `apps/quantchat/generation/rag_generator.py` | `generate` | 28 | Grounded LLM answer |

**30s path:** L90 → L109 → L280 → L28

---

## JD generation — LangGraph

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| UI | `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `handleGenerate` | 451 | Trigger async/sync generate |
| API | `apps/api/app/api/v1/jd_generation.py` | `_execute_jd_generation_core` | 1240 | Orchestrator + HR overlay + save |
| API | `apps/api/app/api/v1/jd_generation.py` | `_apply_hr_inputs_to_jd` | 974 | HR matrix on JD dict |
| Orchestrator | `apps/agents/agents/jd_generation/orchestrator.py` | `generate_job_description` | 118 | Entry to graph |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `generate_jd` | 371 | Generator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `refine_jd` | 441 | Refiner node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `validate_jd` | 516 | Validator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `prepare_jd` | 636 | Assign `job_id` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_build_graph` | 807 | Graph nodes & edges |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_route_after_prepare` | 852 | NPD: skip Milvus → complete |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `run` | 863 | Run graph |
| Persist | `apps/api/app/services/jd_pipeline_service.py` | `store_jd` | 157 | Postgres + pgvector |

**30s path:** L451 → L1240 → L863

---

## Resume parsing

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/api/app/api/v1/resume_parsing.py` | `upload_resume` | 322 | Validate + extract + pipeline |
| Extract | `apps/api/app/services/pdf_extraction.py` | `extract_resume_text` | 169 | DI / local text extract |
| Pipeline | `apps/api/app/services/resume_pipeline_service.py` | `parse_and_store` | 60 | Agent + DB + vectors |
| Agent | `apps/agents/agents/parsing/agent.py` | `execute` | 262 | LLM structured parse |

**30s path:** L322 → L169 → L60 → L262

---

## Job matching (swarm + debate)

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| API | `apps/api/app/api/v1/job_matching.py` | `match_stream` | 283 | SSE thoughts + result |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_swarm` | 389 | Parallel specialists |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_debate` | 493 | Synthesizer → Critic → Arbitrator |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `ArbitratorAgent.run` | 290 | Final match decision |
| Verify | `apps/agents/agents/job_matching/evidence_verifier.py` | `verify_swarm` | 330 | Strip bad evidence quotes |

**30s path:** L283 → L389 → L493

---

## LLM configuration

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Factory | `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm` | 211 | All agents + QuantChat LLM |
| Factory | `apps/agents/agents/llm/chat_factory.py` | `llm_provider` | 80 | `azure_openai` / `openai` / `vertexai` |
| Config | `apps/quantchat/config/settings.py` | `LLM_MODEL` | 89 | QuantChat default model name |
| Config | `apps/api/app/config.py` | `Settings` | 11 | NPD defaults (auth, vector store) |

**Env (NPD):** `LLM_PROVIDER=azure_openai`, `AZURE_OPENAI_*`, `VECTOR_STORE=pgvector`.

---

## Evaluation & feedback

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| RAG eval | `apps/quantchat/monitoring/agent_observability.py` | `RAGEvaluator.evaluate` | 227 | Faithfulness / relevance / groundedness |
| RAG eval | `apps/quantchat/monitoring/agent_observability.py` | `complete_trace` | 472 | Runs eval on RAG; logs quality |
| RAG guard | `apps/quantchat/generation/rag_generator.py` | `_validate_response` | 111 | Answer vs context check |
| Hiring FB | `apps/api/app/api/v1/feedback.py` | `create_feedback` | 185 | Recruiter outcome feedback (DB) |
| Hiring FB | `apps/api/app/api/v1/feedback.py` | `analyze_feedback` | 358 | Drift analysis (FeedbackAgent) |
| Chat FB | `apps/quantchat/monitoring/agent_observability.py` | `record_feedback` | 545 | In-process only; REST/UI not wired |

---

## Observability

| Area | File | Function / symbol | Line | Brief |
|------|------|-------------------|------|-------|
| Hub | `apps/quantchat/monitoring/agent_observability.py` | `start_trace` | 374 | Per-query trace id |
| Hub | `apps/quantchat/monitoring/agent_observability.py` | `complete_trace` | 472 | Latency, cost, quality scores |
| Dashboard | `apps/quantchat/monitoring/agent_observability.py` | `get_full_dashboard` | 1034 | Aggregated metrics JSON |
| Status | `apps/api/app/api/v1/quantchat.py` | `get_quantchat_status` | 199 | QueryRouter health |
| Matching UX | `apps/api/app/api/v1/job_matching.py` | `match_stream` | 283 | Live agent thoughts (SSE) |
| Toggle | `apps/quantchat/config/settings.py` | `ENABLE_OBSERVABILITY` | 116 | In-process obs on/off |

**Gap:** `apps/web/src/lib/api.ts` observability routes expect `/v1/quantchat/observability/*` — mount on API to enable UI dashboards.

---

## Session 3 in one sentence

**QuantChat** = `route_query` → hybrid retrieve → RAG **`generate`**; **JD** = LangGraph **`run`** + API **`store_jd`**; **matching** = **`_run_swarm`** then **`_run_debate`**; **one **`create_chat_llm`**; quality via **`RAGEvaluator`** + hiring **`/feedback`**; traces via **`AgentObservabilityManager`**.
