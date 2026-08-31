"""
Document Ingestion Service
==========================

Handles WRITE operations to Milvus (document storage).
"""

import uuid
import time
import logging
from typing import Dict, Any, List
from pymilvus import connections, Collection, CollectionSchema, utility
from sentence_transformers import SentenceTransformer

from ..config.logging_config import setup_logger
from ..config.settings import (
    MILVUS_HOST, MILVUS_PORT, RESUME_COLLECTION, JD_COLLECTION,
    EMBEDDING_MODEL_NAME, EMBEDDING_DIM, MAX_FULL_CONTENT_LENGTH
)
from .chunking import ResumeChunker, JDChunker
from ..utils.milvus_connection import get_connection_manager, with_milvus_connection, with_retry
from ..utils.storage_optimizer import optimize_chunk_storage, ChunkStorageOptimizer

import re

logger = setup_logger("document_ingestion")

def _clean_pdf_artifacts(text: str) -> str:
    """Comprehensive cleaning of PDF extraction artifacts.
    
    Handles ALL known PDF artifact patterns:
    - "-Aditya- -Rao-" -> "Aditya Rao" (hyphens around words)
    - "-6- -years -o-f" -> "6 years of" (hyphens around chars/words)
    - "-U-X -Designer" -> "UX Designer" (partial hyphens)
    - "word- word" -> "word word" (trailing hyphens)
    - "-word word" -> "word word" (leading hyphens at word start)
    
    Preserves legitimate hyphens in words like "Mary-Jane", "year-over-year"
    """
    if not text:
        return ""
    
    cleaned = text
    
    # PASS 1: Remove hyphens wrapped completely around words/numbers: "-Word-" -> "Word"
    cleaned = re.sub(r'(?<![A-Za-z0-9])-([A-Za-z0-9]+)-(?![A-Za-z0-9])', r'\1', cleaned)
    
    # PASS 2: Remove leading hyphens at word boundaries: " -Word" -> " Word"
    cleaned = re.sub(r'(?<=\s)-([A-Za-z0-9])', r'\1', cleaned)
    cleaned = re.sub(r'^-([A-Za-z0-9])', r'\1', cleaned, flags=re.MULTILINE)
    
    # PASS 3: Remove trailing hyphens at word boundaries: "Word- " -> "Word "
    cleaned = re.sub(r'([A-Za-z0-9])-(?=\s|$|[,.\.)])', r'\1', cleaned)
    
    # PASS 4: Handle "-o-f" pattern (single chars with leading/trailing hyphens)
    cleaned = re.sub(r'(?<=\s)-([a-zA-Z0-9])-(?=\s)', r'\1', cleaned)
    
    # PASS 5: Clean up isolated hyphens
    cleaned = re.sub(r'\s+-\s+', ' ', cleaned)
    
    # PASS 6: Handle dashes between SINGLE characters only: "-U-X" -> "UX"
    # Preserves legitimate hyphenated words like "Mary-Jane"
    def clean_dash_chars(match):
        word = match.group(0).strip('-')
        parts = word.split('-')
        if all(len(p.strip()) == 1 for p in parts if p.strip()):
            return ''.join(p for p in parts if p.strip())
        return match.group(0)
    cleaned = re.sub(r'-?([A-Za-z0-9]+)(?:-([A-Za-z0-9]+))+(-)?', clean_dash_chars, cleaned)
    
    # PASS 7: Remove trailing commas with hyphens: "word,- " -> "word, "
    cleaned = re.sub(r',-\s+', ', ', cleaned)
    
    # PASS 8: Clean remaining hyphens around punctuation
    cleaned = re.sub(r'-+([,.\)\(])', r'\1', cleaned)
    cleaned = re.sub(r'([,.\)\(])-+', r'\1', cleaned)
    
    # PASS 9: Clean patterns like "(2021-Present)" from "(2021---Present-)"
    cleaned = re.sub(r'\(-*(\d+)-*-+(\w+)-*\)', r'(\1-\2)', cleaned)
    
    # PASS 10: Clean multiple spaces
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
    # PASS 11: Clean multiple hyphens: "---" -> "-"
    cleaned = re.sub(r'-{2,}', '-', cleaned)
    
    return cleaned.strip()

# Alias for backward compatibility
_clean_full_content = _clean_pdf_artifacts

# Import schema
try:
    import sys
    from pathlib import Path
    # Add project root to path
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    from milvus_schema import (
        UNIFIED_COLLECTION_SCHEMA, INDEX_PARAMS, SEARCH_PARAMS,
        MAX_FULL_CONTENT_LENGTH as SCHEMA_MAX_LENGTH
    )
    SCHEMA_AVAILABLE = True
except ImportError as e:
    SCHEMA_AVAILABLE = False
    SCHEMA_MAX_LENGTH = MAX_FULL_CONTENT_LENGTH
    logger.warning(f"milvus_schema not available - auto-creation disabled: {e}")

class DocumentIngestion:
    """
    Handles document ingestion into Milvus.
    WRITE-ONLY operations.
    
    Features:
    - Robust connection handling with automatic reconnection
    - Storage-optimized chunk insertion (full_content deduplication)
    - Batch insert with error handling
    """
    
    def __init__(self):
        self._connected = False
        self.encoder = None
        self.resume_chunker = ResumeChunker()
        self.jd_chunker = JDChunker()
        self._connection_manager = get_connection_manager()
        self._storage_optimizer = ChunkStorageOptimizer()
    
    def _format_jd_section(self, section_name: str, data: Any) -> str:
        """
        Format JD section data into human-readable text.
        Properly handles nested dicts, lists, and special sections.
        
        Args:
            section_name: Name of the section for context-aware formatting
            data: Section data (can be str, list, dict, or nested)
            
        Returns:
            Formatted string representation
        """
        if data is None:
            return ""
        
        if isinstance(data, str):
            return data
        
        if isinstance(data, list):
            # Format list items with bullets
            formatted_items = []
            for item in data:
                if isinstance(item, dict):
                    # Nested dict in list - format each dict
                    formatted_items.append(self._format_jd_section("", item))
                else:
                    formatted_items.append(f"• {item}")
            return "\n".join(formatted_items)
        
        if isinstance(data, dict):
            # Handle special sections with better formatting
            if section_name == "Location":
                parts = []
                if data.get('city'):
                    parts.append(data['city'])
                if data.get('country'):
                    parts.append(data['country'])
                location_str = ", ".join(parts) if parts else ""
                if data.get('work_model'):
                    location_str += f" ({data['work_model']})"
                if data.get('travel_required'):
                    travel_pct = data.get('travel_percentage', 0)
                    location_str += f" | Travel: {travel_pct}%"
                return location_str if location_str else str(data)
            
            elif section_name == "Required Qualifications":
                parts = []
                if data.get('education'):
                    parts.append(f"**Education:** {data['education']}")
                if data.get('experience'):
                    parts.append(f"**Experience:** {data['experience']}")
                if data.get('technical_skills'):
                    skills = data['technical_skills']
                    if isinstance(skills, list):
                        skills_str = "\n".join([f"  • {s}" for s in skills])
                        parts.append(f"**Technical Skills:**\n{skills_str}")
                    else:
                        parts.append(f"**Technical Skills:** {skills}")
                return "\n".join(parts) if parts else str(data)
            
            elif section_name == "Work Environment":
                parts = []
                if data.get('reports_to'):
                    parts.append(f"**Reports To:** {data['reports_to']}")
                if data.get('team_size'):
                    parts.append(f"**Team Size:** {data['team_size']}")
                if data.get('collaboration_mode'):
                    parts.append(f"**Collaboration Mode:** {data['collaboration_mode']}")
                if data.get('collaborates_with'):
                    collabs = data['collaborates_with']
                    if isinstance(collabs, list):
                        parts.append(f"**Collaborates With:** {', '.join(collabs)}")
                    else:
                        parts.append(f"**Collaborates With:** {collabs}")
                return "\n".join(parts) if parts else str(data)
            
            elif section_name == "Application Instructions":
                parts = []
                if data.get('apply_url'):
                    parts.append(f"**Apply URL:** {data['apply_url']}")
                if data.get('email'):
                    parts.append(f"**Email:** {data['email']}")
                if data.get('required_materials'):
                    materials = data['required_materials']
                    if isinstance(materials, list):
                        materials_str = "\n".join([f"  • {m}" for m in materials])
                        parts.append(f"**Required Materials:**\n{materials_str}")
                    else:
                        parts.append(f"**Required Materials:** {materials}")
                return "\n".join(parts) if parts else str(data)
            
            else:
                # Generic dict formatting
                parts = []
                for key, value in data.items():
                    # Format key nicely (snake_case to Title Case)
                    nice_key = key.replace('_', ' ').title()
                    if isinstance(value, list):
                        value_str = ", ".join(str(v) for v in value)
                        parts.append(f"**{nice_key}:** {value_str}")
                    elif isinstance(value, dict):
                        parts.append(f"**{nice_key}:** {self._format_jd_section('', value)}")
                    else:
                        parts.append(f"**{nice_key}:** {value}")
                return "\n".join(parts)
        
        # Fallback for other types
        return str(data)
    
    def connect(self):
        """Connect to Milvus with robust connection handling."""
        try:
            # Use connection manager for robust handling
            if self._connection_manager.connect():
                self._connected = True
                logger.info(f"✅ Connected to Milvus via connection manager")
            else:
                raise ConnectionError("Failed to connect to Milvus")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Milvus: {e}")
            raise
    
    def _ensure_connection(self) -> bool:
        """Ensure connection is alive, reconnect if needed."""
        try:
            if self._connection_manager.ensure_connected():
                self._connected = True
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Failed to ensure Milvus connection: {e}")
            return False
    
    def _safe_flush(self, collection, timeout: int = 60, retries: int = 3):
        """Flush with automatic gRPC reconnection on DEADLINE_EXCEEDED.
        
        On final failure, logs a warning instead of raising since data
        is already inserted and queryable without an explicit flush.
        """
        for attempt in range(retries):
            try:
                collection.flush(timeout=timeout)
                return
            except Exception as e:
                if 'DEADLINE_EXCEEDED' in str(e):
                    if attempt < retries - 1:
                        logger.warning(f"⚠️ Flush timeout (attempt {attempt+1}/{retries}) - reconnecting gRPC channel...")
                        try:
                            connections.disconnect("default")
                            connections.connect(
                                alias="default",
                                host=MILVUS_HOST,
                                port=MILVUS_PORT,
                            )
                            logger.info("✅ gRPC channel refreshed, retrying flush...")
                            collection = Collection(collection.name)
                        except Exception as reconn_err:
                            logger.error(f"❌ Reconnection failed: {reconn_err}")
                            raise e
                    else:
                        logger.warning(f"⚠️ Flush timed out after {retries} attempts (data is still inserted and queryable)")
                        return
                else:
                    raise
    
    def load_embedding_model(self):
        """Load embedding model."""
        try:
            self.encoder = SentenceTransformer(EMBEDDING_MODEL_NAME)
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            raise
    
    def is_connected(self) -> bool:
        """Check if connected to Milvus."""
        return self._connected
    
    def _ensure_collection_exists(self, collection_name: str, schema: CollectionSchema) -> bool:
        """Ensure collection exists, create if needed."""
        if utility.has_collection(collection_name):
            logger.debug(f"Collection {collection_name} already exists")
            return True
        
        if not SCHEMA_AVAILABLE:
            logger.error("Schema not available - cannot auto-create collection")
            return False
        
        try:
            logger.info(f"Creating collection: {collection_name}")
            collection = Collection(name=collection_name, schema=schema)
            
            # Create HNSW index for vector search
            logger.info("Creating HNSW index for embeddings...")
            collection.create_index(
                field_name="embedding",
                index_params=INDEX_PARAMS
            )
            
            # Create scalar indexes for fast metadata filtering
            # NOTE: Using Trie index type (INVERTED not supported for VARCHAR in this Milvus version)
            logger.info("Creating scalar indexes for fast metadata filtering...")
            try:
                # Index on document_type for fast filtering
                collection.create_index(
                    field_name="document_type",
                    index_params={"index_type": "Trie"}
                )
                # Index on entity_name for fast entity filtering
                collection.create_index(
                    field_name="entity_name",
                    index_params={"index_type": "Trie"}
                )
                # Index on section_type for fast section filtering
                collection.create_index(
                    field_name="section_type",
                    index_params={"index_type": "Trie"}
                )
                logger.info("✅ Scalar indexes (Trie) created for fast filtering")
            except Exception as e:
                logger.warning(f"Scalar index creation failed (may already exist): {e}")
            
            logger.info(f"✅ Collection {collection_name} created with all indexes")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False
    
    def _delete_existing_resume(self, candidate_name: str, email: str = None) -> int:
        """
        Delete existing resume entries for a candidate to prevent duplicates.
        
        Args:
            candidate_name: Name of the candidate
            email: Optional email for more precise matching
        
        Returns:
            Number of entries deleted
        """
        try:
            if not utility.has_collection(RESUME_COLLECTION):
                return 0
            
            collection = Collection(RESUME_COLLECTION)
            collection.load()
            
            # Normalize name for matching (handle case differences)
            name_lower = candidate_name.lower().strip()
            name_upper = candidate_name.upper().strip()
            name_title = candidate_name.title().strip()
            
            # Build expression to find existing entries
            # Match any case variation of the name
            expr = f'entity_name == "{candidate_name}" or entity_name == "{name_lower}" or entity_name == "{name_upper}" or entity_name == "{name_title}"'
            
            # Query to get IDs of existing entries
            existing = collection.query(
                expr=expr,
                output_fields=['document_id'],
                limit=100
            )
            
            if existing:
                # Get unique document IDs
                doc_ids = list(set(e['document_id'] for e in existing))
                logger.info(f"🗑️ Found {len(existing)} existing entries for '{candidate_name}' ({len(doc_ids)} unique resumes)")
                
                # Delete all existing entries for this candidate
                for doc_id in doc_ids:
                    delete_expr = f'document_id == "{doc_id}"'
                    collection.delete(delete_expr)
                    logger.info(f"   Deleted entries for document_id: {doc_id[:8]}...")
                
                collection.flush(timeout=60)
                
                # CRITICAL: Refresh collection immediately after delete
                # This ensures the deleted data is no longer queryable
                try:
                    collection.release()
                    collection.load()
                    logger.info(f"   ✅ Deleted {len(existing)} old resume entries - collection refreshed")
                except Exception as refresh_err:
                    logger.warning(f"   ⚠️ Delete flush succeeded, refresh warning: {refresh_err}")
                
                return len(existing)
            
            return 0
            
        except Exception as e:
            logger.warning(f"⚠️ Error checking for duplicates: {e}")
            return 0
    
    def add_resume(self, parsed_data: Dict[str, Any]) -> str:
        """
        Add resume to Milvus (with deduplication).
        
        Args:
            parsed_data: Parsed resume data
        
        Returns:
            Resume ID
        """
        if not self._connected:
            raise Exception("Not connected to Milvus")
        
        if not self.encoder:
            raise Exception("Embedding model not loaded")
        
        resume_id = parsed_data.get('id', str(uuid.uuid4()))
        candidate_name = parsed_data.get('personal_info', {}).get('name', 'Unknown')
        candidate_email = parsed_data.get('personal_info', {}).get('email', '')
        
        # DEDUPLICATION: Remove existing entries for this candidate before adding new ones
        deleted_count = self._delete_existing_resume(candidate_name, candidate_email)
        if deleted_count > 0:
            logger.info(f"✅ Deduplication: Removed {deleted_count} old entries for '{candidate_name}'")
        
        logger.info(f"💾 Adding resume to Milvus: {resume_id}")
        
        # Chunk resume
        chunks = self.resume_chunker.chunk_resume(parsed_data)
        logger.info(f"Created {len(chunks)} chunks")
        
        if not chunks:
            raise Exception("No chunks created from resume")
        
        # Generate embeddings
        chunk_texts = [chunk['content'] for chunk in chunks]
        embeddings = self.encoder.encode(chunk_texts, show_progress_bar=False)
        
        # Prepare full content - Create STRUCTURED content for better full-doc retrieval
        # Combine all chunks into a clean, structured document
        full_content = self._create_structured_full_content(parsed_data, chunks)
        full_content = full_content[:SCHEMA_MAX_LENGTH] if full_content else ""
        
        # Ensure collection exists
        collection_needs_creation = not utility.has_collection(RESUME_COLLECTION)
        if collection_needs_creation and SCHEMA_AVAILABLE:
            self._ensure_collection_exists(RESUME_COLLECTION, UNIFIED_COLLECTION_SCHEMA)
        
        # Prepare data for insertion with STORAGE OPTIMIZATION
        # Only first chunk stores full_content, others get empty string
        # This reduces storage by ~90% for typical documents
        data_to_insert = []
        full_content_stored = False
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Storage optimization: only store full_content in first chunk
            # Other chunks reference by document_id
            chunk_full_content = full_content if not full_content_stored else ""
            if not full_content_stored:
                full_content_stored = True
                logger.debug(f"Full content ({len(full_content)} chars) stored in chunk 0")
            
            row_data = {
                'document_id': chunk['entity_id'],
                'document_type': 'resume',
                'entity_name': chunk.get('entity_name', 'Unknown'),
                'section_type': chunk['section'],
                'chunk_text': chunk['content'],
                'full_content': chunk_full_content,
                'embedding': embedding.tolist(),
                'created_at': int(time.time()),
            }
            data_to_insert.append(row_data)
        
        # Insert into Milvus
        try:
            collection = Collection(RESUME_COLLECTION)
            collection.insert(data_to_insert)
            logger.info(f"✅ Resume {resume_id} inserted into Milvus ({len(data_to_insert)} chunks)")
            
            try:
                collection.release()
                collection.load()
                logger.info(f"✅ Resume collection refreshed - new data is now queryable")
            except Exception as refresh_err:
                logger.warning(f"⚠️ Collection refresh warning (data still persisted): {refresh_err}")
            
            logger.info(f"✅ Resume {resume_id} stored in Milvus ({len(data_to_insert)} chunks)")
            return resume_id
        
        except Exception as e:
            logger.error(f"❌ Failed to store resume: {e}")
            raise
    
    def _create_structured_full_content(self, parsed_data: Dict[str, Any], chunks: List[Dict[str, Any]]) -> str:
        """Create a well-structured full content for better full-doc retrieval."""
        parts = []
        
        # Get candidate info
        personal = parsed_data.get('personal_info', {})
        name = personal.get('name', 'Unknown')
        
        # Header
        parts.append(f"RESUME: {name}")
        parts.append("=" * 50)
        
        # Organize chunks by section in logical order
        section_order = ['Personal Info', 'Summary', 'Skills', 'Experience', 'Education', 'Projects', 'Certifications', 'Languages', 'Full Resume']
        section_map = {}
        
        for chunk in chunks:
            section = chunk.get('section', 'Other')
            if section not in section_map:
                section_map[section] = []
            section_map[section].append(chunk.get('content', ''))
        
        # Add sections in order
        for section in section_order:
            if section in section_map:
                parts.append(f"\n{section.upper()}")
                parts.append("-" * 30)
                for content in section_map[section]:
                    parts.append(content)
        
        # Add any remaining sections not in the order
        for section, contents in section_map.items():
            if section not in section_order:
                parts.append(f"\n{section.upper()}")
                parts.append("-" * 30)
                for content in contents:
                    parts.append(content)
        
        return "\n".join(parts)
    
    def _delete_existing_jd(self, jd_id: str) -> int:
        """
        Delete existing JD entries to prevent duplicates when updating.
        
        Args:
            jd_id: The job ID (document_id) to delete
        
        Returns:
            Number of entries deleted
        """
        try:
            if not utility.has_collection(JD_COLLECTION):
                return 0
            
            collection = Collection(JD_COLLECTION)
            collection.load()
            
            # Query to find existing entries with this document_id
            expr = f'document_id == "{jd_id}"'
            
            existing = collection.query(
                expr=expr,
                output_fields=['document_id'],
                limit=100  # JDs typically have 15-20 chunks
            )
            
            if existing:
                logger.info(f"🗑️ Found {len(existing)} existing chunks for JD '{jd_id[:8]}...' - deleting before update")
                
                collection.delete(expr)
                try:
                    self._safe_flush(collection)
                except Exception as flush_err:
                    logger.warning(f"   ⚠️ Delete flush timeout (data still deleted from memory): {flush_err}")
                
                try:
                    collection.release()
                    collection.load()
                    logger.info(f"   ✅ Deleted {len(existing)} old chunks - collection refreshed")
                except Exception as refresh_err:
                    logger.warning(f"   ⚠️ Delete flush succeeded, refresh warning: {refresh_err}")
                
                return len(existing)
            
            return 0
            
        except Exception as e:
            logger.warning(f"⚠️ Error deleting existing JD: {e}")
            return 0
    
    def add_jd(self, jd_data: Dict[str, Any]) -> str:
        """
        Add JD to Milvus (with deduplication).
        
        If a JD with the same ID already exists, it will be deleted first
        to ensure only the latest version is stored.
        
        Args:
            jd_data: JD data
        
        Returns:
            JD ID
        """
        if not self._connected:
            raise Exception("Not connected to Milvus")
        
        if not self.encoder:
            raise Exception("Embedding model not loaded")
        
        jd_id = jd_data.get('id', str(uuid.uuid4()))
        logger.info(f"💾 Adding JD to Milvus: {jd_id}")
        
        # Ensure connection is fresh before heavy operations
        self._ensure_connection()
        
        # DEDUPLICATION: Remove existing entries for this JD before adding new ones
        # This ensures updates replace old data instead of creating duplicates
        deleted_count = self._delete_existing_jd(jd_id)
        if deleted_count > 0:
            logger.info(f"✅ Deduplication: Removed {deleted_count} old chunks for JD '{jd_id[:8]}...'")
        
        # Chunk JD
        chunks = self.jd_chunker.chunk_jd(jd_data)
        logger.info(f"Created {len(chunks)} chunks")
        
        if not chunks:
            raise Exception("No chunks created from JD")
        
        # Generate embeddings
        chunk_texts = [chunk['content'] for chunk in chunks]
        embeddings = self.encoder.encode(chunk_texts, show_progress_bar=False)
        
        # Prepare full content (construct from all sections with proper formatting)
        full_content_parts = []
        sections_to_include = [
            ('Job Title', jd_data.get('job_title')),
            ('Department', jd_data.get('department')),
            ('Location', jd_data.get('location')),
            ('About Company', jd_data.get('about_company')),
            ('Position Summary', jd_data.get('position_summary')),
            ('Responsibilities', jd_data.get('responsibilities')),
            ('Required Qualifications', jd_data.get('required_qualifications')),
            ('Preferred Qualifications', jd_data.get('preferred_qualifications')),
            ('Soft Skills', jd_data.get('soft_skills')),
            ('Tools & Technologies', jd_data.get('tools_technologies')),
            ('Success Metrics', jd_data.get('success_metrics')),
            ('Work Environment', jd_data.get('work_environment')),
            ('Compensation & Benefits', jd_data.get('compensation_benefits')),
            ('Equal Opportunity', jd_data.get('equal_opportunity_statement')),
            ('Application Instructions', jd_data.get('application_instructions')),
        ]
        
        for section_name, section_data in sections_to_include:
            if section_data:
                # Use proper formatting for all section types (handles nested dicts)
                content = self._format_jd_section(section_name, section_data)
                if content:
                    full_content_parts.append(f"## {section_name}\n{content}")
        
        full_content = "\n\n".join(full_content_parts)[:SCHEMA_MAX_LENGTH]
        
        # Ensure collection exists
        collection_needs_creation = not utility.has_collection(JD_COLLECTION)
        if collection_needs_creation and SCHEMA_AVAILABLE:
            self._ensure_collection_exists(JD_COLLECTION, UNIFIED_COLLECTION_SCHEMA)
        elif utility.has_collection(JD_COLLECTION):
            # Ensure indexes exist even if collection already exists
            try:
                collection = Collection(JD_COLLECTION)
                # Check if scalar indexes exist, create if missing
                indexes = collection.indexes
                index_fields = [idx.field_name for idx in indexes]
                if "document_type" not in index_fields:
                    collection.create_index(field_name="document_type", index_params={"index_type": "Trie"})
                if "entity_name" not in index_fields:
                    collection.create_index(field_name="entity_name", index_params={"index_type": "Trie"})
                if "section_type" not in index_fields:
                    collection.create_index(field_name="section_type", index_params={"index_type": "Trie"})
            except Exception as e:
                logger.debug(f"Index check/creation skipped: {e}")
        
        # Prepare data for insertion with STORAGE OPTIMIZATION
        # Only first chunk stores full_content, others get empty string
        data_to_insert = []
        full_content_stored = False
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_full_content = full_content if not full_content_stored else ""
            if not full_content_stored:
                full_content_stored = True
                logger.debug(f"JD full content ({len(full_content)} chars) stored in chunk 0")
            
            row_data = {
                'document_id': chunk['entity_id'],
                'document_type': 'jd',
                'entity_name': chunk.get('entity_name', 'Unknown'),
                'section_type': chunk['section'],
                'chunk_text': chunk['content'],
                'full_content': chunk_full_content,
                'embedding': embedding.tolist(),
                'created_at': int(time.time()),
            }
            data_to_insert.append(row_data)
        
        # Insert into Milvus
        try:
            collection = Collection(JD_COLLECTION)
            collection.insert(data_to_insert)
            logger.info(f"✅ JD {jd_id} inserted into Milvus ({len(data_to_insert)} chunks)")
            
            try:
                collection.release()
                collection.load()
                logger.info(f"✅ JD collection refreshed - new data is now queryable")
            except Exception as refresh_err:
                logger.warning(f"⚠️ Collection refresh warning (data still persisted): {refresh_err}")
            
            logger.info(f"✅ JD {jd_id} stored in Milvus ({len(data_to_insert)} chunks)")
            return jd_id
        
        except Exception as e:
            logger.error(f"❌ Failed to store JD: {e}")
            raise
