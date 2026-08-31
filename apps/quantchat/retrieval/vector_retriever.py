"""
Vector Retriever
================

Semantic vector search using embeddings and Milvus HNSW index.
With caching for improved performance on repeated queries.
"""

from typing import List, Dict, Any

# Milvus + local embedding deps are absent on Azure (pgvector path used instead)
try:
    from pymilvus import connections, Collection, utility
    PYMILVUS_AVAILABLE = True
except ImportError:
    connections = Collection = utility = None
    PYMILVUS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from ..config.logging_config import setup_logger
from ..config.settings import (
    MILVUS_HOST, MILVUS_PORT, RESUME_COLLECTION, JD_COLLECTION,
    EMBEDDING_MODEL_NAME, EMBEDDING_DIM, MAX_CHUNKS_PER_RETRIEVER,
    SEARCH_PARAMS
)
from .metadata_filter import MetadataFilter
from ..utils.tracing import traceable, trace_metadata

# Import caching utilities
try:
    from ..utils.cache import get_cached_embedding, cache_embedding
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

logger = setup_logger("vector_retriever")

class VectorRetriever:
    """
    Performs semantic vector search in Milvus.
    """
    
    def __init__(self):
        self._milvus_connected = False
        self._encoder = None

    @property
    def encoder(self):
        if self._encoder is None:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise RuntimeError(
                    "sentence-transformers is not installed — local embeddings "
                    "unavailable (Azure deployments use the pgvector path)"
                )
            self._encoder = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return self._encoder
    
    def _ensure_milvus(self):
        """Lazy connect to Milvus."""
        if not PYMILVUS_AVAILABLE:
            logger.warning("pymilvus not installed — Milvus retrieval unavailable")
            return False
        if self._milvus_connected:
            return True
        
        try:
            connections.connect(
                alias="default",
                host=MILVUS_HOST,
                port=MILVUS_PORT
            )
            self._milvus_connected = True
            logger.info("Connected to Milvus")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            return False
    
    @traceable(run_type="retriever", name="VectorRetriever.retrieve")
    def retrieve(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform vector search with metadata filtering.
        """
        import os

        from .retrieval_backend import use_pgvector_retrieval

        if use_pgvector_retrieval():
            from .pgvector_retriever import PgVectorRetriever

            pg_filters = dict(filters or {})
            if pg_filters.get("document_types"):
                pg_filters["document_type"] = pg_filters["document_types"][0]
            try:
                rows = PgVectorRetriever().retrieve(query, pg_filters)
                return [
                    {
                        "content": row.get("chunk_text") or row.get("content", ""),
                        "score": float(row.get("score", 0.0)),
                        "doc_id": row.get("document_id"),
                        "doc_type": row.get("document_type"),
                        "entity_name": row.get("entity_name"),
                        "section": row.get("section_type") or row.get("section"),
                        "full_content": row.get("full_content", ""),
                        "source_retriever": "pgvector",
                    }
                    for row in rows
                    if (row.get("chunk_text") or row.get("content"))
                ]
            except Exception as exc:
                logger.error("PgVector retrieval failed: %s", exc, exc_info=True)
                return []

        logger.info(f"Vector retrieval: {query[:100]} with filters {filters}")
        
        if not self._ensure_milvus():
            logger.warning("Milvus not available - returning empty results")
            return []
        
        # Check embedding cache first
        query_emb = None
        if CACHE_AVAILABLE:
            query_emb = get_cached_embedding(query)
            if query_emb:
                logger.debug("Using cached embedding")
        
        # Encode query if not cached
        if query_emb is None:
            query_emb = self.encoder.encode(query, show_progress_bar=False).tolist()
            # Cache the embedding
            if CACHE_AVAILABLE:
                cache_embedding(query, query_emb)
        
        # Build filter expression
        metadata_filter = MetadataFilter()
        expr = metadata_filter.build_milvus_expression(filters)
        
        # Determine collections to search
        collections = self._get_collections(filters)
        
        all_results = []
        filter_failed = False
        
        for col_name in collections:
            if not utility.has_collection(col_name):
                logger.warning(f"Collection {col_name} not found")
                continue
            
            try:
                collection = Collection(col_name)
                collection.load()
                
                # Perform search
                results = collection.search(
                    data=[query_emb],
                    anns_field="embedding",
                    param=SEARCH_PARAMS,
                    limit=MAX_CHUNKS_PER_RETRIEVER,
                    expr=expr if expr else None,
                    output_fields=["document_id", "document_type", "entity_name", 
                                 "section_type", "chunk_text", "full_content", "created_at"]
                )
                
                # Format results
                for hits in results:
                    for hit in hits:
                        entity = hit.entity
                        chunk = {
                            "content": entity.get("chunk_text", ""),
                            "score": float(hit.score),
                            "doc_id": entity.get("document_id"),
                            "doc_type": entity.get("document_type"),
                            "entity_name": entity.get("entity_name"),
                            "section": entity.get("section_type"),
                            "full_content": entity.get("full_content"),
                            "source_retriever": "vector",
                            "created_at": entity.get("created_at"),
                        }
                        
                        if chunk["content"]:
                            all_results.append(chunk)
            
            except Exception as e:
                logger.error(f"Search failed in {col_name}: {e}")
                filter_failed = True
        
        # Fallback: If no results and we had entity filters, retry without entity filter
        if not all_results and (filter_failed or filters.get("entity_names")):
            logger.warning("Entity filter returned no results - falling back to broader search")
            # Remove entity filter and retry
            relaxed_filters = {k: v for k, v in filters.items() if k != "entity_names"}
            relaxed_expr = metadata_filter.build_milvus_expression(relaxed_filters)
            
            for col_name in collections:
                if not utility.has_collection(col_name):
                    continue
                    
                try:
                    collection = Collection(col_name)
                    collection.load()
                    
                    results = collection.search(
                        data=[query_emb],
                        anns_field="embedding",
                        param=SEARCH_PARAMS,
                        limit=MAX_CHUNKS_PER_RETRIEVER,
                        expr=relaxed_expr if relaxed_expr else None,
                        output_fields=["document_id", "document_type", "entity_name", 
                                     "section_type", "chunk_text", "full_content", "created_at"]
                    )
                    
                    for hits in results:
                        for hit in hits:
                            entity = hit.entity
                            chunk = {
                                "content": entity.get("chunk_text", ""),
                                "score": float(hit.score),
                                "doc_id": entity.get("document_id"),
                                "doc_type": entity.get("document_type"),
                                "entity_name": entity.get("entity_name"),
                                "section": entity.get("section_type"),
                                "full_content": entity.get("full_content"),
                                "source_retriever": "vector",
                                "created_at": entity.get("created_at"),
                            }
                            
                            if chunk["content"]:
                                all_results.append(chunk)
                except Exception as e:
                    logger.error(f"Fallback search failed in {col_name}: {e}")
        
        # Sort by score
        all_results.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"Vector retrieval found {len(all_results)} chunks")
        trace_metadata({
            "chunks_found": len(all_results),
            "collections_searched": collections,
            "embedding_cached": query_emb is not None and CACHE_AVAILABLE,
            "filter_expression": expr or "none",
        })
        return all_results[:MAX_CHUNKS_PER_RETRIEVER]
    
    def _get_collections(self, filters: Dict[str, Any]) -> List[str]:
        """Determine which collections to search."""
        doc_type = filters.get("document_type")
        
        if doc_type == "resume":
            return [RESUME_COLLECTION]
        elif doc_type == "jd":
            return [JD_COLLECTION]
        else:
            # Search both
            return [RESUME_COLLECTION, JD_COLLECTION]
