# Agentic systems — quick reference (KT demo)

Major files and functions only. Open top → bottom (UI → API → agent).

---

## Resume parsing

| File | Show this function | What it does |
|------|-------------------|--------------|
| `apps/web/src/components/ResumeUpload.tsx` | `uploadResume` | User upload → calls resume API |
| `apps/api/app/api/v1/resume_parsing.py` | `upload_resume` | Validates file, extract text, runs pipeline |
| `apps/api/app/integrations/document_intelligence.py` | `extract_text_from_pdf` | Azure DI: PDF → text |
| `apps/api/app/services/resume_pipeline_service.py` | `parse_and_store` | Orchestrates parse, DB, vectors |
| `apps/agents/agents/parsing/agent.py` | `execute` | LLM structured resume JSON |
| `apps/api/app/services/pgvector_ingestion.py` | `add_resume` | Index chunks for RAG/matching |

---

## JD generation

| File | Show this function | What it does |
|------|-------------------|--------------|
| `apps/web/src/components/jobs/jd-generation-dialog.tsx` | `handleGenerate` | Triggers async/sync JD generate |
| `apps/api/app/api/v1/jd_generation.py` | `generate_job_description_async` | Starts background JD task |
| `apps/api/app/api/v1/jd_generation.py` | `_execute_jd_generation_core` | Runs orchestrator + save path |
| `apps/api/app/api/v1/jd_generation.py` | `_apply_hr_inputs_to_jd` | Stamps HR matrix after LLM |
| `apps/agents/agents/jd_generation/orchestrator.py` | `generate_job_description` | Entry to LangGraph workflow |
| `apps/agents/agents/jd_generation/state_machine.py` | `run` | Invokes compiled LangGraph |
| `apps/agents/agents/jd_generation/state_machine.py` | `generate_jd` / `refine_jd` / `validate_jd` | Core graph nodes |
| `apps/agents/agents/jd_generation/crew_agents.py` | `JDGeneratorAgent.generate_jd` | Primary JD LLM step |
| `apps/api/app/services/jd_pipeline_service.py` | `store_jd` | Save job + pgvector |

---

## QuantChat (QueryRouter)

| File | Show this function | What it does |
|------|-------------------|--------------|
| `apps/web/src/components/QuantChat.tsx` | `handleSubmit` | Sends chat message |
| `apps/api/app/api/v1/quantchat.py` | `ai_chat` | API entry → QueryRouter |
| `apps/quantchat/core/query_router.py` | `route_query` | Routes intent, runs pipeline |
| `apps/quantchat/core/query_router.py` | `_handle_rag_pipeline` | Hybrid RAG path |
| `apps/quantchat/core/intent_classifier.py` | `classify` | RAG vs general intent |
| `apps/quantchat/retrieval/vector_retriever.py` | `retrieve` | Semantic search |
| `apps/quantchat/retrieval/keyword_retriever.py` | `retrieve` | Keyword search |
| `apps/quantchat/fusion/rrf_fusion.py` | `fuse` | Merge vector + keyword results |
| `apps/quantchat/reranking/reranker.py` | `rerank` | Re-score top chunks |
| `apps/quantchat/generation/rag_generator.py` | `generate` | LLM answer with context |

---

## Job matching (HSS-D swarm)

| File | Show this function | What it does |
|------|-------------------|--------------|
| `apps/web/src/app/dashboard/job-matching/page.tsx` | (page) | Matching UI entry |
| `apps/api/app/api/v1/job_matching.py` | `match` | JSON match result |
| `apps/api/app/api/v1/job_matching.py` | `match_stream` | SSE live agent thoughts |
| `apps/agents/agents/job_matching/orchestrator.py` | `match` / `stream` | Public orchestrator API |
| `apps/agents/agents/job_matching/orchestrator.py` | `_run_swarm` | Parallel specialist agents |
| `apps/agents/agents/job_matching/orchestrator.py` | `_run_debate` | Synthesizer → critic → arbitrator |
| `apps/agents/agents/job_matching/swarm_agents.py` | `BaseSpecialistAgent.run` | One dimension score (skills, etc.) |
| `apps/agents/agents/job_matching/debate_agents.py` | `SynthesizerAgent.run` | Builds match synthesis |
| `apps/agents/agents/job_matching/debate_agents.py` | `ArbitratorAgent.run` | Final match decision |
| `apps/agents/agents/job_matching/data_access_pg.py` | (load helpers) | Load candidate + JD from DB/pgvector |

---

## Shared (one slide)

| File | Show this function | What it does |
|------|-------------------|--------------|
| `apps/web/src/app/api/[...path]/route.ts` | proxy handler | BFF → FastAPI |
| `apps/agents/agents/llm/chat_factory.py` | `create_chat_llm` | All agents’ LLM client |

---

## 30-second demo paths

| System | Open in order |
|--------|----------------|
| Resume | `upload_resume` → `parse_and_store` → `execute` |
| JD | `handleGenerate` → `_execute_jd_generation_core` → `run` |
| QuantChat | `ai_chat` → `route_query` → `_handle_rag_pipeline` |
| Matching | `match_stream` → `_run_swarm` → `_run_debate` |
