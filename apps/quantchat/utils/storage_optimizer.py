"""
Full Content Storage Optimization
=================================

This module addresses the critical storage waste issue where full_content
was duplicated across ALL chunks of a document.

NEW STRATEGY:
- Store full_content ONLY in the first chunk (section="full_document")
- Other chunks store "" for full_content
- Retrieval reconstructs full content when needed

Storage Savings:
- Before: 10 chunks × 65KB = 650KB per resume
- After:  1 chunk × 65KB + 9 chunks × 0KB = 65KB per resume
- Savings: ~90% reduction in storage
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict

from ..config.logging_config import setup_logger

logger = setup_logger("storage_optimizer")


# Section type for full document storage
FULL_DOCUMENT_SECTION = "full_document"


def enrich_chunks_with_full_content(chunks: List[Dict]) -> List[Dict]:
    """
    Enrich chunks with full_content from sibling chunks.
    
    After storage optimization, only one chunk per document has full_content.
    This function finds that chunk and propagates full_content to all chunks
    from the same document.
    
    Args:
        chunks: List of retrieved chunks (some with empty full_content)
        
    Returns:
        Chunks with full_content propagated from document siblings
    """
    if not chunks:
        return chunks
    
    # Group chunks by document_id
    doc_chunks = defaultdict(list)
    for chunk in chunks:
        doc_id = chunk.get("doc_id") or chunk.get("document_id")
        if doc_id:
            doc_chunks[doc_id].append(chunk)
    
    # Find full_content for each document
    doc_full_content = {}
    for doc_id, doc_chunk_list in doc_chunks.items():
        for chunk in doc_chunk_list:
            full_content = chunk.get("full_content")
            if full_content and len(full_content) > 100:  # Non-trivial content
                doc_full_content[doc_id] = full_content
                break
    
    # Enrich chunks that are missing full_content
    enriched = []
    for chunk in chunks:
        new_chunk = chunk.copy()
        doc_id = chunk.get("doc_id") or chunk.get("document_id")
        
        current_full_content = chunk.get("full_content")
        if not current_full_content and doc_id in doc_full_content:
            new_chunk["full_content"] = doc_full_content[doc_id]
            logger.debug(f"Enriched chunk from doc {doc_id} with full_content")
        
        enriched.append(new_chunk)
    
    return enriched


def optimize_chunk_storage(chunks: List[Dict], full_content: str) -> List[Dict]:
    """
    Optimize chunk storage by deduplicating full_content.
    
    Strategy:
    1. First chunk with section="full_document" stores full_content
    2. All other chunks store empty string
    
    Args:
        chunks: List of chunk dictionaries
        full_content: The full document content
        
    Returns:
        Optimized chunks with full_content in only one place
    """
    if not chunks:
        return chunks
    
    optimized = []
    full_content_stored = False
    
    for chunk in chunks:
        new_chunk = chunk.copy()
        
        # Store full_content only in full_document section OR first chunk
        if chunk.get('section_type') == FULL_DOCUMENT_SECTION and not full_content_stored:
            new_chunk['full_content'] = full_content
            full_content_stored = True
        elif not full_content_stored and chunk == chunks[0]:
            # Fallback: store in first chunk if no full_document section
            new_chunk['full_content'] = full_content
            full_content_stored = True
        else:
            # Other chunks get empty string
            new_chunk['full_content'] = ""
        
        optimized.append(new_chunk)
    
    # If no chunks received full_content, add it to first
    if not full_content_stored and optimized:
        optimized[0]['full_content'] = full_content
    
    return optimized


def get_full_content_for_entity(entity_chunks: List[Dict]) -> Optional[str]:
    """
    Retrieve full_content from entity chunks.
    
    Looks for the chunk that has full_content stored.
    
    Args:
        entity_chunks: All chunks for an entity
        
    Returns:
        Full content string or None
    """
    for chunk in entity_chunks:
        full_content = chunk.get('full_content', '')
        if full_content and len(full_content) > 100:  # Non-trivial content
            return full_content
    
    return None


def calculate_storage_savings(num_chunks: int, avg_full_content_size: int = 30000) -> Dict:
    """
    Calculate storage savings from optimization.
    
    Args:
        num_chunks: Number of chunks per document
        avg_full_content_size: Average size of full_content in bytes
        
    Returns:
        Dictionary with savings statistics
    """
    old_storage = num_chunks * avg_full_content_size
    new_storage = avg_full_content_size  # Only one copy
    savings = old_storage - new_storage
    
    return {
        "old_storage_bytes": old_storage,
        "new_storage_bytes": new_storage,
        "savings_bytes": savings,
        "savings_percentage": (savings / old_storage * 100) if old_storage > 0 else 0,
        "num_chunks": num_chunks
    }


class ChunkStorageOptimizer:
    """
    Class-based optimizer for more complex scenarios.
    
    Features:
    - Compression support (future)
    - Reference-based storage (future)
    - Lazy loading of full content
    """
    
    def __init__(self, compression_enabled: bool = False):
        self.compression_enabled = compression_enabled
        self._stats = {
            "documents_optimized": 0,
            "total_chunks": 0,
            "bytes_saved": 0
        }
    
    def optimize(self, chunks: List[Dict], full_content: str) -> List[Dict]:
        """Optimize chunks and track statistics."""
        optimized = optimize_chunk_storage(chunks, full_content)
        
        # Update stats
        self._stats["documents_optimized"] += 1
        self._stats["total_chunks"] += len(chunks)
        
        # Estimate savings
        avg_size = len(full_content) if full_content else 0
        savings = calculate_storage_savings(len(chunks), avg_size)
        self._stats["bytes_saved"] += savings["savings_bytes"]
        
        return optimized
    
    @property
    def stats(self) -> Dict:
        """Get optimization statistics."""
        return self._stats.copy()
    
    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "documents_optimized": 0,
            "total_chunks": 0,
            "bytes_saved": 0
        }
