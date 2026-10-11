# Session 3 Quick Reference Guide

QuantHire AI | AI Components, Agentic Workflows and Observability

Line = IDE Go to line. Full doc: docs/session-3-ai-components-complete.md

Alternate copy at repo root: SESSION-3-QUICK-REFERENCE.md

---

## 1 QuantChat RAG pipeline

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/quantchat.py | ai_chat | 90 | Chat entry |
| Router | apps/quantchat/core/query_router.py | route_query | 109 | Intent and branch |
| Router | apps/quantchat/core/query_router.py | _handle_rag_pipeline | 280 | Hybrid RAG path |
| Intent | apps/quantchat/core/intent_classifier.py | classify | 94 | Intent classification |
| Intent | apps/quantchat/core/intent_classifier.py | _fallback_classify | 210 | Regex fallback |
| Vector | apps/quantchat/retrieval/vector_retriever.py | retrieve | 85 | Vector search |
| Keyword | apps/quantchat/retrieval/keyword_retriever.py | retrieve | 59 | Keyword search |
| Fusion | apps/quantchat/fusion/rrf_fusion.py | fuse | 33 | RRF fusion |
| Rerank | apps/quantchat/reranking/reranker.py | rerank | 51 | Rerank chunks |
| Context | apps/quantchat/context/context_builder.py | build_context | 65 | Build context |
| Generate | apps/quantchat/generation/rag_generator.py | generate | 28 | LLM answer |

Demo lines: 90 then 109 then 280 then 28

---

## 2 JD generation LangGraph

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| UI | apps/web/src/components/jobs/jd-generation-dialog.tsx | handleGenerate | 451 | Start JD |
| API | apps/api/app/api/v1/jd_generation.py | _execute_jd_generation_core | 1240 | Core execute |
| API | apps/api/app/api/v1/jd_generation.py | _apply_hr_inputs_to_jd | 974 | HR overlay |
| Orchestrator | apps/agents/agents/jd_generation/orchestrator.py | generate_job_description | 118 | Orchestrator |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | generate_jd | 371 | Generator node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | refine_jd | 441 | Refiner node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | validate_jd | 516 | Validator node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | prepare_jd | 636 | Assign job_id |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | _build_graph | 807 | Graph build |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | _route_after_prepare | 852 | NPD route |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | run | 863 | Run graph |
| Persist | apps/api/app/services/jd_pipeline_service.py | store_jd | 157 | Save JD |

Demo lines: 451 then 1240 then 863

---

## 3 Resume parsing

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/resume_parsing.py | upload_resume | 322 | Upload |
| Extract | apps/api/app/services/pdf_extraction.py | extract_resume_text | 169 | Extract text |
| Pipeline | apps/api/app/services/resume_pipeline_service.py | parse_and_store | 60 | Pipeline |
| Agent | apps/agents/agents/parsing/agent.py | execute | 262 | Parse agent |
| Vectors | apps/api/app/services/pgvector_ingestion.py | add_resume | 293 | Vectors |

Demo lines: 322 then 169 then 60 then 262

---

## 4 Job matching

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/job_matching.py | match_stream | 283 | SSE |
| API | apps/api/app/api/v1/job_matching.py | match | 254 | JSON |
| Orchestrator | apps/agents/agents/job_matching/orchestrator.py | _run_swarm | 389 | Swarm |
| Orchestrator | apps/agents/agents/job_matching/orchestrator.py | _run_debate | 493 | Debate |
| Debate | apps/agents/agents/job_matching/debate_agents.py | ArbitratorAgent.run | 290 | Final score |
| Verify | apps/agents/agents/job_matching/evidence_verifier.py | verify_swarm | 330 | Evidence |

Demo lines: 283 then 389 then 493 then 290

---

## 5 LLM config

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| Factory | apps/agents/agents/llm/chat_factory.py | create_chat_llm | 211 | LLM factory |
| Factory | apps/agents/agents/llm/chat_factory.py | llm_provider | 80 | Provider |
| Config | apps/quantchat/config/settings.py | LLM_MODEL | 89 | Model name |
| Config | apps/api/app/config.py | Settings | 11 | Settings |

---

## 6 Evaluation feedback

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| Eval | apps/quantchat/monitoring/agent_observability.py | RAGEvaluator.evaluate | 227 | RAG scores |
| Eval | apps/quantchat/monitoring/agent_observability.py | complete_trace | 472 | On trace end |
| Guard | apps/quantchat/generation/rag_generator.py | _validate_response | 111 | Validate |
| Hiring | apps/api/app/api/v1/feedback.py | create_feedback | 185 | Hiring FB |
| Chat | apps/quantchat/monitoring/agent_observability.py | record_feedback | 545 | Chat FB in-memory |

---

## 7 Observability

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| Trace | apps/quantchat/monitoring/agent_observability.py | start_trace | 374 | Start |
| Trace | apps/quantchat/monitoring/agent_observability.py | complete_trace | 472 | Complete |
| Dash | apps/quantchat/monitoring/agent_observability.py | get_full_dashboard | 1034 | Dashboard |
| API | apps/api/app/api/v1/quantchat.py | get_quantchat_status | 199 | Status |

---

End Session 3 Quick Reference
