"""Redis-based rate limiting middleware for distributed deployments."""

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - rate limiting will use in-memory fallback")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-based rate limiting middleware for production.
    
    Falls back to in-memory rate limiting if Redis is unavailable.
    Supports distributed deployments with multiple instances.
    """

    def __init__(self, app, rate_limit: Optional[int] = None, redis_url: Optional[str] = None):
        """
        Initialize rate limiter.
        
        Args:
            app: ASGI application
            rate_limit: Maximum requests per minute (defaults to settings.rate_limit_per_minute)
            redis_url: Redis connection URL (defaults to settings.redis_url)
        """
        super().__init__(app)
        self.rate_limit = rate_limit or settings.rate_limit_per_minute
        self.redis_url = redis_url or settings.redis_url
        
        # Initialize Redis client
        self.redis_client = None
        self._redis_available = False
        self._in_memory_requests = {}  # Fallback for in-memory rate limiting
        
        if REDIS_AVAILABLE:
            self._init_redis()
        else:
            logger.warning(
                "Redis not available - using in-memory rate limiting. "
                "This will not work correctly with multiple instances."
            )

    def _init_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            self.redis_client.ping()
            self._redis_available = True
            logger.info(f"✅ Redis rate limiting connected: {self.redis_url}")
        except Exception as e:
            # Expected in dev environment without Redis - use debug level
            logger.debug(
                f"Redis not available for rate limiting: {e}. "
                "Using in-memory rate limiting (suitable for development)."
            )
            self._redis_available = False
            self.redis_client = None

    def _get_client_identifier(self, request: Request) -> str:
        """
        Get client identifier for rate limiting.
        
        Tries to get real IP from headers (for reverse proxy setups),
        falls back to direct client IP.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client identifier string
        """
        # Check for real IP in headers only when a trusted proxy is configured
        if settings.trust_proxy_headers:
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
                return f"ip:{client_ip}"

            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return f"ip:{real_ip}"

        if request.client:
            return f"ip:{request.client.host}"

        return "ip:unknown"

    def _check_rate_limit_redis(self, client_id: str) -> tuple[bool, int, int]:
        """
        Check rate limit using Redis (distributed).
        
        Args:
            client_id: Client identifier
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        if not self._redis_available or not self.redis_client:
            if settings.is_hardened:
                return False, 0, 60
            return True, self.rate_limit, 60
        
        try:
            key = f"rate_limit:{client_id}"
            current_time = int(time.time())
            window_start = current_time - 60  # 1 minute window
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove old entries (older than 1 minute)
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration (cleanup after 2 minutes)
            pipe.expire(key, 120)
            
            results = pipe.execute()
            current_count = results[1]  # Count from zcard
            
            # Check if limit exceeded
            is_allowed = current_count < self.rate_limit
            remaining = max(0, self.rate_limit - current_count - 1)
            reset_time = 60 - (current_time % 60)  # Seconds until window resets
            
            return is_allowed, remaining, reset_time
            
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}.")
            if settings.is_hardened:
                return False, 0, 60
            return True, self.rate_limit, 60

    def _check_rate_limit_memory(self, client_id: str) -> tuple[bool, int, int]:
        """
        Check rate limit using in-memory storage (fallback).
        
        Args:
            client_id: Client identifier
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        current_time = time.time()
        
        # Initialize if not exists
        if client_id not in self._in_memory_requests:
            self._in_memory_requests[client_id] = []
        
        # Clean old requests (older than 1 minute)
        self._in_memory_requests[client_id] = [
            ts for ts in self._in_memory_requests[client_id]
            if current_time - ts < 60
        ]
        
        # Check limit
        current_count = len(self._in_memory_requests[client_id])
        is_allowed = current_count < self.rate_limit
        
        if is_allowed:
            # Add current request
            self._in_memory_requests[client_id].append(current_time)
        
        remaining = max(0, self.rate_limit - current_count - 1)
        reset_time = 60 - (current_time % 60)

        if len(self._in_memory_requests) > 10000:
            self._in_memory_requests = {
                key: timestamps
                for key, timestamps in self._in_memory_requests.items()
                if timestamps
            }

        return is_allowed, remaining, reset_time

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health checks; docs are disabled in hardened envs
        if request.url.path in ["/health", "/healthz", "/readyz"]:
            return await call_next(request)
        if not settings.is_hardened and request.url.path in [
            "/docs",
            "/redoc",
            "/openapi.json",
        ]:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_identifier(request)
        
        # Check rate limit
        if self._redis_available:
            is_allowed, remaining, reset_time = self._check_rate_limit_redis(client_id)
        else:
            is_allowed, remaining, reset_time = self._check_rate_limit_memory(client_id)
        
        # If rate limit exceeded, return 429
        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {self.rate_limit} requests per minute allowed",
                    "retry_after": reset_time,
                },
                headers={
                    "X-RateLimit-Limit": str(self.rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + reset_time),
                    "Retry-After": str(reset_time),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + reset_time)
        
        return response
