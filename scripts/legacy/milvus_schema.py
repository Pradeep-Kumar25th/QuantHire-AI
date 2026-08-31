"""
Milvus Schema Definition - Production Ready
===========================================

Unified schema for QuantChat AI RAG system.
Optimized for:
- Fast semantic search (HNSW index)
- Full document retrieval (full_content field)
- Entity filtering (entity_name field)
- Section-wise queries (section_type field)
- Efficient RAG operations (chunk_text field)
"""

from pymilvus import FieldSchema, DataType, CollectionSchema

# Embedding dimension (must match embedding model: BAAI/bge-base-en-v1.5)
EMBEDDING_DIM = 768

# Maximum full content length (Milvus VARCHAR limit)
MAX_FULL_CONTENT_LENGTH = 65535
MAX_CHUNK_TEXT_LENGTH = 5000

# Unified Schema Fields (for both resumes and JDs)
UNIFIED_FIELDS = [
    # Primary Key
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    
    # Document Identification
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=200, description="Resume/JD unique ID"),
    FieldSchema(name="document_type", dtype=DataType.VARCHAR, max_length=50, description="'resume' or 'jd'"),
    FieldSchema(name="entity_name", dtype=DataType.VARCHAR, max_length=300, description="Candidate name or Job title"),
    
    # Content Organization
    FieldSchema(name="section_type", dtype=DataType.VARCHAR, max_length=100, description="Section category (Skills, Experience, etc.)"),
    FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=MAX_CHUNK_TEXT_LENGTH, description="Chunk content for RAG search"),
    
    # Full Content Field (for efficient full-document retrieval)
    FieldSchema(
        name="full_content", 
        dtype=DataType.VARCHAR, 
        max_length=MAX_FULL_CONTENT_LENGTH, 
        description="Complete document text (for full-doc retrieval)"
    ),
    
    # Vector Embedding
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM, description="768-dim vector embedding"),
    
    # Metadata
    FieldSchema(name="created_at", dtype=DataType.INT64, description="Unix timestamp"),
]

# Create unified collection schema
UNIFIED_COLLECTION_SCHEMA = CollectionSchema(
    fields=UNIFIED_FIELDS,
    description="Unified collection for resumes and JDs with full document support"
)

# HNSW Index Parameters (optimized for high recall)
INDEX_PARAMS = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {
        "M": 16,      # Number of connections per node
        "efConstruction": 200,  # Build-time search width
    }
}

# Scalar Index Parameters for VARCHAR fields (Trie for prefix matching, fast filtering)
SCALAR_INDEX_PARAMS = {
    "index_type": "Trie"  # Trie is correct for VARCHAR, INVERTED not supported
}

# Search Parameters (optimized for high recall)
SEARCH_PARAMS = {
    "metric_type": "COSINE",
    "params": {"ef": 128}  # Search-time width (higher = better recall, slower)
}

# Collection Names
RESUME_COLLECTION = "quanthire_resumes"
JD_COLLECTION = "quanthire_job_descriptions"
UNIFIED_COLLECTION = "quanthire_documents"  # Optional: single unified collection
