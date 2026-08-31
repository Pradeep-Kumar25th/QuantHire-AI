"""
Query Router - Main Orchestration
==================================

Production-ready query router with comprehensive error handling and monitoring.
"""

from typing import Dict, Any, Optional
from ..config.logging_config import setup_logger
from ..config.settings import (
    ENABLE_FALLBACKS, FALLBACK_TO_CACHE, FALLBACK_TO_CHUNKS,
    ENABLE_MONITORING, LOG_QUERY_LATENCY, LLM_MODEL
)
from ..utils.tracing import traceable, trace_metadata
import time

from .intent_classifier import IntentClassifier, Intent
from .query_normalizer import QueryNormalizer
from ..retrieval.query_expander import QueryExpander
from ..retrieval.metadata_filter import MetadataFilter
from ..retrieval.vector_retriever import VectorRetriever
from ..retrieval.keyword_retriever import KeywordRetriever
from ..retrieval.full_doc_retriever import FullDocumentRetriever
from ..fusion.rrf_fusion import ReciprocalRankFusion
from ..reranking.reranker import Reranker
from ..context.context_builder import ContextBuilder
from ..generation.rag_generator import RAGAnswerGenerator
from ..generation.general_generator import GeneralAnswerGenerator
from ..generation.formatter import ResponseFormatter
from ..memory.conversation_memory import ConversationMemory

# Import caching for RAG results
try:
    from ..utils.cache import get_cached_rag_result, cache_rag_result
    CACHING_AVAILABLE = True
except ImportError:
    CACHING_AVAILABLE = False

# Optional monitoring
try:
    from ..monitoring.rag_monitor import RAGMonitor as RAGMonitor
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    RAGMonitor = None

# Agent Observability
try:
    from ..monitoring.agent_observability import AgentObservabilityManager
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
    AgentObservabilityManager = None

logger = setup_logger("query_router")

class QueryRouter:
    """
    Main query router for QuantChat AI.
    
    Orchestrates the complete RAG pipeline:
    1. Query understanding (intent classification, entity extraction)
    2. Query expansion (multi-query, synonyms)
    3. Hybrid retrieval (vector + keyword)
    4. RRF fusion
    5. Multi-stage reranking
    6. Smart context building
    7. LLM generation
    8. Response formatting
    """
    
    def __init__(self):
        # Core components
        self.normalizer = QueryNormalizer()
        self.classifier = IntentClassifier()
        self.query_expander = QueryExpander()
        self.metadata_filter = MetadataFilter()
        
        # Retrieval components
        self.vector_retriever = VectorRetriever()
        self.keyword_retriever = KeywordRetriever()
        self.full_doc_retriever = FullDocumentRetriever()
        
        # Fusion and reranking
        self.rrf = ReciprocalRankFusion()
        self.reranker = Reranker()
        
        # Context and generation
        self.context_builder = ContextBuilder()
        self.rag_generator = RAGAnswerGenerator()
        self.general_generator = GeneralAnswerGenerator()
        self.formatter = ResponseFormatter()
        
        # Memory
        self.memory = ConversationMemory()
        
        # Monitoring
        self.monitor = RAGMonitor() if MONITORING_AVAILABLE else None
        
        # Agent Observability (full production-grade)
        from ..config.settings import ENABLE_OBSERVABILITY
        self.observability = (
            AgentObservabilityManager()
            if OBSERVABILITY_AVAILABLE and ENABLE_OBSERVABILITY
            else None
        )
    
    @traceable(run_type="chain", name="QueryRouter.route_query")
    def route_query(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route query through appropriate pipeline.
        
        Args:
            query: User query
            session_id: Session identifier for conversation memory
        
        Returns:
            Response dictionary with answer and metadata
        """
        start_time = time.time()
        session_id = session_id or "default"
        obs_trace_id = None
        
        # Start observability trace
        if self.observability:
            obs_trace_id = self.observability.start_trace(query, session_id)
        
        try:
            logger.info(f"[trace={obs_trace_id or 'none'}] Processing query: {query[:100]}")
            
            # 0. Check RAG cache for exact match (stateless queries only)
            if CACHING_AVAILABLE and session_id == "default":
                cached_result = get_cached_rag_result(query, session_id)
                if cached_result:
                    cached_result["cached"] = True
                    cached_result["latency"] = time.time() - start_time
                    if self.observability and obs_trace_id:
                        self.observability.complete_trace(
                            obs_trace_id, response=cached_result.get("response", ""),
                            context="", source="cache", confidence=cached_result.get("confidence", 0.9),
                            total_latency_ms=(time.time() - start_time) * 1000,
                            cached=True,
                        )
                    cached_result["obs_trace_id"] = obs_trace_id
                    return cached_result
            
            # 1. Normalize query
            t0 = time.time()
            normalized_query = self.normalizer.normalize(query)
            if self.observability and obs_trace_id:
                self.observability.record_step_latency(obs_trace_id, "normalize", (time.time() - t0) * 1000)
            
            # 2. Get conversation context
            conversation_history = self.memory.get_history(session_id)
            tracked_entities = self.memory.get_tracked_entities(session_id)
            
            # 3. Enhance query with context
            enhanced_query = self.normalizer.enhance_with_context(normalized_query, tracked_entities)
            
            # 4. Classify intent
            t0 = time.time()
            intent_result = self.classifier.classify(enhanced_query, conversation_history)
            intent_latency = (time.time() - t0) * 1000
            if self.observability and obs_trace_id:
                self.observability.record_step_latency(obs_trace_id, "intent_classify", intent_latency)
                if intent_result.classification_method == "llm":
                    self.observability.record_llm_call(
                        obs_trace_id, model=LLM_MODEL,
                        input_text=enhanced_query, output_text=str(intent_result.to_dict()),
                    )
            
            logger.info(f"Classified intent: {intent_result.to_dict()}")
            trace_metadata({
                "intent": intent_result.intent.value,
                "domain": intent_result.domain.value,
                "entity_names": intent_result.entity_names,
                "session_id": session_id,
            })
            
            # 5. Route based on intent
            context_for_eval = ""
            if intent_result.intent == Intent.GENERAL_KNOWLEDGE:
                pipeline_route = "general_knowledge"
                result = self._handle_general_knowledge(enhanced_query, obs_trace_id=obs_trace_id)
            
            elif intent_result.intent == Intent.FULL_DOCUMENT:
                pipeline_route = "full_document"
                result = self._handle_full_document(intent_result, session_id, tracked_entities, obs_trace_id=obs_trace_id)
            
            elif intent_result.intent == Intent.COMPARISON:
                pipeline_route = "comparison_rag"
                result = self._handle_comparison(enhanced_query, intent_result, conversation_history, session_id,
                                                  tracked_entities=tracked_entities, obs_trace_id=obs_trace_id)
            
            else:
                pipeline_route = "rag_pipeline"
                result = self._handle_rag_pipeline(
                    enhanced_query, intent_result, conversation_history,
                    tracked_entities, session_id, obs_trace_id=obs_trace_id
                )
                context_for_eval = result.get("_context", "")
            
            # Record intent decision in observability audit trail (after route is determined)
            if self.observability and obs_trace_id:
                self.observability.record_intent(
                    obs_trace_id,
                    intent=intent_result.intent.value,
                    domain=intent_result.domain.value,
                    entity_names=intent_result.entity_names,
                    pipeline_route=pipeline_route,
                    confidence=intent_result.confidence,
                )
            
            # 6. Update conversation memory
            self.memory.add_turn(
                session_id=session_id,
                user_query=query,
                assistant_response=result.get("response", ""),
                entities=intent_result.entity_names
            )
            
            # 7. Track metrics
            latency = time.time() - start_time
            result["latency"] = latency
            result["obs_trace_id"] = obs_trace_id
            
            if self.monitor:
                self.monitor.track_query(
                    query=query,
                    response=result.get("response", ""),
                    latency=latency,
                    chunks_retrieved=result.get("chunks_retrieved", 0),
                    chunks_used=result.get("chunks_used", 0),
                    intent=intent_result.intent.value,
                    source=result.get("source", "unknown")
                )
            elif LOG_QUERY_LATENCY:
                logger.info(f"Query latency: {latency:.2f}s")
            
            # 8. Complete observability trace (evaluation + alerting + cost)
            if self.observability and obs_trace_id:
                self.observability.complete_trace(
                    obs_trace_id,
                    response=result.get("response", ""),
                    context=context_for_eval,
                    source=result.get("source", "unknown"),
                    confidence=result.get("confidence", 0.5),
                    total_latency_ms=latency * 1000,
                    validation_passed=result.get("validation", {}).get("valid", True) if isinstance(result.get("validation"), dict) else True,
                )
            
            # Remove internal context from response (not for client)
            result.pop("_context", None)
            
            # 9. Cache result for stateless queries
            if CACHING_AVAILABLE and session_id == "default":
                cache_rag_result(query, result, session_id)
            
            return result
        
        except Exception as e:
            logger.error(f"Query routing failed: {e}", exc_info=True)
            
            # Record error in observability
            if self.observability and obs_trace_id:
                self.observability.complete_trace(
                    obs_trace_id, response="", context="",
                    source="error", confidence=0.0,
                    total_latency_ms=(time.time() - start_time) * 1000,
                    error=str(e),
                )
            
            return self._handle_error(query, e, session_id, obs_trace_id=obs_trace_id)
    
    @traceable(run_type="chain", name="RAG_Pipeline")
    def _handle_rag_pipeline(
        self,
        query: str,
        intent_result: Any,
        conversation_history: str,
        tracked_entities: list,
        session_id: str,
        obs_trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle RAG pipeline for resume/JD queries."""
        logger.info("Routing to RAG Pipeline")
        
        # 1. Build filters
        filters = self.metadata_filter.build_filters(intent_result)
        
        # 2. Expand query (may include LLM call for multi-query generation)
        t0 = time.time()
        query_variations = self.query_expander.expand(query)
        expansion_latency = (time.time() - t0) * 1000
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "query_expansion", expansion_latency)
            # Only record LLM cost when multi-query is enabled AND the LLM was available
            # Synonym-only expansion doesn't use the LLM
            from ..config.settings import ENABLE_MULTI_QUERY
            if ENABLE_MULTI_QUERY and self.query_expander.llm_generator:
                self.observability.record_llm_call(
                    obs_trace_id, model=LLM_MODEL,
                    input_text=query, output_text=str(query_variations),
                )
        
        # 3. Multi-query retrieval
        t0 = time.time()
        all_vector_results = []
        all_keyword_results = []
        
        for q_var in query_variations:
            try:
                vector_chunks = self.vector_retriever.retrieve(q_var, filters)
                all_vector_results.extend(vector_chunks)
                
                keyword_chunks = self.keyword_retriever.retrieve(q_var, filters)
                all_keyword_results.extend(keyword_chunks)
            except Exception as e:
                logger.warning(f"Retrieval failed for query variation: {e}")
                continue
        
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "retrieval", (time.time() - t0) * 1000)
        
        # 4. RRF fusion
        if not all_vector_results and not all_keyword_results:
            logger.warning("No retrieval results - returning empty response")
            if self.observability and obs_trace_id:
                self.observability.record_retrieval(
                    obs_trace_id, query_variations=len(query_variations),
                    vector_chunks=0, keyword_chunks=0, fused_chunks=0, reranked_chunks=0,
                )
            return {
                "response": "I couldn't find any relevant information in the database. Please try rephrasing your query.",
                "source": "rag_pipeline",
                "chunks_used": 0,
                "confidence": 0.1
            }
        
        t0 = time.time()
        fused_chunks = self.rrf.fuse([all_vector_results, all_keyword_results])
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "rrf_fusion", (time.time() - t0) * 1000)
        
        # Track retrieval metrics
        if self.monitor:
            self.monitor.track_retrieval(
                query=query,
                vector_count=len(all_vector_results),
                keyword_count=len(all_keyword_results),
                fused_count=len(fused_chunks),
                reranked_count=0
            )
        
        # 5. Reranking
        t0 = time.time()
        reranked_chunks = self.reranker.rerank(query, fused_chunks)
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "reranking", (time.time() - t0) * 1000)
        
        # 6. Fallback if too few chunks
        if len(reranked_chunks) < 5 and (filters.get("section_type") or filters.get("entity_names")):
            logger.info("Too few chunks, relaxing filters...")
            relaxed_filters = self.metadata_filter.build_relaxed_filters(filters, drop_section=True)
            vector_chunks = self.vector_retriever.retrieve(query, relaxed_filters)
            keyword_chunks = self.keyword_retriever.retrieve(query, relaxed_filters)
            fused_chunks = self.rrf.fuse([vector_chunks, keyword_chunks])
            reranked_chunks = self.reranker.rerank(query, fused_chunks)
        
        # Record retrieval metrics in observability
        if self.observability and obs_trace_id:
            self.observability.record_retrieval(
                obs_trace_id,
                query_variations=len(query_variations),
                vector_chunks=len(all_vector_results),
                keyword_chunks=len(all_keyword_results),
                fused_chunks=len(fused_chunks),
                reranked_chunks=len(reranked_chunks),
            )
        
        # 7. Build context
        t0 = time.time()
        context = self.context_builder.build_context(
            chunks=reranked_chunks,
            query=query,
            conversation_history=conversation_history,
            tracked_entities=tracked_entities
        )
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "context_build", (time.time() - t0) * 1000)
            self.observability.record_context(obs_trace_id, len(reranked_chunks), context)
        
        # 8. Generate answer
        t0 = time.time()
        answer_data = self.rag_generator.generate(
            query=query,
            context=context,
            intent=intent_result.intent.value,
            entity_names=intent_result.entity_names,
            section=intent_result.section
        )
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "llm_generation", (time.time() - t0) * 1000)
            actual_model = getattr(self.rag_generator.llm_generator, 'last_model_used', LLM_MODEL)
            self.observability.record_llm_call(
                obs_trace_id, model=actual_model,
                input_text=context, output_text=answer_data.get("response", ""),
            )
        
        # 9. Format response
        sources = [
            {
                "doc_type": chunk.get("doc_type"),
                "entity_name": chunk.get("entity_name"),
                "section": chunk.get("section")
            }
            for chunk in reranked_chunks[:3]
        ]
        
        formatted_response = self.formatter.format_rag_response(
            response=answer_data["response"],
            sources=sources,
            entity_names=intent_result.entity_names,
            section=intent_result.section
        )
        
        result = {
            "response": formatted_response,
            "source": "rag_pipeline",
            "chunks_retrieved": len(fused_chunks),
            "chunks_used": len(reranked_chunks),
            "confidence": answer_data.get("confidence", 0.9),
            "validation": answer_data.get("validation", {}),
            "_context": context,
        }
        
        trace_metadata({
            "vector_results": len(all_vector_results),
            "keyword_results": len(all_keyword_results),
            "fused_chunks": len(fused_chunks),
            "reranked_chunks": len(reranked_chunks),
            "confidence": result["confidence"],
        })
        
        return result
    
    @traceable(run_type="chain", name="FullDocument_Pipeline")
    def _handle_full_document(
        self,
        intent_result: Any,
        session_id: str,
        tracked_entities: list = None,
        obs_trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle full document retrieval."""
        logger.info("Routing to Full Document Pipeline")
        
        entity_names = intent_result.entity_names
        doc_type = "resume" if intent_result.domain.value == "resume" else "jd"
        
        if not entity_names and tracked_entities:
            logger.info(f"No entity in query, using tracked entities from context: {tracked_entities}")
            entity_names = [tracked_entities[-1]]
        
        if not entity_names:
            return {
                "response": "Please specify which resume or JD you'd like to see. For example: 'Show me Priya Singh's full resume'",
                "source": "full_document",
                "confidence": 0.5
            }
        
        # Retrieve full document
        t0 = time.time()
        full_doc = self.full_doc_retriever.retrieve_full_document(
            document_type=doc_type,
            entity_name=entity_names[0]
        )
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "full_doc_retrieve", (time.time() - t0) * 1000)
        
        if not full_doc:
            return {
                "response": f"I couldn't find a {doc_type} for {entity_names[0]}. Please check the name and try again.",
                "source": "full_document",
                "confidence": 0.3
            }
        
        # Format response
        t0 = time.time()
        formatted = self.formatter.format_full_doc_response(
            full_content=full_doc["full_content"],
            document_type=doc_type,
            entity_name=full_doc["entity_name"]
        )
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "format_response", (time.time() - t0) * 1000)
        
        return {
            "response": formatted,
            "source": "full_document",
            "confidence": 0.95
        }
    
    @traceable(run_type="chain", name="GeneralKnowledge_Pipeline")
    def _handle_general_knowledge(self, query: str, obs_trace_id: Optional[str] = None) -> Dict[str, Any]:
        """Handle general knowledge questions."""
        logger.info("Routing to General Knowledge Pipeline")
        
        t0 = time.time()
        answer_data = self.general_generator.generate(query)
        if self.observability and obs_trace_id:
            self.observability.record_step_latency(obs_trace_id, "general_llm", (time.time() - t0) * 1000)
            actual_model = getattr(self.general_generator.llm_generator, 'last_model_used', LLM_MODEL)
            self.observability.record_llm_call(
                obs_trace_id, model=actual_model,
                input_text=query, output_text=answer_data.get("response", ""),
            )
        
        formatted = self.formatter.format_general_response(answer_data["response"])
        
        return {
            "response": formatted,
            "source": "general_knowledge",
            "confidence": answer_data.get("confidence", 0.8)
        }
    
    @traceable(run_type="chain", name="Comparison_Pipeline")
    def _handle_comparison(
        self,
        query: str,
        intent_result: Any,
        conversation_history: str,
        session_id: str,
        tracked_entities: list = None,
        obs_trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle comparison queries."""
        logger.info("Routing to Comparison Pipeline")
        
        return self._handle_rag_pipeline(
            query, intent_result, conversation_history,
            tracked_entities or [],
            session_id, obs_trace_id=obs_trace_id
        )
    
    def _handle_error(self, query: str, error: Exception, session_id: str,
                      obs_trace_id: str = None) -> Dict[str, Any]:
        """Handle errors with fallbacks."""
        logger.error(f"Error in query routing: {error}")
        
        if FALLBACK_TO_CHUNKS:
            try:
                for doc_type in ("resume", "jd"):
                    filters = {"document_type": doc_type}
                    chunks = self.vector_retriever.retrieve(query, filters)
                    if chunks:
                        return {
                            "response": f"Based on available information:\n\n{chunks[0].get('content', '')[:500]}...",
                            "source": "error_fallback",
                            "confidence": 0.3,
                            "obs_trace_id": obs_trace_id,
                        }
            except Exception:
                pass
        
        return {
            "response": "I apologize, but I'm experiencing technical difficulties. Please try again in a moment.",
            "source": "error",
            "confidence": 0.1,
            "obs_trace_id": obs_trace_id,
        }
