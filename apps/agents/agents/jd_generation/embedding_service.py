"""
Embedding Service for JD Generation
===================================
Service for generating embeddings for job descriptions.
"""

import logging
from typing import List, Optional

from agents.jd_generation.config import JDGenerationConfig, get_config
from agents.jd_generation.exceptions import StorageError

logger = logging.getLogger(__name__)

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available. Install with: pip install sentence-transformers")


class EmbeddingService:
    """Service for generating embeddings."""
    
    def __init__(self, config: Optional[JDGenerationConfig] = None):
        """
        Initialize embedding service.
        
        Args:
            config: JDGenerationConfig instance (uses global config if not provided)
        """
        self.config: JDGenerationConfig = config or get_config()
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load embedding model."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers not available. Embeddings will be disabled.")
            return
        
        try:
            logger.info(f"Loading embedding model: {self.config.embedding_model}")
            self.model = SentenceTransformer(self.config.embedding_model)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}", exc_info=True)
            self.model = None
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
            
        Raises:
            StorageError: If embedding generation fails
        """
        if self.model is None:
            # Fallback: return zero vector with correct dimension
            logger.warning(
                "Embedding model not available, returning zero vector",
                extra={"dimension": self.config.embedding_dimension}
            )
            return [0.0] * self.config.embedding_dimension
        
        try:
            # Generate embedding
            embedding = self.model.encode(text, convert_to_numpy=True).tolist()
            
            # Verify dimension
            if len(embedding) != self.config.embedding_dimension:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self.config.embedding_dimension}, "
                    f"got {len(embedding)}"
                )
            
            return embedding
            
        except Exception as e:
            logger.error(
                f"Failed to generate embedding: {e}",
                exc_info=True
            )
            raise StorageError(
                message=f"Failed to generate embedding: {str(e)}",
                storage_type="embedding",
                details={"error": str(e), "text_length": len(text)}
            )
    
    def generate_embedding_for_jd(self, jd: dict) -> List[float]:
        """
        Generate embedding for job description.
        
        Args:
            jd: Job description dictionary
            
        Returns:
            Embedding vector
        """
        # Combine JD fields into text for embedding
        text_parts = []
        
        if jd.get("title"):
            text_parts.append(f"Title: {jd['title']}")
        
        if jd.get("overview"):
            text_parts.append(f"Overview: {jd['overview']}")
        
        if jd.get("responsibilities"):
            if isinstance(jd["responsibilities"], list):
                text_parts.append(f"Responsibilities: {' '.join(jd['responsibilities'])}")
            else:
                text_parts.append(f"Responsibilities: {jd['responsibilities']}")
        
        if jd.get("requirements"):
            req = jd["requirements"]
            if isinstance(req, dict):
                if req.get("required"):
                    text_parts.append(f"Required: {' '.join(req['required'])}")
                if req.get("preferred"):
                    text_parts.append(f"Preferred: {' '.join(req['preferred'])}")
        
        if jd.get("skills"):
            skills = jd["skills"]
            if isinstance(skills, dict):
                if skills.get("technical"):
                    text_parts.append(f"Technical Skills: {' '.join(skills['technical'])}")
                if skills.get("soft"):
                    text_parts.append(f"Soft Skills: {' '.join(skills['soft'])}")
        
        # Combine all parts
        text = " ".join(text_parts)
        
        # If no text, use JSON representation
        if not text:
            import json
            text = json.dumps(jd, default=str)
        
        return self.generate_embedding(text)


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(config: Optional[JDGenerationConfig] = None) -> EmbeddingService:
    """
    Get global embedding service instance (singleton pattern).
    
    Args:
        config: JDGenerationConfig instance (uses global config if not provided)
        
    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(config)
    return _embedding_service


def reset_embedding_service() -> None:
    """Reset global embedding service (useful for testing)."""
    global _embedding_service
    _embedding_service = None

