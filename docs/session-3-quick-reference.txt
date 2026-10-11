# Session 3 Quick Reference

QuantHire AI - Session 3: AI Components, Agentic Workflows and Observability

How to open this file:
- Path: docs/session-3-quick-reference.md (inside docs folder at repo root)
- Copy: SESSION-3-QUICK-REFERENCE.md at repo root
- Copy: docs/Session3QuickReference.md
- Plain text: docs/session-3-quick-reference.txt

---

## 1. QuantChat

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/quantchat.py | ai_chat | 90 | Chat API entry |
| Router | apps/quantchat/core/query_router.py | route_query | 109 | Main router |
| Router | apps/quantchat/core/query_router.py | _handle_rag_pipeline | 280 | RAG pipeline |
| Intent | apps/quantchat/core/intent_classifier.py | classify | 94 | Classify intent |
| Vector | apps/quantchat/retrieval/vector_retriever.py | retrieve | 85 | Vector search |
| Keyword | apps/quantchat/retrieval/keyword_retriever.py | retrieve | 59 | Keyword search |
| Fusion | apps/quantchat/fusion/rrf_fusion.py | fuse | 33 | RRF fusion |
| Rerank | apps/quantchat/reranking/reranker.py | rerank | 51 | Rerank |
| Context | apps/quantchat/context/context_builder.py | build_context | 65 | Build context |
| Generate | apps/quantchat/generation/rag_generator.py | generate | 28 | Generate answer |

Demo: line 90 -> 109 -> 280 -> 28

---

## 2. JD generation

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| UI | apps/web/src/components/jobs/jd-generation-dialog.tsx | handleGenerate | 451 | UI generate |
| API | apps/api/app/api/v1/jd_generation.py | _execute_jd_generation_core | 1240 | Execute core |
| API | apps/api/app/api/v1/jd_generation.py | _apply_hr_inputs_to_jd | 974 | HR inputs |
| Orchestrator | apps/agents/agents/jd_generation/orchestrator.py | generate_job_description | 118 | Orchestrator |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | generate_jd | 371 | Generate node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | refine_jd | 441 | Refine node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | validate_jd | 516 | Validate node |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | prepare_jd | 636 | Prepare job_id |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | _build_graph | 807 | Build graph |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | _route_after_prepare | 852 | Route NPD |
| Workflow | apps/agents/agents/jd_generation/state_machine.py | run | 863 | Run workflow |
| Persist | apps/api/app/services/jd_pipeline_service.py | store_jd | 157 | Store JD |

Demo: line 451 -> 1240 -> 863

---

## 3. Resume parsing

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/resume_parsing.py | upload_resume | 322 | Upload |
| Extract | apps/api/app/services/pdf_extraction.py | extract_resume_text | 169 | Extract |
| Pipeline | apps/api/app/services/resume_pipeline_service.py | parse_and_store | 60 | Pipeline |
| Agent | apps/agents/agents/parsing/agent.py | execute | 262 | Parse agent |
| Vectors | apps/api/app/services/pgvector_ingestion.py | add_resume | 293 | Index |

Demo: line 322 -> 169 -> 60 -> 262

---

## 4. Job matching

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| API | apps/api/app/api/v1/job_matching.py | match_stream | 283 | SSE stream |
| API | apps/api/app/api/v1/job_matching.py | match | 254 | JSON match |
| Orchestrator | apps/agents/agents/job_matching/orchestrator.py | _run_swarm | 389 | Swarm |
| Orchestrator | apps/agents/agents/job_matching/orchestrator.py | _run_debate | 493 | Debate |
| Debate | apps/agents/agents/job_matching/debate_agents.py | ArbitratorAgent.run | 290 | Final decision |
| Verify | apps/agents/agents/job_matching/evidence_verifier.py | verify_swarm | 330 | Verify evidence |

Demo: line 283 -> 389 -> 493 -> 290

---

## 5. LLM

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| Factory | apps/agents/agents/llm/chat_factory.py | create_chat_llm | 211 | Create LLM |
| Factory | apps/agents/agents/llm/chat_factory.py | llm_provider | 80 | Provider |

---

## 6. Evaluation

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| Eval | apps/quantchat/monitoring/agent_observability.py | RAGEvaluator.evaluate | 227 | RAG eval |
| Eval | apps/quantchat/monitoring/agent_observability.py | complete_trace | 472 | Complete trace |
| Hiring | apps/api/app/api/v1/feedback.py | create_feedback | 185 | Hiring feedback |

---

## 7. Observability

| Area | File | Function | Line | Brief |
|------|------|----------|------|-------|
| Trace | apps/quantchat/monitoring/agent_observability.py | start_trace | 374 | Start trace |
| Trace | apps/quantchat/monitoring/agent_observability.py | complete_trace | 472 | End trace |
| API | apps/api/app/api/v1/quantchat.py | get_quantchat_status | 199 | Status |

---

END OF SESSION 3 QUICK REFERENCE
