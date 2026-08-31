"""
Milvus Connection Manager
=========================

Robust connection handling with:
- Connection pooling simulation (Milvus doesn't have native pools)
- Automatic reconnection with exponential backoff
- Health monitoring
- Connection lifecycle management

This addresses the gap: No connection pooling or reconnection handling
"""

import time
import logging
from typing import Optional, Callable, Any
from functools import wraps
from pymilvus import connections, utility
from threading import Lock

from ..config.settings import MILVUS_HOST, MILVUS_PORT
from ..config.logging_config import setup_logger

logger = setup_logger("milvus_connection")

# Connection configuration
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 30.0  # seconds
HEALTH_CHECK_INTERVAL = 60  # seconds


class MilvusConnectionManager:
    """
    Singleton connection manager for Milvus.
    
    Features:
    - Thread-safe connection management
    - Automatic reconnection with exponential backoff
    - Health monitoring
    - Graceful degradation
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._connected = False
        self._last_health_check = 0
        self._consecutive_failures = 0
        self._connection_lock = Lock()
        self._initialized = True
    
    def connect(self, force: bool = False) -> bool:
        """
        Connect to Milvus with retry logic.
        
        Args:
            force: Force reconnection even if already connected
            
        Returns:
            True if connected successfully
        """
        with self._connection_lock:
            if self._connected and not force:
                return True
            
            return self._connect_with_retry()
    
    def _connect_with_retry(self) -> bool:
        """Internal connection with exponential backoff."""
        delay = BASE_RETRY_DELAY
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Disconnect first if reconnecting
                try:
                    connections.disconnect("default")
                except:
                    pass
                
                connections.connect(
                    alias="default",
                    host=MILVUS_HOST,
                    port=MILVUS_PORT
                )
                
                # Verify connection
                if self._verify_connection():
                    self._connected = True
                    self._consecutive_failures = 0
                    self._last_health_check = time.time()
                    logger.info(f"✅ Connected to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
                    return True
                    
            except Exception as e:
                self._consecutive_failures += 1
                logger.warning(f"Connection attempt {attempt}/{MAX_RETRIES} failed: {e}")
                
                if attempt < MAX_RETRIES:
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    delay = min(delay * 2, MAX_RETRY_DELAY)
        
        self._connected = False
        logger.error(f"❌ Failed to connect to Milvus after {MAX_RETRIES} attempts")
        return False
    
    def _verify_connection(self) -> bool:
        """Verify connection is actually working."""
        try:
            # Simple operation to verify connection
            utility.list_collections()
            return True
        except Exception as e:
            logger.warning(f"Connection verification failed: {e}")
            return False
    
    def ensure_connected(self) -> bool:
        """
        Ensure we have a valid connection.
        Performs health check if needed.
        """
        current_time = time.time()
        
        # Quick check without lock
        if self._connected:
            # Periodic health check
            if current_time - self._last_health_check > HEALTH_CHECK_INTERVAL:
                return self.health_check()
            return True
        
        # Need to connect
        return self.connect()
    
    def health_check(self) -> bool:
        """
        Perform health check on connection.
        Reconnect if unhealthy.
        """
        with self._connection_lock:
            try:
                if self._verify_connection():
                    self._last_health_check = time.time()
                    return True
            except:
                pass
            
            logger.warning("Health check failed, attempting reconnection...")
            self._connected = False
            return self._connect_with_retry()
    
    def disconnect(self):
        """Disconnect from Milvus."""
        with self._connection_lock:
            try:
                connections.disconnect("default")
                self._connected = False
                logger.info("Disconnected from Milvus")
            except Exception as e:
                logger.warning(f"Disconnect error (may be normal): {e}")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected (quick check, no verification)."""
        return self._connected
    
    @property
    def connection_stats(self) -> dict:
        """Get connection statistics."""
        return {
            "connected": self._connected,
            "consecutive_failures": self._consecutive_failures,
            "last_health_check": self._last_health_check,
            "seconds_since_health_check": time.time() - self._last_health_check if self._last_health_check > 0 else None
        }


# Global singleton instance
_connection_manager = None


def get_connection_manager() -> MilvusConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = MilvusConnectionManager()
    return _connection_manager


def with_milvus_connection(func: Callable) -> Callable:
    """
    Decorator to ensure Milvus connection before executing function.
    
    Automatically reconnects if connection is lost.
    
    Usage:
        @with_milvus_connection
        def my_function():
            # Use Milvus here
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        manager = get_connection_manager()
        
        if not manager.ensure_connected():
            raise ConnectionError("Cannot connect to Milvus")
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a connection-related error
            if any(x in error_str for x in ['connection', 'disconnected', 'timeout', 'unavailable']):
                logger.warning(f"Connection error during operation, retrying: {e}")
                # Try to reconnect and retry once
                if manager.connect(force=True):
                    return func(*args, **kwargs)
            raise
    
    return wrapper


def with_retry(max_retries: int = 2, delay: float = 1.0):
    """
    Decorator for retry logic on Milvus operations.
    
    Args:
        max_retries: Maximum number of retries
        delay: Base delay between retries (doubles each retry)
    
    Usage:
        @with_retry(max_retries=3)
        def my_operation():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning(f"{func.__name__} failed (attempt {attempt + 1}), retrying in {current_delay}s: {e}")
                        time.sleep(current_delay)
                        current_delay *= 2
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {e}")
            
            raise last_error
        
        return wrapper
    return decorator
