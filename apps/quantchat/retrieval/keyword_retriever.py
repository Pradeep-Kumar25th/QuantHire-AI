"""
Keyword Retriever
=================

Keyword/lexical search using BM25-style matching in Milvus.
"""

import re
from typing import List, Dict, Any, Optional

# pymilvus is absent on Azure (pgvector path used instead)
try:
    from pymilvus import connections, Collection, utility
    PYMILVUS_AVAILABLE = True
except ImportError:
    connections = Collection = utility = None
    PYMILVUS_AVAILABLE = False

from ..config.logging_config import setup_logger
from ..config.settings import (
    MILVUS_HOST, MILVUS_PORT, RESUME_COLLECTION, JD_COLLECTION,
    MAX_CHUNKS_PER_RETRIEVER
)
from .metadata_filter import MetadataFilter
from ..utils.tracing import traceable, trace_metadata

logger = setup_logger("keyword_retriever")

class KeywordRetriever:
    """
    Performs keyword/lexical search using Milvus LIKE operator.
    """
    
    def __init__(self):
        self._milvus_connected = False
    
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
            logger.info("KeywordRetriever: Connected to Milvus")
            return True
        except Exception as e:
            logger.error(f"KeywordRetriever: Failed to connect: {e}")
            return False
    
    @traceable(run_type="retriever", name="KeywordRetriever.retrieve")
    def retrieve(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform keyword search with metadata filtering.
        """
        import os

        logger.info(f"Keyword retrieval: {query[:100]}")

        from .retrieval_backend import use_pgvector_retrieval

        if use_pgvector_retrieval():
            return self._retrieve_pgvector(query, filters)

        if not self._ensure_milvus():
            return []
        
        # Extract keywords and entity names
        keywords = self._extract_keywords(query)
        potential_entities = self._extract_potential_entities(query)
        
        if not keywords and not potential_entities:
            return []
        
        # Build filter expression
        metadata_filter = MetadataFilter()
        base_expr = metadata_filter.build_milvus_expression(filters)
        
        # Strategy 1: Entity name matching (highest priority)
        entity_results = []
        if potential_entities:
            entity_results = self._search_by_entity(potential_entities, filters)
        
        # Strategy 2: Keyword containment search
        keyword_results = self._search_by_keywords(keywords, base_expr, filters)
        
        # Combine results with scoring
        all_results = []
        seen_ids = set()
        
        # Entity matches get higher score
        for chunk in entity_results:
            chunk_id = f"{chunk.get('doc_id')}_{chunk.get('section')}"
            if chunk_id not in seen_ids:
                chunk["score"] = 1.5  # Higher score for entity match
                chunk["match_type"] = "entity"
                all_results.append(chunk)
                seen_ids.add(chunk_id)
        
        # Keyword matches
        for chunk in keyword_results:
            chunk_id = f"{chunk.get('doc_id')}_{chunk.get('section')}"
            if chunk_id not in seen_ids:
                chunk["score"] = 1.0
                chunk["match_type"] = "keyword"
                all_results.append(chunk)
                seen_ids.add(chunk_id)
        
        logger.info(f"Keyword retrieval found {len(all_results)} chunks (entity: {len(entity_results)}, keyword: {len(keyword_results)})")
        trace_metadata({
            "entity_matches": len(entity_results),
            "keyword_matches": len(keyword_results),
            "total_chunks": len(all_results),
            "keywords_extracted": keywords,
            "entities_detected": potential_entities,
        })
        return all_results
    
    def _retrieve_pgvector(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        from .pg_async import run_coro_blocking

        keywords = self._extract_keywords(query)
        potential_entities = self._extract_potential_entities(query)
        document_type = filters.get("document_type")
        if filters.get("document_types"):
            document_type = filters["document_types"][0]
        entity_names = list(filters.get("entity_names") or [])
        entity_name = filters.get("entity_name") or filters.get("candidate_name")
        if entity_names and not entity_name and len(entity_names) == 1:
            entity_name = entity_names[0]
        if potential_entities and not entity_name and not entity_names:
            entity_name = potential_entities[0]

        return run_coro_blocking(
            self._retrieve_pgvector_async(
                keywords,
                document_type=document_type,
                entity_name=entity_name,
                entity_names=entity_names if len(entity_names) > 1 else None,
                document_id=filters.get("document_id"),
                section_type=filters.get("section_type"),
            )
        )

    async def _retrieve_pgvector_async(
        self,
        keywords: List[str],
        *,
        document_type: Optional[str],
        entity_name: Optional[str],
        entity_names: Optional[List[str]] = None,
        document_id: Optional[str] = None,
        section_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        import sys
        from pathlib import Path

        apps_root = Path(__file__).resolve().parents[2]
        api_root = apps_root / "api"
        for path in (str(api_root), str(apps_root)):
            if path not in sys.path:
                sys.path.insert(0, path)

        from app.services.pgvector_ingestion import PgVectorIngestionService

        from .pg_async import pg_session

        async with pg_session() as session:
            service = PgVectorIngestionService(session)
            rows = await service.search_chunks_by_keywords(
                keywords,
                document_type=document_type,
                entity_name=entity_name,
                entity_names=entity_names,
                document_id=document_id,
                section_type=section_type,
                top_k=MAX_CHUNKS_PER_RETRIEVER,
            )

        return [
            {
                "content": row.get("chunk_text") or "",
                "score": float(row.get("score", 1.0)),
                "doc_id": row.get("document_id"),
                "doc_type": row.get("document_type"),
                "entity_name": row.get("entity_name"),
                "section": row.get("section_type"),
                "full_content": row.get("full_content", ""),
                "match_type": "keyword",
                "source_retriever": "pgvector_keyword",
            }
            for row in rows
            if row.get("chunk_text")
        ]
    
    def _extract_potential_entities(self, query: str) -> List[str]:
        """Extract potential entity names from query."""
        entities = []
        
        # Look for capitalized words (potential names)
        # Pattern: Two or more capitalized words together
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        names = re.findall(name_pattern, query)
        entities.extend(names)
        
        # Single capitalized words (could be first names)
        single_pattern = r'\b([A-Z][a-z]{2,})\b'
        singles = re.findall(single_pattern, query)
        entities.extend(singles)
        
        return list(set(entities))[:3]  # Top 3 potential entities
    
    def _search_by_entity(self, entities: List[str], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search by entity name with fuzzy matching."""
        results = []
        collections = self._get_collections(filters)
        
        for col_name in collections:
            try:
                collection = Collection(col_name)
                collection.load()
                
                for entity in entities:
                    # Multiple matching strategies
                    entity_lower = entity.lower()
                    entity_upper = entity.upper()
                    entity_cap = entity.capitalize()
                    first_word = entity.split()[0] if entity else ""
                    
                    # Build expression for fuzzy entity matching
                    expr = f'entity_name like "{first_word}%" || entity_name like "{entity_cap}%" || entity_name like "{entity_upper}%"'
                    
                    try:
                        hits = collection.query(
                            expr=expr,
                            output_fields=["document_id", "document_type", "entity_name",
                                         "section_type", "chunk_text", "full_content", "created_at"],
                            limit=MAX_CHUNKS_PER_RETRIEVER // 2
                        )
                        
                        for hit in hits:
                            chunk = {
                                "content": hit.get("chunk_text", ""),
                                "score": 1.5,
                                "doc_id": hit.get("document_id"),
                                "doc_type": hit.get("document_type"),
                                "entity_name": hit.get("entity_name"),
                                "section": hit.get("section_type"),
                                "full_content": hit.get("full_content"),
                                "source_retriever": "keyword_entity",
                                "created_at": hit.get("created_at"),
                            }
                            if chunk["content"]:
                                results.append(chunk)
                    except Exception as e:
                        logger.debug(f"Entity search failed for {entity}: {e}")
            
            except Exception as e:
                logger.warning(f"Entity search failed in {col_name}: {e}")
        
        return results
    
    def _search_by_keywords(self, keywords: List[str], base_expr: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search by keywords in chunk text."""
        results = []
        
        if not keywords:
            return results
        
        collections = self._get_collections(filters)
        
        # Build keyword expression (prefix matching - Milvus limitation)
        # NOTE: Milvus only supports prefix matching (like "word%"), not containment
        keyword_exprs = [f'chunk_text like "{k}%"' for k in keywords[:2]]
        keyword_expr = " || ".join(keyword_exprs)  # OR for better recall
        
        # Combine expressions
        if base_expr:
            final_expr = f"({base_expr}) && ({keyword_expr})"
        else:
            final_expr = keyword_expr
        
        for col_name in collections:
            try:
                collection = Collection(col_name)
                collection.load()
                
                # Query for keyword matching
                hits = collection.query(
                    expr=final_expr,
                    output_fields=["document_id", "document_type", "entity_name",
                                 "section_type", "chunk_text", "full_content", "created_at"],
                    limit=MAX_CHUNKS_PER_RETRIEVER
                )
                
                # Format results
                for hit in hits:
                    chunk = {
                        "content": hit.get("chunk_text", ""),
                        "score": 1.0,
                        "doc_id": hit.get("document_id"),
                        "doc_type": hit.get("document_type"),
                        "entity_name": hit.get("entity_name"),
                        "section": hit.get("section_type"),
                        "full_content": hit.get("full_content"),
                        "source_retriever": "keyword",
                        "created_at": hit.get("created_at"),
                    }
                    if chunk["content"]:
                        results.append(chunk)
            
            except Exception as e:
                logger.warning(f"Keyword query failed in {col_name}: {e}")
        
        return results
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract significant keywords from query."""
        stopwords = {"this", "that", "the", "a", "an", "of", "for", "with", "in", "on", 
                    "to", "is", "are", "what", "how", "does", "have", "has", "show", "get",
                    "me", "tell", "give", "find", "list", "all", "any", "who", "whose",
                    "resume", "resumes", "cv", "profile", "candidate", "candidates"}
        
        words = re.findall(r"\w+", query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        return keywords[:5]  # Top 5 keywords
    
    def _get_collections(self, filters: Dict[str, Any]) -> List[str]:
        """Determine which collections to search."""
        doc_type = filters.get("document_type")
        
        if doc_type == "resume":
            return [RESUME_COLLECTION]
        elif doc_type == "jd":
            return [JD_COLLECTION]
        else:
            return [RESUME_COLLECTION, JD_COLLECTION]
