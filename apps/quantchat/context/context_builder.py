"""
Smart Context Builder
======================

Builds optimized context for LLM with smart selection, compression, and prioritization.
Includes semantic deduplication to avoid redundant content.
"""

from typing import List, Dict, Any, Optional, Set
from ..config.logging_config import setup_logger
from ..config.settings import (
    MAX_CONTEXT_CHUNKS, MAX_CONTEXT_TOKENS,
    ENABLE_CONTEXT_COMPRESSION, CONTEXT_COMPRESSION_THRESHOLD,
    ENABLE_SMART_SELECTION
)
from ..generation.llm_generator import LLMGenerator
from ..utils.tracing import traceable, trace_metadata

logger = setup_logger("context_builder")

# Minimum similarity ratio to consider chunks as duplicates
DEDUP_SIMILARITY_THRESHOLD = 0.7


def _compute_text_similarity(text1: str, text2: str) -> float:
    """
    Compute simple text similarity using word overlap (Jaccard-like).
    
    Fast approximation without requiring embeddings.
    """
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0


class ContextBuilder:
    """
    Builds optimized context for LLM generation.
    
    Features:
    - Smart chunk selection (relevance-based, not just top N)
    - Context compression for long chunks
    - Redundancy removal
    - Conversation history integration
    """
    
    def __init__(self):
        try:
            self.llm_generator = LLMGenerator() if ENABLE_CONTEXT_COMPRESSION else None
        except Exception as e:
            logger.warning(f"LLM generator not available for context compression: {e}")
            self.llm_generator = None
    
    @traceable(run_type="chain", name="ContextBuilder.build_context")
    def build_context(
        self,
        chunks: List[Dict[str, Any]],
        query: str,
        conversation_history: Optional[str] = None,
        tracked_entities: Optional[List[str]] = None,
        full_document_mode: bool = False
    ) -> str:
        """
        Build optimized context from chunks.
        
        Args:
            chunks: Retrieved chunks
            query: User query
            conversation_history: Previous conversation turns
            tracked_entities: Previously mentioned entities
            full_document_mode: If True, disable compression and include ALL content
        
        Returns:
            Formatted context string
        """
        logger.info(f"Building context from {len(chunks)} chunks (full_document_mode={full_document_mode})")
        
        context_parts = []
        token_estimate = 0
        
        # For full document mode, skip conversation history to maximize document space
        if not full_document_mode:
            # 1. Add conversation history
            if conversation_history:
                history_section = f"=== CONVERSATION HISTORY ===\n{conversation_history}\n"
                history_tokens = len(history_section.split())
                if history_tokens < MAX_CONTEXT_TOKENS * 0.25:  # 25% budget for history
                    context_parts.append(history_section)
                    token_estimate += history_tokens
        
        # 2. Add tracked entities
        if tracked_entities:
            entities_str = ", ".join(tracked_entities[:10])
            entities_section = f"=== PREVIOUSLY MENTIONED ENTITIES ===\n{entities_str}\n"
            entities_tokens = len(entities_section.split())
            if token_estimate + entities_tokens < MAX_CONTEXT_TOKENS * 0.3:
                context_parts.append(entities_section)
                token_estimate += entities_tokens
        
        # 3. Smart chunk selection with deduplication
        if ENABLE_SMART_SELECTION:
            selected_chunks = self._select_relevant_chunks(query, chunks)
        else:
            selected_chunks = chunks[:MAX_CONTEXT_CHUNKS]
        
        # 3.5. Semantic deduplication - remove near-duplicate chunks
        deduplicated_chunks = self._deduplicate_chunks(selected_chunks)
        if len(deduplicated_chunks) < len(selected_chunks):
            logger.info(f"Deduplication removed {len(selected_chunks) - len(deduplicated_chunks)} redundant chunks")
        
        # 4. Group chunks by document
        doc_groups = {}
        for chunk in deduplicated_chunks:
            doc_id = chunk.get("doc_id", "unknown")
            if doc_id not in doc_groups:
                doc_groups[doc_id] = []
            doc_groups[doc_id].append(chunk)
        
        # 5. Build document sections
        context_parts.append("=== RELEVANT DOCUMENTS FROM DATABASE ===")
        
        # Sort documents by max relevance score
        sorted_docs = sorted(
            doc_groups.items(),
            key=lambda item: max(c.get("rerank_score", c.get("score", 0)) for c in item[1]),
            reverse=True
        )
        
        for doc_id, doc_chunks in sorted_docs:
            if token_estimate >= MAX_CONTEXT_TOKENS:
                break
            
            # Get document metadata
            first_chunk = doc_chunks[0]
            entity = first_chunk.get("entity_name", "Unknown")
            doc_type = first_chunk.get("doc_type", "Document")
            
            doc_header = f"\n--- DOCUMENT: {doc_type.upper()} | ID: {entity} ---\n"
            context_parts.append(doc_header)
            token_estimate += len(doc_header.split())
            
            # Add chunks for this document
            for chunk in doc_chunks:
                if token_estimate >= MAX_CONTEXT_TOKENS:
                    break
                
                section = chunk.get("section", "General")
                content = chunk.get("content", "").strip()
                
                # Compress if needed (skip compression in full_document_mode to preserve ALL data)
                if ENABLE_CONTEXT_COMPRESSION and len(content) > CONTEXT_COMPRESSION_THRESHOLD and not full_document_mode:
                    content = self._compress_chunk(query, content)
                
                chunk_str = f"[SECTION: {section}]\n{content}\n"
                chunk_tokens = len(chunk_str.split())
                
                if token_estimate + chunk_tokens <= MAX_CONTEXT_TOKENS:
                    context_parts.append(chunk_str)
                    token_estimate += chunk_tokens
        
        final_context = "\n\n".join(context_parts)
        logger.info(f"Context built: {token_estimate} tokens, {len(selected_chunks)} chunks")
        trace_metadata({
            "input_chunks": len(chunks),
            "selected_chunks": len(selected_chunks),
            "deduplicated_chunks": len(deduplicated_chunks),
            "document_groups": len(doc_groups),
            "estimated_tokens": token_estimate,
            "max_tokens_budget": MAX_CONTEXT_TOKENS,
        })
        return final_context
    
    def _select_relevant_chunks(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Select most relevant chunks (not just top N)."""
        # Use rerank_score if available, otherwise use original score
        scored_chunks = []
        for chunk in chunks:
            score = chunk.get("rerank_score") or chunk.get("rrf_score") or chunk.get("score", 0)
            scored_chunks.append((score, chunk))
        
        # Sort by score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Take top chunks, but also include chunks from different documents
        selected = []
        seen_docs = set()
        
        # First pass: Top chunk from each document
        for score, chunk in scored_chunks:
            doc_id = chunk.get("doc_id", "unknown")
            if doc_id not in seen_docs:
                selected.append(chunk)
                seen_docs.add(doc_id)
        
        # Second pass: Fill remaining slots with highest scores
        for score, chunk in scored_chunks:
            if len(selected) >= MAX_CONTEXT_CHUNKS:
                break
            if chunk not in selected:
                selected.append(chunk)
        
        return selected[:MAX_CONTEXT_CHUNKS]
    
    def _deduplicate_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove semantically duplicate chunks to avoid wasting context tokens.
        
        Uses word overlap similarity (fast, no embeddings needed).
        Keeps the chunk with higher score when duplicates found.
        
        Args:
            chunks: List of chunks to deduplicate
            
        Returns:
            Deduplicated chunk list
        """
        if len(chunks) <= 1:
            return chunks
        
        deduplicated = []
        seen_content_hashes: Set[int] = set()
        
        for chunk in chunks:
            content = chunk.get("content", "")
            
            # Quick exact-match check using hash
            content_hash = hash(content.lower().strip())
            if content_hash in seen_content_hashes:
                continue
            
            # Semantic similarity check against already-selected chunks
            is_duplicate = False
            for existing in deduplicated:
                existing_content = existing.get("content", "")
                similarity = _compute_text_similarity(content, existing_content)
                
                if similarity >= DEDUP_SIMILARITY_THRESHOLD:
                    is_duplicate = True
                    logger.debug(f"Duplicate chunk detected (similarity={similarity:.2f})")
                    break
            
            if not is_duplicate:
                deduplicated.append(chunk)
                seen_content_hashes.add(content_hash)
        
        return deduplicated
    
    def _compress_chunk(self, query: str, content: str) -> str:
        """Compress long chunk while preserving relevance."""
        if not self.llm_generator:
            # Simple truncation
            return content[:CONTEXT_COMPRESSION_THRESHOLD] + "..."
        
        try:
            prompt = f"""Summarize this document chunk, focusing on information relevant to the query.

QUERY: {query}

CHUNK:
{content[:5000]}

Provide a concise summary (max 1000 chars) that preserves all information relevant to the query.

Summary:"""
            
            summary = self.llm_generator.generate(
                system_prompt="You are a document summarizer. Provide concise summaries.",
                user_prompt=prompt,
                temperature=0.2
            )
            
            return summary[:CONTEXT_COMPRESSION_THRESHOLD]
        
        except Exception as e:
            logger.warning(f"Chunk compression failed: {e}")
            return content[:CONTEXT_COMPRESSION_THRESHOLD] + "..."
