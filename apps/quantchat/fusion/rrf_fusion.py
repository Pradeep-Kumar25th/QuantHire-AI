"""
Reciprocal Rank Fusion (RRF)
=============================

Combines results from multiple retrievers using RRF algorithm.
With parent-document boosting for related chunk retrieval.
"""

from typing import List, Dict, Any
from collections import defaultdict
from ..config.logging_config import setup_logger
from ..config.settings import MAX_CHUNKS_AFTER_RRF, RRF_K
from ..utils.storage_optimizer import enrich_chunks_with_full_content
from ..utils.tracing import traceable, trace_metadata

logger = setup_logger("rrf_fusion")

# Parent document boost factor (chunks from same document as high-scoring chunks get boosted)
PARENT_DOC_BOOST = 0.15


class ReciprocalRankFusion:
    """
    Merges results from multiple retrievers using RRF.
    
    Formula: score = 1 / (k + rank)
    
    Includes parent-document boosting: when a chunk scores high,
    other chunks from the same document get a boost.
    """
    
    @traceable(run_type="chain", name="RRF_Fusion")
    def fuse(self, results_lists: List[List[Dict[str, Any]]], enable_parent_boost: bool = True) -> List[Dict[str, Any]]:
        """
        Fuse multiple result lists using RRF.
        
        Args:
            results_lists: List of result lists from different retrievers
            enable_parent_boost: Whether to boost chunks from same document
        
        Returns:
            Fused and deduplicated results
        """
        logger.info(f"Fusing {len(results_lists)} result sets using RRF")
        
        fused_scores = defaultdict(float)
        chunk_map = {}  # Map chunk_id -> chunk data
        doc_to_chunks = defaultdict(list)  # doc_id -> list of chunk_ids
        
        # Process each result list
        for result_list in results_lists:
            for rank, item in enumerate(result_list):
                # Create unique chunk ID
                chunk_id = self._get_chunk_id(item)
                doc_id = item.get("doc_id", "unknown")
                
                # Store chunk data
                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = item
                    doc_to_chunks[doc_id].append(chunk_id)
                
                # Add RRF score
                fused_scores[chunk_id] += 1.0 / (RRF_K + rank + 1)
        
        # Parent-document boosting: boost chunks from documents that have high-scoring chunks
        if enable_parent_boost:
            self._apply_parent_boost(fused_scores, doc_to_chunks, chunk_map)
        
        # Sort by fused score
        sorted_chunk_ids = sorted(fused_scores.keys(), 
                                 key=lambda k: fused_scores[k], 
                                 reverse=True)
        
        # Build final results
        final_results = []
        for chunk_id in sorted_chunk_ids:
            chunk = chunk_map[chunk_id]
            chunk["rrf_score"] = fused_scores[chunk_id]
            final_results.append(chunk)
        
        # Enrich chunks with full_content from sibling chunks
        # (Storage optimization: only one chunk per doc stores full_content)
        final_results = enrich_chunks_with_full_content(final_results)
        
        logger.info(f"RRF produced {len(final_results)} unique chunks")
        trace_metadata({
            "input_lists": len(results_lists),
            "input_total": sum(len(r) for r in results_lists),
            "unique_chunks": len(final_results),
            "unique_documents": len(doc_to_chunks),
            "parent_boost_enabled": enable_parent_boost,
            "output_limit": MAX_CHUNKS_AFTER_RRF,
        })
        return final_results[:MAX_CHUNKS_AFTER_RRF]
    
    def _apply_parent_boost(self, scores: Dict[str, float], doc_to_chunks: Dict[str, List[str]], chunk_map: Dict[str, Any]):
        """Apply parent-document boosting.
        
        When chunks from the same document appear in results, they get boosted.
        This helps retrieve related sections (e.g., if Skills chunk matches, Experience chunk from same resume gets boosted).
        """
        # Find top-scoring documents
        doc_max_scores = {}
        for doc_id, chunk_ids in doc_to_chunks.items():
            if chunk_ids:
                max_score = max(scores[cid] for cid in chunk_ids)
                doc_max_scores[doc_id] = max_score
        
        # Top 25% of documents by score get their chunks boosted
        if doc_max_scores:
            sorted_docs = sorted(doc_max_scores.keys(), key=lambda d: doc_max_scores[d], reverse=True)
            top_docs = set(sorted_docs[:max(1, len(sorted_docs) // 4)])
            
            # Boost chunks from top-scoring documents
            for doc_id in top_docs:
                for chunk_id in doc_to_chunks.get(doc_id, []):
                    # Only boost if not already a top chunk
                    if scores[chunk_id] < doc_max_scores[doc_id]:
                        scores[chunk_id] += PARENT_DOC_BOOST
                        logger.debug(f"Boosted chunk from doc {doc_id[:20]} by {PARENT_DOC_BOOST}")
    
    def _get_chunk_id(self, chunk: Dict[str, Any]) -> str:
        """Generate unique chunk ID for deduplication."""
        # Use doc_id + section + content hash
        doc_id = chunk.get("doc_id", "unknown")
        section = chunk.get("section", "unknown")
        content = chunk.get("content", "")[:100]  # First 100 chars
        
        return f"{doc_id}_{section}_{hash(content)}"
