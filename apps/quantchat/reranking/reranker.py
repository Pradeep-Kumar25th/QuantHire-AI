"""
Multi-Stage Reranker
=====================

Reranks retrieved chunks using cross-encoder and optionally LLM-based reranking.
"""

from typing import List, Dict, Any
from ..config.logging_config import setup_logger
from ..config.settings import (
    ENABLE_RERANKING, RERANK_STAGE1_LIMIT, RERANK_STAGE2_LIMIT,
    ENABLE_LLM_RERANKING
)
from ..generation.llm_generator import LLMGenerator
from ..utils.tracing import traceable, trace_metadata

logger = setup_logger("reranker")

# Try to import cross-encoder
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    logger.warning("CrossEncoder not available - reranking will be limited")

class Reranker:
    """
    Multi-stage reranker for improved relevance.
    
    Stage 1: Cross-encoder (fast, good accuracy)
    Stage 2: LLM-based (slower, highest accuracy, optional)
    """
    
    def __init__(self):
        self.cross_encoder = None
        try:
            self.llm_generator = LLMGenerator() if ENABLE_LLM_RERANKING else None
        except Exception as e:
            logger.warning(f"LLM generator not available for reranking: {e}")
            self.llm_generator = None
        
        if CROSS_ENCODER_AVAILABLE:
            try:
                self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
                logger.info("CrossEncoder loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load CrossEncoder: {e}")
    
    @traceable(run_type="chain", name="Reranker.rerank")
    def rerank(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank chunks using multi-stage approach.
        
        Args:
            query: User query
            chunks: Chunks to rerank
        
        Returns:
            Reranked chunks
        """
        if not ENABLE_RERANKING or not chunks:
            return chunks
        
        logger.info(f"Reranking {len(chunks)} chunks")
        
        # Stage 1: Cross-encoder reranking
        if self.cross_encoder and len(chunks) > 1:
            stage1_chunks = self._cross_encoder_rerank(query, chunks)
        else:
            stage1_chunks = chunks
        
        # Stage 2: LLM-based reranking (optional, for top N)
        if ENABLE_LLM_RERANKING and self.llm_generator and len(stage1_chunks) > RERANK_STAGE2_LIMIT:
            final_chunks = self._llm_rerank(query, stage1_chunks[:RERANK_STAGE1_LIMIT])
            # Append remaining chunks
            final_chunks.extend(stage1_chunks[RERANK_STAGE1_LIMIT:])
        else:
            final_chunks = stage1_chunks
        
        logger.info(f"Reranking complete: {len(final_chunks)} chunks")
        trace_metadata({
            "input_chunks": len(chunks),
            "output_chunks": len(final_chunks),
            "cross_encoder_used": self.cross_encoder is not None,
            "llm_reranking_used": ENABLE_LLM_RERANKING and self.llm_generator is not None,
            "top_rerank_score": final_chunks[0].get("rerank_score") if final_chunks else None,
        })
        return final_chunks
    
    def _cross_encoder_rerank(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Stage 1: Cross-encoder reranking."""
        try:
            # Prepare pairs
            pairs = [[query, chunk.get("content", "")] for chunk in chunks]
            
            # Predict scores
            scores = self.cross_encoder.predict(pairs)
            
            # Attach scores
            for i, chunk in enumerate(chunks):
                chunk["rerank_score"] = float(scores[i])
            
            # Sort by rerank score
            reranked = sorted(chunks, key=lambda x: x.get("rerank_score", 0), reverse=True)
            
            return reranked[:RERANK_STAGE1_LIMIT]
        
        except Exception as e:
            logger.error(f"Cross-encoder reranking failed: {e}")
            return chunks[:RERANK_STAGE1_LIMIT]
    
    def _llm_rerank(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Stage 2: LLM-based reranking (optional, for highest accuracy)."""
        try:
            # Prepare chunk list for LLM
            chunk_list = "\n".join([
                f"{i+1}. {chunk.get('content', '')[:500]}"
                for i, chunk in enumerate(chunks)
            ])
            
            prompt = f"""Rank these document chunks by relevance to the query.

QUERY: {query}

CHUNKS:
{chunk_list}

Return a JSON array of chunk numbers (1-based) in order of relevance:
[3, 1, 5, 2, 4, ...]

JSON:"""
            
            response = self.llm_generator.generate(
                system_prompt="You are a relevance ranking assistant. Return only valid JSON array.",
                user_prompt=prompt,
                temperature=0.1
            )
            
            # Parse ranking
            import json
            import re
            json_match = re.search(r'\[.*\]', response)
            if json_match:
                ranking = json.loads(json_match.group())
                # Reorder chunks based on LLM ranking
                reranked = [chunks[i-1] for i in ranking if 1 <= i <= len(chunks)]
                # Add any missing chunks
                reranked.extend([c for i, c in enumerate(chunks, 1) if i not in ranking])
                return reranked[:RERANK_STAGE2_LIMIT]
        
        except Exception as e:
            logger.warning(f"LLM reranking failed: {e}")
        
        return chunks[:RERANK_STAGE2_LIMIT]
