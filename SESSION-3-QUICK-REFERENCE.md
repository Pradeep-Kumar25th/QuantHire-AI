# Also at repo root: SESSION-3-QUICK-REFERENCE.md

# Session 3 Quick Reference Guide

QuantHire AI - AI Components, Agentic Workflows and Observability

Line numbers = IDE Go to line. Full doc: docs/session-3-ai-components-complete.md

---

## 1. QuantChat (RAG pipeline)

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/quantchat.py | ai_chat | 90 | Chat API entry |
| Router | apps/quantchat/core/query_router.py | route_query | 109 | Intent and branch |
| Router | apps/quantchat/core/query_router.py | _handle_rag_pipeline | 280 | Hybrid RAG main path |
| Intent | apps/quantchat/core/intent_classifier.py | classify | 94 | RAG vs general vs full doc |
| Intent | apps/quantchat/core/intent_classifier.py | _fallback_classify | 210 | Regex fallback |
| Vector | apps/quantchat/retrieval/vector_retriever.py | retrieve | 85 | Semantic pgvector search |
| Keyword | apps/quantchat/retrieval/keyword_retriever.py | retrieve | 59 | Keyword search |
| Fusion | apps/quantchat/fusion/rrf_fusion.py | fuse | 33 | RRF merge lists |
| Rerank | apps/quantchat/reranking/reranker.py | rerank | 51 | Re-score chunks |
| Context | apps/quantchat/context/context_builder.py | build_context | 65 | Build LLM context |
| Generate | apps/quantchat/generation/rag_generator.py | generate | 28 | Grounded answer |

Demo: 90 -> 109 -> 280 -> 28

Other routes: _handle_general_knowledge 509 | _handle_full_document 452 | _handle_comparison 532

---

## 2. JD generation (LangGraph)

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| UI | apps/web/src/components/jobs/jd-generation-dialog.tsx | handleGenerate | 451 | Start generate |
| API | apps/api/app/api/v1/jd_generation.py | _execute_jd_generation_core | 1240 | Orchestrator and save |
| API | apps/api/app/api/v1/jd_generation.py | _apply_hr_inputs_to_jd | 974 | HR matrix overlay |
| Orchestrator | apps/agents/agents/jd_generation/orchestrator.py | generate_job_description | 118 | Graph entry |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | generate_jd | 371 | Generator node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | refine_jd | 441 | Refiner node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | validate_jd | 516 | Validator node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | prepare_jd | 636 | Assign job_id |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | _build_graph | 807 | Graph nodes and edges |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | _route_after_prepare | 852 | NPD skip Milvus |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | run | 863 | Run graph |
| Persist | apps/api/app/services/jd_pipeline_service.py | store_jd | 157 | Postgres pgvector |

Demo: 451 -> 1240 -> 863

---

## 3. Resume parsing

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/resume_parsing.py | upload_resume | 322 | Upload and validate |
| Extract | apps/api/app/services/pdf_extraction.py | extract_resume_text | 169 | Text extraction |
| Pipeline | apps/api/app/services/resume_pipeline_service.py | parse_and_store | 60 | Agent and DB |
| Agent | apps/agents/agents/parsing/agent.py | execute | 262 | LLM parse JSON |
| Vectors | apps/api/app/services/pgvector_ingestion.py | add_resume | 293 | Vector index |

Demo: 322 -> 169 -> 60 -> 262

---

## 4. Job matching

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/job_matching.py | match_stream | 283 | SSE stream |
| API | apps/api/app/api/v1/job_matching.py | match | 254 | JSON match |
| Orchestrator | apps/agents/agents/job_matching/orchestrator.py | _run_swarm | 389 | Parallel specialists |
| Orchestrator | apps/agents/agents/job_matching/orchestrator.py | _run_debate | 493 | Debate chain |
| Debate | apps/agents/agents/job_matching/debate_agents.py | ArbitratorAgent.run | 290 | Final decision |
| Verify | apps/agents/agents/job_matching/evidence_verifier.py | verify_swarm | 330 | Ground evidence |

Demo: 283 -> 389 -> 493 -> 290

---

## 5. LLM configuration

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| Factory | apps/agents/agents/llm/chat_factory.py | create_chat_llm | 211 | All agents LLM |
| Factory | apps/agents/agents/llm/chat_factory.py | llm_provider | 80 | Provider switch |
| Factory | apps/agents/agents/llm/chat_factory.py | fallback_llm_model | 109 | Fallback model |
| Config | apps/quantchat/config/settings.py | LLM_MODEL | 89 | QuantChat model |
| Config | apps/api/app/config.py | Settings | 11 | App settings |

NPD env: LLM_PROVIDER=azure_openai, AZURE_OPENAI_*, VECTOR_STORE=pgvector

---

## 6. Evaluation and feedback

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| RAG eval | apps/quantchat/monitoring/agent_observability.py | RAGEvaluator.evaluate | 227 | Quality scores |
| RAG eval | apps/quantchat/monitoring/agent_observability.py | complete_trace | 472 | Eval on trace end |
| Guard | apps/quantchat/generation/rag_generator.py | _validate_response | 111 | Context check |
| Hiring | apps/api/app/api/v1/feedback.py | create_feedback | 185 | DB feedback |
| Hiring | apps/api/app/api/v1/feedback.py | analyze_feedback | 358 | Drift analysis |
| Chat FB | apps/quantchat/monitoring/agent_observability.py | record_feedback | 545 | In-process only |

---

## 7. Observability

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| Trace | apps/quantchat/monitoring/agent_observability.py | start_trace | 374 | Start trace |
| Trace | apps/quantchat/monitoring/agent_observability.py | complete_trace | 472 | Latency cost quality |
| Dashboard | apps/quantchat/monitoring/agent_observability.py | get_full_dashboard | 1034 | Dashboard JSON |
| API | apps/api/app/api/v1/quantchat.py | get_quantchat_status | 199 | Router health |
| Toggle | apps/quantchat/config/settings.py | ENABLE_OBSERVABILITY | 116 | On or off |

Gap: mount /v1/quantchat/observability/* for web dashboard client.

---

## 8. One-line summary

QuantChat route_query and RAG generate; JD LangGraph run and store_jd; resume execute; matching swarm and debate; create_chat_llm; RAGEvaluator and hiring feedback.

---

End of Session 3 Quick Reference
