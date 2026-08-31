"""Logging middleware for request/response tracking."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timer
        start_time = time.time()

        # Log request
        logger.info(
            "request_started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            logger.error(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "duration_ms": int(duration * 1000),
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

        # Calculate duration
        duration = time.time() - start_time

        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration:.4f}"

        # Log response
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "status_code": response.status_code,
                "duration_ms": int(duration * 1000),
            },
        )

        return response

