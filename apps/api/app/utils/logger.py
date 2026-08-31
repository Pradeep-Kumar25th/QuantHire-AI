"""Structured logging utility."""

import logging
import sys
from typing import Any

# Optional structlog import
try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

from app.config import settings


def setup_logging() -> Any:
    """Setup structured logging.
    
    Returns:
        Logger: Configured logger (structlog if available, else standard logging)
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    if STRUCTLOG_AVAILABLE:
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
                if settings.structured_logging
                else structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        return structlog.get_logger()
    else:
        # Fallback to standard logging
        return logging.getLogger(__name__)


# Global logger instance
logger = setup_logging()

