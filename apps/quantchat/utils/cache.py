"""
Query and Embedding Cache
=========================

In-memory LRU cache for frequently used queries and embeddings.
"""

import hashlib
import time
from typing import Dict, Any, Optional, List
from functools import lru_cache
from collections import OrderedDict
from threading import Lock
from ..config.logging_config import setup_logger
from ..config.settings import (
    ENABLE_QUERY_CACHE, ENABLE_EMBEDDING_CACHE,
    CACHE_TTL_SECONDS
)

logger = setup_logger("cache")


class TTLCache:
    """Thread-safe LRU cache with TTL (Time To Live)."""
    
    def __init__(self, maxsize: int = 1000, ttl: int = CACHE_TTL_SECONDS):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from args."""
        key_str = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired."""
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            # Check TTL
            if time.time() - self.timestamps[key] > self.ttl:
                del self.cache[key]
                del self.timestamps[key]
                self.misses += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
    
    def set(self, key: str, value: Any):
        """Set item in cache."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.maxsize:
                    # Remove oldest item
                    oldest = next(iter(self.cache))
                    del self.cache[oldest]
                    del self.timestamps[oldest]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def clear(self):
        """Clear the cache."""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            self.hits = 0
            self.misses = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "size": len(self.cache),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2%}"
        }


# Global cache instances
_embedding_cache = TTLCache(maxsize=5000, ttl=CACHE_TTL_SECONDS) if ENABLE_EMBEDDING_CACHE else None
_query_cache = TTLCache(maxsize=1000, ttl=CACHE_TTL_SECONDS) if ENABLE_QUERY_CACHE else None


def get_cached_embedding(query: str) -> Optional[List[float]]:
    """Get cached embedding for query."""
    if not _embedding_cache:
        return None
    
    key = hashlib.md5(query.encode()).hexdigest()
    return _embedding_cache.get(key)


def cache_embedding(query: str, embedding: List[float]):
    """Cache embedding for query."""
    if not _embedding_cache:
        return
    
    key = hashlib.md5(query.encode()).hexdigest()
    _embedding_cache.set(key, embedding)
    logger.debug(f"Cached embedding for query hash: {key[:8]}")


def get_cached_query_result(query: str, filters: Dict) -> Optional[List[Dict]]:
    """Get cached retrieval result for query+filters."""
    if not _query_cache:
        return None
    
    key = hashlib.md5(f"{query}:{str(sorted(filters.items()))}".encode()).hexdigest()
    result = _query_cache.get(key)
    if result:
        logger.debug(f"Cache HIT for query: {query[:50]}")
    return result


def cache_query_result(query: str, filters: Dict, results: List[Dict]):
    """Cache retrieval results for query+filters."""
    if not _query_cache:
        return
    
    key = hashlib.md5(f"{query}:{str(sorted(filters.items()))}".encode()).hexdigest()
    _query_cache.set(key, results)
    logger.debug(f"Cached {len(results)} results for query hash: {key[:8]}")


def get_cache_stats() -> Dict[str, Any]:
    """Get all cache statistics."""
    return {
        "embedding_cache": _embedding_cache.stats() if _embedding_cache else "disabled",
        "query_cache": _query_cache.stats() if _query_cache else "disabled"
    }


def clear_all_caches():
    """Clear all caches."""
    if _embedding_cache:
        _embedding_cache.clear()
    if _query_cache:
        _query_cache.clear()
    logger.info("All caches cleared")


# RAG result cache (for full pipeline results)
_rag_result_cache = TTLCache(maxsize=500, ttl=300) if ENABLE_QUERY_CACHE else None  # 5 min TTL


def get_cached_rag_result(query: str, session_id: str = "default") -> Optional[Dict[str, Any]]:
    """
    Get cached RAG result for exact query match.
    
    Only caches results for queries without session context (stateless queries).
    
    Args:
        query: User query
        session_id: Session ID (used to differentiate context)
        
    Returns:
        Cached result or None
    """
    if not _rag_result_cache:
        return None
    
    # Don't cache session-specific queries
    if session_id != "default":
        return None
    
    key = hashlib.md5(query.lower().strip().encode()).hexdigest()
    result = _rag_result_cache.get(key)
    
    if result:
        logger.info(f"RAG cache HIT for query: {query[:50]}")
    
    return result


def cache_rag_result(query: str, result: Dict[str, Any], session_id: str = "default"):
    """
    Cache RAG result for exact query match.
    
    Args:
        query: User query
        result: RAG pipeline result
        session_id: Session ID
    """
    if not _rag_result_cache:
        return
    
    # Only cache high-confidence, stateless results
    if session_id != "default":
        return
    
    confidence = result.get("confidence", 0)
    if confidence < 0.7:  # Don't cache low-confidence results
        return
    
    key = hashlib.md5(query.lower().strip().encode()).hexdigest()
    _rag_result_cache.set(key, result)
    logger.debug(f"Cached RAG result for query: {query[:50]}")
