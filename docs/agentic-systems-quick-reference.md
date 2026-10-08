# Agentic systems — quick reference (KT demo)

Verified against the repo on branch `cursor/jd-generation-architecture-doc-b100`. **Line** = definition line for that symbol (IDE “Go to line”). Walk each system **Frontend → BFF → API → services/agents**.

---

## Resume parsing

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|-------|
| Frontend | `apps/web/src/components/ResumeUpload.tsx` | `uploadResume` | 145 | POST `FormData` to `/v1/resume-parsing/upload-resume`; handles progress and errors |
| BFF | `apps/web/src/app/api/[...path]/route.ts` | `POST` → `proxyToBackend` | 239 / 146 | Forwards browser API calls to FastAPI (same path under `/api/`) |
| API | `apps/api/app/api/v1/resume_parsing.py` | `upload_resume` | 322 | Validates file, optional Azure Blob, extracts text, runs pipeline |
| Service | `apps/api/app/services/pdf_extraction.py` | `extract_resume_text` | 169 | Universal extract by extension; PDF uses DI first, then local fallbacks |
| Integration | `apps/api/app/integrations/document_intelligence.py` | `extract_text_from_pdf_sync` | 133 | Azure Document Intelligence: bytes → text (used from `pdf_extraction._di_extract_sync`) |
| Service | `apps/api/app/services/resume_pipeline_service.py` | `parse_and_store` | 60 | Parsing agent, candidate upsert, pgvector ingest, commit |
| Agent | `apps/agents/agents/parsing/agent.py` | `execute` | 262 | LLM structured parse of resume text (invoked via `run_with_tracking` in pipeline) |
| Service | `apps/api/app/services/pgvector_ingestion.py` | `add_resume` | 293 | Chunk, embed, and store resume sections in pgvector |

---

## JD generation

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|-------|
| Frontend | `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `handleGenerate` | 451 | Validates HR fields; calls async or sync JD generate API |
| BFF | `apps/web/src/app/api/[...path]/route.ts` | `POST` → `proxyToBackend` | 239 / 146 | Proxies JD generation requests to FastAPI |
| API | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description_async` | 1454 | Creates in-memory task id; schedules background generation (202) |
| API | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description` | 1512 | Synchronous generate endpoint (blocks until done) |
| API | `apps/api/app/api/v1/jd_generation.py` | `_execute_jd_generation_core` | 1240 | Calls orchestrator, normalizes JD payload, HR overlay, persistence |
| API | `apps/api/app/api/v1/jd_generation.py` | `_apply_hr_inputs_to_jd` | 974 | Merges salary, location, matrix, and other HR inputs into JD dict |
| Agent | `apps/agents/agents/jd_generation/orchestrator.py` | `generate_job_description` | 118 | Validates inputs and runs LangGraph JD workflow |
| Agent | `apps/agents/agents/jd_generation/state_machine.py` | `run` | 863 | Invokes compiled graph; returns final state |
| Agent | `apps/agents/agents/jd_generation/state_machine.py` | `generate_jd` | 371 | Graph node: initial JD draft |
| Agent | `apps/agents/agents/jd_generation/state_machine.py` | `refine_jd` | 441 | Graph node: refinement pass |
| Agent | `apps/agents/agents/jd_generation/state_machine.py` | `validate_jd` | 516 | Graph node: validation before completion |
| Agent | `apps/agents/agents/jd_generation/crew_agents.py` | `JDGeneratorAgent.generate_jd` | 2378 | Crew LLM step that writes JD sections from context |
| Service | `apps/api/app/services/jd_pipeline_service.py` | `store_jd` | 157 | Persists job record and JD vectors to Postgres/pgvector |

---

## QuantChat (QueryRouter)

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|-------|
| Frontend | `apps/web/src/components/QuantChat.tsx` | `handleSubmit` | 133 | Submits user message to QuantChat API |
| BFF | `apps/web/src/app/api/[...path]/route.ts` | `POST` → `proxyToBackend` | 239 / 146 | Proxies `/v1/quantchat/chat` to FastAPI |
| API | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | 90 | Resolves `QueryRouter`, runs query, returns reply + metadata |
| QuantChat | `apps/quantchat/core/query_router.py` | `route_query` | 109 | Intent classification; RAG vs general branch |
| QuantChat | `apps/quantchat/core/query_router.py` | `_handle_rag_pipeline` | 280 | Retrieve → fuse → rerank → grounded answer |
| QuantChat | `apps/quantchat/core/intent_classifier.py` | `classify` | 94 | LLM or fallback intent (RAG-eligible vs general) |
| QuantChat | `apps/quantchat/retrieval/vector_retriever.py` | `retrieve` | 85 | Embedding search over pgvector chunks |
| QuantChat | `apps/quantchat/retrieval/keyword_retriever.py` | `retrieve` | 59 | Keyword / lexical retrieval |
| QuantChat | `apps/quantchat/fusion/rrf_fusion.py` | `fuse` | 33 | Reciprocal rank fusion of result lists |
| QuantChat | `apps/quantchat/reranking/reranker.py` | `rerank` | 51 | Re-scores fused chunks for the query |
| QuantChat | `apps/quantchat/generation/rag_generator.py` | `RAGAnswerGenerator.generate` | 28 | LLM answer grounded on retrieved context |

---

## Job matching (HSS-D swarm)

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|-------|
| Frontend | `apps/web/src/app/dashboard/job-matching/page.tsx` | `JobMatchingPageContent` | 93 | Setup/run/results UI; `handleLaunch` starts SSE via `useMatchStream` |
| Frontend | `apps/web/src/app/dashboard/job-matching/page.tsx` | `JobMatchingPage` | 389 | Page shell (Suspense wrapper around content) |
| BFF | `apps/web/src/app/api/[...path]/route.ts` | `GET` → `proxyToBackend` | 235 / 146 | Proxies match-stream SSE (streaming response passthrough) |
| API | `apps/api/app/api/v1/job_matching.py` | `match` | 254 | POST JSON match via `orchestrator.amatch` |
| API | `apps/api/app/api/v1/job_matching.py` | `match_stream` | 283 | GET SSE: agent thoughts then final result |
| Agent | `apps/agents/agents/job_matching/orchestrator.py` | `amatch` | 228 | Async full pipeline (swarm + debate + result) |
| Agent | `apps/agents/agents/job_matching/orchestrator.py` | `match` | 256 | Sync wrapper: `asyncio.run(amatch(...))` |
| Agent | `apps/agents/agents/job_matching/orchestrator.py` | `stream` | 265 | Async iterator of thought events for SSE |
| Agent | `apps/agents/agents/job_matching/orchestrator.py` | `_run_swarm` | 389 | Parallel specialist dimension scoring |
| Agent | `apps/agents/agents/job_matching/orchestrator.py` | `_run_debate` | 493 | Synthesizer → Critic → Arbitrator chain |
| Agent | `apps/agents/agents/job_matching/swarm_agents.py` | `BaseSpecialistAgent.run` | 132 | One dimension: score + rationale vs JD |
| Agent | `apps/agents/agents/job_matching/debate_agents.py` | `SynthesizerAgent.run` | 95 | Draft narrative from dimension scores |
| Agent | `apps/agents/agents/job_matching/debate_agents.py` | `CriticAgent.run` | 204 | Challenges synthesis; feeds next debate round |
| Agent | `apps/agents/agents/job_matching/debate_agents.py` | `ArbitratorAgent.run` | 290 | Final fit decision and confidence |
| Agent | `apps/agents/agents/job_matching/data_access_pg.py` | `get_candidate_pg` | 271 | Load candidate profile from Postgres/chunks |
| Agent | `apps/agents/agents/job_matching/data_access_pg.py` | `get_jd_pg` | 279 | Load JD / job opening from Postgres/chunks |

---

## Shared (one slide)

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|-------|
| BFF | `apps/web/src/app/api/[...path]/route.ts` | `proxyToBackend` | 146 | Core BFF proxy (auth headers, timeouts, SSE passthrough) |
| Shared LLM | `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm` | 211 | Factory for Azure/OpenAI chat models across agents |

---

## Verification notes (accuracy)

| Topic | Detail |
|-------|--------|
| Resume text extract | `upload_resume` calls **`extract_resume_text`** (L169), not DI directly. DI is reached via **`extract_text_from_pdf_sync`** (L133) inside `_di_extract_sync` (L115). |
| Parsing agent entry | Pipeline uses **`run_with_tracking`** on the parsing agent; demo **`execute`** (L262) is the core LLM parse implementation. |
| JD async tasks | Background jobs use **`jd_generation_tasks`** + `asyncio.create_task` from **`generate_job_description_async`** (L1471–1477), not a separate queue service. |
| Job match API | Blocking route uses **`amatch`**; **`match`** on the orchestrator (L256) is the sync convenience wrapper. |
| Match stream | **`match_stream`** is **GET** `/match-stream` with query params, not POST. |
| QuantChat class | RAG step class is **`RAGAnswerGenerator`**; method **`generate`** starts at L28. |

---

## 30-second demo paths (layer order)

| System | Open in order |
|--------|----------------|
| Resume | L322 `upload_resume` → L169 `extract_resume_text` → L60 `parse_and_store` → L262 `execute` |
| JD | L451 `handleGenerate` → L1240 `_execute_jd_generation_core` → L863 `run` |
| QuantChat | L90 `ai_chat` → L109 `route_query` → L280 `_handle_rag_pipeline` |
| Matching | L283 `match_stream` → L389 `_run_swarm` → L493 `_run_debate` |
