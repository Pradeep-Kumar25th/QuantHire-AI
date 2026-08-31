"""
Direct Retriever - Lightweight Similarity Search
================================================

Lightweight retrieval for JD Generation (no Q&A pipeline overhead).
Uses the same retrieval components as QueryRouter but without intent classification,
LLM generation, or response formatting.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict

from ..config.logging_config import setup_logger
from ..config.settings import MAX_CHUNKS_PER_RETRIEVER
from .metadata_filter import MetadataFilter
from .vector_retriever import VectorRetriever
from .keyword_retriever import KeywordRetriever
from ..fusion.rrf_fusion import ReciprocalRankFusion
from ..reranking.reranker import Reranker
from ..utils.tracing import traceable, trace_metadata

logger = setup_logger("direct_retriever")

class DirectRetriever:
    """
    Lightweight similarity search for JD Generation.
    
    Provides:
    - Hybrid retrieval (vector + keyword)
    - RRF fusion
    - Optional reranking
    - Document grouping
    - Raw chunk results (no LLM generation)
    """
    
    def __init__(self, use_reranking: bool = True):
        """
        Initialize DirectRetriever.
        
        Args:
            use_reranking: Whether to use reranking (default: True)
        """
        self.metadata_filter = MetadataFilter()
        self.vector_retriever = VectorRetriever()
        self.keyword_retriever = KeywordRetriever()
        self.rrf = ReciprocalRankFusion()
        self.reranker = Reranker() if use_reranking else None
        logger.info(f"DirectRetriever initialized (reranking: {use_reranking})")
    
    @traceable(run_type="retriever", name="DirectRetriever.find_similar")
    def find_similar_documents(
        self,
        query: str,
        document_type: str = "jd",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        group_by_document: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find similar documents using hybrid retrieval.
        
        Args:
            query: Search query
            document_type: "resume" or "jd"
            filters: Additional metadata filters
            limit: Maximum number of results
            group_by_document: If True, group chunks by document_id
        
        Returns:
            List of document chunks or grouped documents
        """
        logger.info(f"DirectRetriever: Searching for {document_type} - {query[:50]}")
        
        # Build filters
        search_filters = filters or {}
        search_filters["document_type"] = document_type
        
        # Hybrid retrieval
        vector_chunks = self.vector_retriever.retrieve(query, search_filters)
        keyword_chunks = self.keyword_retriever.retrieve(query, search_filters)
        
        # RRF fusion
        fused_chunks = self.rrf.fuse([vector_chunks, keyword_chunks])
        
        # Reranking (optional)
        if self.reranker and fused_chunks:
            final_chunks = self.reranker.rerank(query, fused_chunks)
        else:
            final_chunks = fused_chunks
        
        # Limit results
        final_chunks = final_chunks[:limit]
        
        trace_metadata({
            "document_type": document_type,
            "vector_chunks": len(vector_chunks),
            "keyword_chunks": len(keyword_chunks),
            "fused_chunks": len(fused_chunks),
            "final_chunks": len(final_chunks),
            "grouped": group_by_document,
        })
        
        # Group by document if requested
        if group_by_document:
            return self._group_by_document(final_chunks)
        
        return final_chunks
    
    def find_similar_jds(
        self,
        job_title: str,
        department: Optional[str] = None,
        limit: int = 10,
        group_by_document: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find similar JDs (convenience method).
        
        Args:
            job_title: Job title to search for
            department: Department filter (optional)
            limit: Maximum number of results
            group_by_document: Group chunks by document (default: True)
        
        Returns:
            List of similar JDs with grouped content
        """
        # Build query
        query = job_title
        if department:
            query = f"{job_title} {department}"
        
        # Build filters
        filters = {}
        if department:
            # Note: department filtering would need to be added to schema
            # For now, we'll filter in post-processing
            pass
        
        # Find similar documents
        results = self.find_similar_documents(
            query=query,
            document_type="jd",
            filters=filters,
            limit=limit * 3,  # Get more chunks for grouping
            group_by_document=group_by_document
        )
        
        # Filter by department if specified
        if department and group_by_document:
            results = [
                r for r in results
                if r.get("department", "").lower() == department.lower()
            ]
        
        # Limit final results
        return results[:limit]
    
    def _group_by_document(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Group chunks by document_id and combine content.
        
        Args:
            chunks: List of chunks
        
        Returns:
            List of grouped documents
        """
        doc_groups = defaultdict(lambda: {
            "chunks": [],
            "scores": [],
            "doc_id": None,
            "doc_type": None,
            "entity_name": None,
            "sections": set()
        })
        
        for chunk in chunks:
            doc_id = chunk.get("doc_id", "unknown")
            group = doc_groups[doc_id]
            
            if not group["doc_id"]:
                group["doc_id"] = doc_id
                group["doc_type"] = chunk.get("doc_type")
                group["entity_name"] = chunk.get("entity_name")
            
            group["chunks"].append(chunk)
            group["scores"].append(chunk.get("score", 0) or chunk.get("rerank_score", 0))
            if chunk.get("section"):
                group["sections"].add(chunk.get("section"))
        
        # Build grouped documents
        grouped_docs = []
        for doc_id, group in doc_groups.items():
            # Combine content from all chunks
            content_parts = []
            for chunk in sorted(group["chunks"], key=lambda c: c.get("score", 0) or c.get("rerank_score", 0), reverse=True):
                section = chunk.get("section", "")
                content = chunk.get("content", "")
                if content:
                    if section:
                        content_parts.append(f"[{section}]\n{content}")
                    else:
                        content_parts.append(content)
            
            # Calculate average score
            avg_score = sum(group["scores"]) / len(group["scores"]) if group["scores"] else 0
            
            grouped_docs.append({
                "job_id": doc_id,
                "title": group["entity_name"] or "Unknown",
                "department": "",  # Would need to extract from content or metadata
                "content": "\n\n".join(content_parts),
                "similarity": float(avg_score),
                "sections": list(group["sections"])
            })
        
        # Sort by similarity
        grouped_docs.sort(key=lambda x: x["similarity"], reverse=True)
        
        return grouped_docs
