"""
Full Document Retriever
========================

Retrieves complete documents (full resume/JD) directly from Milvus.
"""

from typing import Dict, Any, Optional

# pymilvus is absent on Azure (pgvector path used instead)
try:
    from pymilvus import connections, Collection, utility
    PYMILVUS_AVAILABLE = True
except ImportError:
    connections = Collection = utility = None
    PYMILVUS_AVAILABLE = False

from ..config.logging_config import setup_logger
from ..config.settings import MILVUS_HOST, MILVUS_PORT, RESUME_COLLECTION, JD_COLLECTION

logger = setup_logger("full_doc_retriever")

class FullDocumentRetriever:
    """
    Retrieves full documents directly from Milvus full_content field.
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
            logger.info("FullDocRetriever: Connected to Milvus")
            return True
        except Exception as e:
            logger.error(f"FullDocRetriever: Failed to connect: {e}")
            return False
    
    def retrieve_full_document(self, document_type: str, entity_name: Optional[str] = None, 
                               document_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve full document by entity name or document ID.
        
        Args:
            document_type: "resume" or "jd"
            entity_name: Candidate name or job title
            document_id: Document ID (alternative to entity_name)
        
        Returns:
            Document with full_content, or None if not found
        """
        logger.info(f"Retrieving full {document_type} - entity: {entity_name}, id: {document_id}")

        import os

        from .retrieval_backend import use_pgvector_retrieval

        if use_pgvector_retrieval():
            return self._retrieve_pgvector_full(document_type, entity_name, document_id)
        
        if not self._ensure_milvus():
            return None
        
        # Determine collection
        collection_name = RESUME_COLLECTION if document_type == "resume" else JD_COLLECTION
        
        if not utility.has_collection(collection_name):
            logger.warning(f"Collection {collection_name} not found")
            return None
        
        try:
            collection = Collection(collection_name)
            collection.load()
            
            # Build filter expression
            expr_parts = [f'document_type == "{document_type}"']
            
            if document_id:
                expr_parts.append(f'document_id == "{document_id}"')
            elif entity_name:
                # IMPORTANT: Milvus like operator only supports PREFIX matching (ab%), not contains (%ab%)
                # For entity name search, we need to retrieve ALL documents of the type
                # and filter by name match in Python. This is efficient because typically
                # there are only dozens of JDs/resumes in the database.
                # Store entity_name for post-query filtering
                self._target_entity_name = entity_name
                # Don't add entity_name filter to expr - we'll filter in Python
            else:
                logger.warning("No entity_name or document_id provided")
                return None
            
            expr = " && ".join(expr_parts)
            
            # Query for chunks - get ALL documents of this type for Python-based name matching
            # This is efficient because there are typically only dozens of JDs/resumes
            results = collection.query(
                expr=expr,
                output_fields=["document_id", "document_type", "entity_name", 
                             "full_content", "section_type", "chunk_text"],
                limit=1000  # Get all documents for accurate name matching
            )
            
            if results:
                # If entity_name was used for search, filter for best match
                if entity_name and hasattr(self, '_target_entity_name'):
                    target_name = self._target_entity_name.lower().strip()
                    # Normalize: replace / and - with spaces for word matching
                    target_normalized = target_name.replace('/', ' ').replace('-', ' ')
                    target_words = set(w for w in target_normalized.split() if w)
                    
                    # Score each result by how well it matches the target name
                    def name_match_score(hit):
                        stored_name = hit.get("entity_name", "").lower().strip()
                        stored_normalized = stored_name.replace('/', ' ').replace('-', ' ')
                        stored_words = set(w for w in stored_normalized.split() if w)
                        
                        # Exact match (highest priority)
                        if stored_name == target_name or stored_normalized == target_normalized:
                            return 100
                        
                        # Count matching words
                        matching_words = len(target_words.intersection(stored_words))
                        
                        # If ALL query words are present in stored name, high score
                        # This handles "UI/UX Designer" matching "Junior UI/UX Designer"
                        if target_words.issubset(stored_words):
                            return 90 + matching_words
                        
                        # Partial match - percentage of query words found
                        if matching_words > 0:
                            match_ratio = matching_words / len(target_words) if target_words else 0
                            return 50 + (match_ratio * 30)
                        
                        return 0
                    
                    # Sort by match score and get best match
                    results.sort(key=name_match_score, reverse=True)
                    best_score = name_match_score(results[0])
                    
                    # Only accept matches with score > 0 (at least some word match)
                    if best_score > 0:
                        hit = results[0]
                        logger.info(f"Best match: {hit.get('entity_name')} (score: {best_score})")
                    else:
                        hit = results[0]  # Fallback to first result
                else:
                    hit = results[0]
                full_content = hit.get("full_content", "")
                
                # If full_content not available, try to reconstruct from chunks
                if not full_content:
                    logger.info("full_content not available, reconstructing from chunks...")
                    full_content = self._reconstruct_from_chunks(collection, expr)
                
                return {
                    "document_id": hit.get("document_id"),
                    "document_type": hit.get("document_type"),
                    "entity_name": hit.get("entity_name"),
                    "full_content": full_content,
                    "section_type": "Complete Document"
                }
            
            logger.warning(f"Full document not found: {entity_name or document_id}")
            return None
        
        except Exception as e:
            logger.error(f"Failed to retrieve full document: {e}")
            return None

    def _retrieve_pgvector_full(
        self,
        document_type: str,
        entity_name: Optional[str],
        document_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        from .pg_async import run_coro_blocking

        return run_coro_blocking(
            self._retrieve_pgvector_full_async(document_type, entity_name, document_id)
        )

    async def _retrieve_pgvector_full_async(
        self,
        document_type: str,
        entity_name: Optional[str],
        document_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
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
            return await service.fetch_full_document(
                document_type=document_type,
                entity_name=entity_name,
                document_id=document_id,
            )
    
    def _reconstruct_from_chunks(self, collection: Collection, expr: str) -> str:
        """Reconstruct full document from chunks if full_content not available."""
        try:
            # Get all chunks for this document
            results = collection.query(
                expr=expr,
                output_fields=["chunk_text", "section_type"],
                limit=1000  # Get all chunks
            )
            
            if not results:
                return ""
            
            # Sort by section order (if available)
            section_order = ["Personal Info", "Skills", "Experience", "Education", "Projects"]
            
            def sort_key(hit):
                section = hit.get("section_type", "")
                try:
                    return section_order.index(section)
                except ValueError:
                    return 999
            
            results.sort(key=sort_key)
            
            # Concatenate chunks
            full_text = "\n\n".join([hit.get("chunk_text", "") for hit in results])
            return full_text
        
        except Exception as e:
            logger.error(f"Failed to reconstruct from chunks: {e}")
            return ""
