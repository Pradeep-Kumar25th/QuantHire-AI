"""Enterprise middleware for FastAPI application."""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.exceptions import QuantHireException
from app.core.logging import set_correlation_id

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context for logging and tracing.
    
    Adds:
    - Correlation ID
    - Request timing
    - User context
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add context."""
        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(__import__("uuid").uuid4())
        
        # Set in logging context
        set_correlation_id(correlation_id)
        
        # Store in request state
        request.state.correlation_id = correlation_id
        request.state.start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = correlation_id
        
        # Add timing header
        process_time = time.time() - request.state.start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        # Only log server errors - PerformanceMonitoringMiddleware handles slow request warnings
        if response.status_code >= 500:
            logger.warning(
                f"Error: {request.method} {request.url.path} - {response.status_code} ({process_time*1000:.0f}ms)"
            )
        
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handler middleware.
    
    Catches unhandled exceptions and formats them properly.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle errors globally."""
        try:
            response = await call_next(request)
            return response
        
        except QuantHireException as e:
            # Custom exceptions - return formatted error
            logger.warning(
                f"Application error: {e.error_code}",
                extra={
                    "error_code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                    "path": request.url.path,
                }
            )
            
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.error_code,
                        "message": e.message,
                        "details": e.details,
                        "correlation_id": getattr(request.state, "correlation_id", None),
                        "path": str(request.url.path),
                    }
                }
            )
        
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unhandled exception: {type(e).__name__}",
                extra={
                    "error": str(e),
                    "path": request.url.path,
                },
                exc_info=True,
            )
            
            from fastapi.responses import JSONResponse
            
            # Don't expose internal errors in production
            if hasattr(request.app.state, "settings"):
                hide_internals = request.app.state.settings.is_hardened
            else:
                hide_internals = False

            error_detail = "Internal server error" if hide_internals else str(e)
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": error_detail,
                        "correlation_id": getattr(request.state, "correlation_id", None),
                    }
                }
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content-Security-Policy: More permissive for docs page to allow Swagger UI
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            # Allow Swagger UI resources (CDN, inline scripts, etc.)
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: https:; "
                "connect-src 'self'"
            )
        else:
            # Strict CSP for API endpoints
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
            )
        
        return response


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Monitor API performance and log slow requests."""
    
    def __init__(self, app: ASGIApp, slow_request_threshold: float = 1.0):
        """
        Initialize performance monitoring.
        
        Args:
            app: ASGI application
            slow_request_threshold: Threshold in seconds for slow request warning
        """
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance."""
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # Log slow requests
        if process_time > self.slow_request_threshold:
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "process_time_ms": process_time * 1000,
                    "threshold_ms": self.slow_request_threshold * 1000,
                }
            )
        
        return response












