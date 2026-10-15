# Session 2 — Agentic systems code tour

**Purpose:** Files and functions to open live for the four major agentic systems.  
**Line numbers:** From repo at `apps/` layout; re-check in IDE if your branch differs (`Go to line`).

**Demo order (recommended):** Resume → JD → QuantChat → Job matching → shared BFF/LLM/pgvector.

---

## Shared infrastructure (mention once)

| File | Function / area | Brief |
|------|-----------------|--------|
| `apps/web/src/app/api/[...path]/route.ts` | `isLongRunningPath`, proxy handlers | BFF to FastAPI; ~620s timeout for JD, resume, matching |
| `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm`, `llm_provider` | Azure OpenAI / Vertex / OpenAI for all agents |
| `apps/api/app/services/pgvector_ingestion.py` | `add_resume`, `add_jd`, `search_chunks_by_keywords` | Chunking, embeddings, retrieval backing store |

---

## 1. Resume parsing agent

**Flow:** UI upload → API → Blob + text extraction → `ParsingAgent` → Postgres + pgvector.

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|--------|
| UI | `apps/web/src/components/ResumeUpload.tsx` | `uploadResume` | ~145 | Validates file, POST via BFF, shows parse result |
| API | `apps/api/app/api/v1/resume_parsing.py` | `upload_resume` | 322 | Entry: validate, extract text, run pipeline |
| API | `apps/api/app/api/v1/resume_parsing.py` | (inline) | ~423 | `extract_resume_text` — PDF/DOCX/OCR |
| API | `apps/api/app/api/v1/resume_parsing.py` | (inline) | ~472–476 | `ResumePipelineService.parse_and_store(...)` |
| API | `apps/api/app/api/v1/resume_parsing.py` | `analyze_resume` | 703 | Text-only analysis via QueryRouter (optional demo) |
| Integration | `apps/api/app/integrations/document_intelligence.py` | `extract_text_from_pdf` | 138 | Azure DI async text extraction |
| Integration | `apps/api/app/integrations/document_intelligence.py` | `_extract_text_sync` | 75 | Sync DI analyze call |
| Integration | `apps/api/app/integrations/azure_blob.py` | `AzureBlobStorage` | 18 | Blob upload/download (NPD) |
| Service | `apps/api/app/services/resume_pipeline_service.py` | `get_parsing_agent` | 31 | Process-wide `ParsingAgent` singleton |
| Service | `apps/api/app/services/resume_pipeline_service.py` | `parse_and_store` | 60 | Parse → enrich → candidate row → vectors |
| Service | `apps/api/app/services/resume_pipeline_service.py` | (inline) | 71 | `ParsingAgent.run_with_tracking(...)` |
| Service | `apps/api/app/services/resume_completeness.py` | `enrich_parsed_for_enterprise` | (import ~76) | Completeness + narrative experience for UI |
| Agent | `apps/agents/agents/parsing/agent.py` | `ParsingAgent` | 67 | Structured LLM resume extraction |
| Agent | `apps/agents/agents/parsing/agent.py` | `execute` | 262 | Main LLM call + JSON schema output |
| Agent | `apps/agents/agents/parsing/agent.py` | `_normalize_parsed_data` | 244 | Sanitize parsed fields |
| Agent | `apps/agents/agents/parsing/agent.py` | `_validate_parsed_resume` | 250 | Pydantic `ParsedResume` validation |
| Agent base | `apps/agents/agents/base/agent.py` | `run_with_tracking` | 208 | Wraps `execute` with metrics/errors |
| Data | `apps/api/app/services/pgvector_ingestion.py` | `add_resume` | 293 | Index resume chunks for RAG/matching |
| Model | `apps/api/app/models/candidates.py` | `Candidate` | (class) | OLTP candidate + profile JSON |

**Say in the room:** “Upload hits one API handler; the pipeline service owns parse, enrich, and vector ingest; the parsing agent only does structured LLM extraction.”

---

## 2. JD generation (LangGraph multi-agent)

**Flow:** Dialog → async/sync API → orchestrator → LangGraph → HR stamp → `store_jd`.

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|--------|
| UI | `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `JDGenerationDialog` | 112 | HR matrix, generate, poll, preview |
| UI | `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `handleGenerate` | 451 | Calls `generateAsync` / sync fallback |
| UI | `apps/web/src/components/jobs/jd-preview-card.tsx` | (component) | — | HITL preview, save, export hooks |
| API | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description_async` | 1454 | 202 + `task_id` |
| API | `apps/api/app/api/v1/jd_generation.py` | `get_generation_status` | 1486 | Poll in-memory task |
| API | `apps/api/app/api/v1/jd_generation.py` | `generate_job_description` | 1512 | Sync generate (~10 min client timeout) |
| API | `apps/api/app/api/v1/jd_generation.py` | `_execute_jd_generation_core` | 1240 | Orchestrator + HR apply + auto-save |
| API | `apps/api/app/api/v1/jd_generation.py` | `_apply_hr_inputs_to_jd` | 974 | Deterministic HR matrix after LLM |
| API | `apps/api/app/api/v1/jd_generation.py` | `_resolve_generation_inputs` | 1168 | Business-ready validation |
| API | `apps/api/app/api/v1/jd_generation.py` | `_get_jd_orchestrator` | 1199 | Lazy singleton orchestrator |
| API | `apps/api/app/api/v1/jd_generation.py` | `save_job_description` | 1708 | Explicit save / update job + vectors |
| Tasks | `apps/api/app/services/jd_generation_tasks.py` | `create_task` | 53 | Register async JD task |
| Tasks | `apps/api/app/services/jd_generation_tasks.py` | `mark_running` / `mark_completed` | 70 / 79 | Task lifecycle |
| Tasks | `apps/api/app/services/jd_generation_tasks.py` | `get_task` | (see file) | Poll lookup |
| Orchestrator | `apps/agents/agents/jd_generation/orchestrator.py` | `JDGenerationOrchestrator` | 39 | Retries, post-process, workflow invoke |
| Orchestrator | `apps/agents/agents/jd_generation/orchestrator.py` | `generate_job_description` | 118 | Public entry from API thread |
| Orchestrator | `apps/agents/agents/jd_generation/orchestrator.py` | `get_agent_thoughts` | 500 | Thoughts for UI tab |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `JDGenerationState` | 64 | LangGraph typed state |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `JDGenerationWorkflow` | 100 | Graph builder + node methods |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `initialize_state` | 276 | Graph entry node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `gather_context` | 295 | RAG context node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `generate_jd` | 371 | Generator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `refine_jd` | 441 | Refiner node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `validate_jd` | 516 | Validator node |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `prepare_jd` | 636 | Assign `job_id` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_build_graph` | 807 | Nodes, edges, conditional routes |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `_route_after_prepare` | 852 | Azure: skip Milvus → `complete` |
| Workflow | `apps/agents/agents/jd_generation/state_machine.py` | `run` | 863 | `compiled_graph.invoke(...)` |
| Agents | `apps/agents/agents/jd_generation/crew_agents.py` | `RAGAgent.retrieve_similar_jobs` | 4365 | Similar JD retrieval |
| Agents | `apps/agents/agents/jd_generation/crew_agents.py` | `JDGeneratorAgent.generate_jd` | 2378 | Primary 15-section generation |
| Agents | `apps/agents/agents/jd_generation/crew_agents.py` | `JDRefinerAgent.refine_jd` | 3286 | Refinement pass |
| Agents | `apps/agents/agents/jd_generation/crew_agents.py` | `JDValidatorAgent.validate_jd` | 3891 | QA / auto-fix |
| Prompts | `apps/agents/agents/jd_generation/enterprise_prompts.py` | `get_enterprise_generation_prompt` | (see file) | Enterprise JD prompt templates |
| LLM | `apps/agents/agents/jd_generation/llm_runner.py` | `invoke_prompt_with_retry` | (see file) | Direct LangChain invoke + retry |
| Persist | `apps/api/app/services/jd_pipeline_service.py` | `store_jd` | 157 | Job upsert + vector ingest |
| Persist | `apps/api/app/services/pgvector_ingestion.py` | `add_jd` | 346 | JD chunks for QuantChat |

**Say in the room:** “LangGraph runs the agent chain; the API layer owns HR conformance and persistence—that’s our two-layer design.”

---

## 3. QuantChat (QueryRouter RAG)

**Flow:** UI → `ai_chat` → `route_query` → intent → hybrid retrieval → RRF → rerank → generate.

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|--------|
| UI | `apps/web/src/components/QuantChat.tsx` | `handleSubmit` | 133 | POST chat message |
| UI | `apps/web/src/components/QuantChat.tsx` | (default export) | 343 | Sidebar chat widget |
| UI | `apps/web/src/app/dashboard/chat/page.tsx` | (page) | — | Full-page chat route |
| API | `apps/api/app/api/v1/quantchat.py` | `ai_chat` | 90 | Validates router, runs pipeline in thread |
| API | `apps/api/app/api/v1/quantchat.py` | (inline) | 150–152 | `router.route_query` via `asyncio.to_thread` |
| API | `apps/api/app/api/v1/quantchat.py` | `get_quantchat_status` | 199 | Health / router init status |
| Router | `apps/quantchat/__init__.py` | `get_query_router` | 37 | Singleton QueryRouter |
| Router | `apps/quantchat/core/query_router.py` | `QueryRouter` | 57 | Main RAG orchestrator class |
| Router | `apps/quantchat/core/query_router.py` | `route_query` | 109 | Entry: cache, intent, branch |
| Router | `apps/quantchat/core/query_router.py` | `_handle_rag_pipeline` | 280 | Hybrid retrieve → fuse → rerank → answer |
| Router | `apps/quantchat/core/query_router.py` | `_handle_full_document` | 452 | Full-doc path when needed |
| Router | `apps/quantchat/core/query_router.py` | `_handle_general_knowledge` | 509 | Non-RAG answers |
| Intent | `apps/quantchat/core/intent_classifier.py` | `classify` | 94 | Intent + domain for routing |
| Expand | `apps/quantchat/retrieval/query_expander.py` | (class) | — | Multi-query / synonyms |
| Filter | `apps/quantchat/retrieval/metadata_filter.py` | `build_filters` | — | Entity/type filters from intent |
| Retrieval | `apps/quantchat/retrieval/vector_retriever.py` | `retrieve` | 85 | Semantic path (delegates pgvector/Milvus) |
| Retrieval | `apps/quantchat/retrieval/pgvector_retriever.py` | `retrieve` | 57 | Azure pgvector search |
| Retrieval | `apps/quantchat/retrieval/keyword_retriever.py` | `retrieve` | 59 | Keyword / lexical search |
| Fusion | `apps/quantchat/fusion/rrf_fusion.py` | `ReciprocalRankFusion.fuse` | 33 | Merge vector + keyword ranks |
| Rerank | `apps/quantchat/reranking/reranker.py` | `rerank` | 51 | Cross-encoder / LLM rerank |
| Context | `apps/quantchat/context/context_builder.py` | (class) | — | Prompt context from top chunks |
| Generate | `apps/quantchat/generation/rag_generator.py` | `RAGAnswerGenerator.generate` | 28 | Grounded answer |
| Generate | `apps/quantchat/generation/formatter.py` | (class) | — | Response formatting / citations |
| Memory | `apps/quantchat/memory/conversation_memory.py` | (class) | — | Session history for router |
| Data | `apps/api/app/services/pgvector_ingestion.py` | `search_chunks_by_keywords` | 531 | Keyword retriever DB backend |

**Say in the room:** “QuantChat API is thin; all RAG logic lives in QueryRouter—we run vector and keyword search, fuse with RRF, then rerank before the LLM.”

---

## 4. Job matching agentic swarm (HSS-D)

**Flow:** API `match` / `match_stream` → orchestrator → specialists → debate → result/SSE.

| Layer | File | Function / symbol | Line | Brief |
|-------|------|-------------------|------|--------|
| UI | `apps/web/src/app/dashboard/job-matching/page.tsx` | (page) | — | Matching workspace |
| UI | `apps/web/src/components/matching/match-result-view.tsx` | (component) | — | Scores, explanations, feedback |
| API | `apps/api/app/api/v1/job_matching.py` | `match` | 254 | JSON `MatchResult` |
| API | `apps/api/app/api/v1/job_matching.py` | `match_stream` | 283 | SSE agent thoughts stream |
| API | `apps/api/app/api/v1/job_matching.py` | `rank` | 359 | Rank many candidates for one JD |
| API | `apps/api/app/api/v1/job_matching.py` | `_get_orchestrator` | 115 | Lazy orchestrator instance |
| API | `apps/api/app/api/v1/job_matching.py` | `list_candidates_for_matching` | 197 | Dropdown data |
| API | `apps/api/app/api/v1/job_matching.py` | `list_jds_for_matching` | 225 | Dropdown data |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `JobMatchingOrchestrator` | (class ~117) | HSS-D coordinator |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `match` | 256 | Sync match entry |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `stream` | 265 | Async SSE entry |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `amatch` | 228 | Async match wrapper |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run` | 621 | Full pipeline |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_swarm` | 389 | Parallel specialists + risk + bias |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_peer_awareness_pass` | 450 | Cross-specialist revision |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `_run_debate` | 493 | Synthesizer / critic / arbitrator |
| Orchestrator | `apps/agents/agents/job_matching/orchestrator.py` | `arank` / `rank` | 309 / 379 | Multi-candidate ranking |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `BaseSpecialistAgent.run` | 132 | Specialist LLM pattern |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `SkillsAgent` | 313 | Skills dimension |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `ExperienceAgent` | 319 | Experience dimension |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `EducationAgent` | 325 | Education dimension |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `DomainAgent` | 331 | Domain dimension |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `CultureAgent` | 337 | Culture dimension |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `GrowthAgent` | 343 | Growth dimension |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `ProjectsAgent` | 349 | Projects dimension |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `RiskAgent.run` | 390 | Risk assessment |
| Swarm | `apps/agents/agents/job_matching/swarm_agents.py` | `BiasAuditorAgent.run` | 484 | Bias audit |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `SynthesizerAgent.run` | 95 | Merge specialist evidence |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `CriticAgent.run` | 204 | Challenge synthesis |
| Debate | `apps/agents/agents/job_matching/debate_agents.py` | `ArbitratorAgent.run` | 290 | Final adjudication |
| Data | `apps/agents/agents/job_matching/data_access_pg.py` | (load functions) | — | Candidate/JD from pgvector path |
| Models | `apps/agents/agents/job_matching/enterprise_models.py` | `MatchResult`, `AgentThought` | — | API/UI DTOs |
| Config | `apps/agents/agents/job_matching/config.py` | `get_config` | — | Weights, models, timeouts |
| Cache | `apps/agents/agents/job_matching/cache.py` | `match_cache_key` | — | Optional match result cache |

**Say in the room:** “Matching is a staged swarm—parallel specialists, then debate agents—not a single prompt. `match_stream` exposes thoughts over SSE for the UI.”

---

## Quick reference — one path per system

| System | Start here | Then jump to |
|--------|------------|--------------|
| Resume | `resume_parsing.py:322` `upload_resume` | `resume_pipeline_service.py:60` → `parsing/agent.py:262` |
| JD | `jd-generation-dialog.tsx:451` `handleGenerate` | `jd_generation.py:1240` → `state_machine.py:863` `run` |
| QuantChat | `QuantChat.tsx:133` `handleSubmit` | `quantchat.py:90` → `query_router.py:280` `_handle_rag_pipeline` |
| Matching | `job_matching.py:283` `match_stream` | `orchestrator.py:389` `_run_swarm` → `493` `_run_debate` |

---

## Related docs

- `docs/session-2-code-walkthrough-complete.md` — full Session 2 agenda  
- `docs/jd-generation-architecture.md` — JD-only deep dive  
- `docs/session-1-architecture-and-resources-complete.md` — architecture context  

---

*End of agentic code tour.*
