# Agentic systems — quick reference (KT demo)

Major files and functions only. Open top → bottom (UI → API → agent). **Line** = start of the symbol in the current repo (use IDE “Go to line”).

---

## Resume parsing

| Line | File | Function | Brief description |
|------|------|----------|-------------------|
| 145 | `apps/web/src/components/ResumeUpload.tsx` | `uploadResume` | Builds `FormData`, POSTs file to resume API, handles UI state/errors |
| 322 | `apps/api/app/api/v1/resume_parsing.py` | `upload_resume` | Auth + validation; extract text; delegates to pipeline |
| 138 | `apps/api/app/integrations/document_intelligence.py` | `extract_text_from_pdf` | Async wrapper: Azure Document Intelligence PDF → plain text |
| 60 | `apps/api/app/services/resume_pipeline_service.py` | `parse_and_store` | End-to-end: parse agent, persist candidate, trigger vector ingest |
| 262 | `apps/agents/agents/parsing/agent.py` | `execute` | LLM parses resume text into structured JSON (skills, experience, etc.) |
| 293 | `apps/api/app/services/pgvector_ingestion.py` | `add_resume` | Chunk + embed resume; write to pgvector for RAG and matching |

---

## JD generation

| Line | File | Function | Brief description |
|------|------|----------|-------------------|
| 451 | `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `handleGenerate` | Collects HR inputs; calls async or sync JD generate API |
| 1454 | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description_async` | Enqueues background task; returns task id for polling |
| 1240 | `apps/api/app/api/v1/jd_generation.py` | `_execute_jd_generation_core` | Runs orchestrator, merges result, applies HR fields, saves |
| 974 | `apps/api/app/api/v1/jd_generation.py` | `_apply_hr_inputs_to_jd` | Overlays salary, location, matrix fields onto LLM JD payload |
| 118 | `apps/agents/agents/jd_generation/orchestrator.py` | `generate_job_description` | Builds context and invokes LangGraph workflow |
| 863 | `apps/agents/agents/jd_generation/state_machine.py` | `run` | Compiles/invokes graph; returns final `JDGenerationState` |
| 371 | `apps/agents/agents/jd_generation/state_machine.py` | `generate_jd` | Graph node: first-pass JD generation |
| 441 | `apps/agents/agents/jd_generation/state_machine.py` | `refine_jd` | Graph node: refine draft from feedback/rules |
| 516 | `apps/agents/agents/jd_generation/state_machine.py` | `validate_jd` | Graph node: quality/compliance checks before exit |
| 2378 | `apps/agents/agents/jd_generation/crew_agents.py` | `JDGeneratorAgent.generate_jd` | Crew LLM call that produces JD sections from context |
| 157 | `apps/api/app/services/jd_pipeline_service.py` | `store_jd` | Persist job record + pgvector embeddings for the JD |

---

## QuantChat (QueryRouter)

| Line | File | Function | Brief description |
|------|------|----------|-------------------|
| 133 | `apps/web/src/components/QuantChat.tsx` | `handleSubmit` | Sends user message to QuantChat API; updates chat UI |
| 90 | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | HTTP entry: builds router, returns assistant reply + metadata |
| 109 | `apps/quantchat/core/query_router.py` | `route_query` | Classifies intent; branches to RAG vs general chat |
| 280 | `apps/quantchat/core/query_router.py` | `_handle_rag_pipeline` | Hybrid retrieve → fuse → rerank → grounded generation |
| 94 | `apps/quantchat/core/intent_classifier.py` | `classify` | LLM (or fallback) labels query as RAG-eligible vs general |
| 85 | `apps/quantchat/retrieval/vector_retriever.py` | `retrieve` | Semantic search over pgvector chunks |
| 59 | `apps/quantchat/retrieval/keyword_retriever.py` | `retrieve` | Keyword/BM25-style search for lexical matches |
| 33 | `apps/quantchat/fusion/rrf_fusion.py` | `fuse` | Reciprocal rank fusion of vector + keyword hit lists |
| 51 | `apps/quantchat/reranking/reranker.py` | `rerank` | Re-scores top chunks for query relevance |
| 28 | `apps/quantchat/generation/rag_generator.py` | `generate` | LLM answer constrained to retrieved context |

---

## Job matching (HSS-D swarm)

| Line | File | Function | Brief description |
|------|------|----------|-------------------|
| 389 | `apps/web/src/app/dashboard/job-matching/page.tsx` | `JobMatchingPage` | Dashboard: launcher, live swarm UI, results |
| 254 | `apps/api/app/api/v1/job_matching.py` | `match` | Synchronous match: full pipeline → JSON result |
| 283 | `apps/api/app/api/v1/job_matching.py` | `match_stream` | SSE stream of agent thoughts + final match |
| 256 | `apps/agents/agents/job_matching/orchestrator.py` | `match` | Sync wrapper around async pipeline (`asyncio.run`) |
| 265 | `apps/agents/agents/job_matching/orchestrator.py` | `stream` | Async generator yielding thought events during run |
| 389 | `apps/agents/agents/job_matching/orchestrator.py` | `_run_swarm` | Runs specialist agents in parallel (skills, experience, …) |
| 493 | `apps/agents/agents/job_matching/orchestrator.py` | `_run_debate` | Synthesizer → critic → arbitrator debate chain |
| 132 | `apps/agents/agents/job_matching/swarm_agents.py` | `BaseSpecialistAgent.run` | One dimension: LLM score + rationale for candidate vs JD |
| 95 | `apps/agents/agents/job_matching/debate_agents.py` | `SynthesizerAgent.run` | Combines dimension scores into draft match narrative |
| 290 | `apps/agents/agents/job_matching/debate_agents.py` | `ArbitratorAgent.run` | Final decision, overall fit, and confidence |
| 271 | `apps/agents/agents/job_matching/data_access_pg.py` | `get_candidate_pg` | Load normalized candidate profile (+ vectors) from Postgres |
| 279 | `apps/agents/agents/job_matching/data_access_pg.py` | `get_jd_pg` | Load job opening / JD text and requirements from Postgres |

---

## Shared (one slide)

| Line | File | Function | Brief description |
|------|------|----------|-------------------|
| 146 | `apps/web/src/app/api/[...path]/route.ts` | `proxyToBackend` | Next.js BFF: forwards method/body/headers to FastAPI |
| 211 | `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm` | Central factory for Azure/OpenAI chat models used by agents |

---

## 30-second demo paths (with lines)

| System | Open in order |
|--------|----------------|
| Resume | L322 `upload_resume` → L60 `parse_and_store` → L262 `execute` |
| JD | L451 `handleGenerate` → L1240 `_execute_jd_generation_core` → L863 `run` |
| QuantChat | L90 `ai_chat` → L109 `route_query` → L280 `_handle_rag_pipeline` |
| Matching | L283 `match_stream` → L389 `_run_swarm` → L493 `_run_debate` |
