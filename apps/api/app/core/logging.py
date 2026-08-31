"""Enterprise-grade structured logging configuration."""

import logging
import sys
from datetime import datetime
from typing import Any, Dict

# Optional imports for structured logging
try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

try:
    from pythonjsonlogger import jsonlogger
    JSONLOGGER_AVAILABLE = True
except ImportError:
    JSONLOGGER_AVAILABLE = False

from app.config import settings

# Optional PII redaction
try:
    from app.utils.pii_redaction import PIIRedactor
    PII_REDACTION_AVAILABLE = True
except ImportError:
    PII_REDACTION_AVAILABLE = False


def configure_logging() -> None:
    """Configure structured logging for the application."""
    
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Configure structlog if available
    if STRUCTLOG_AVAILABLE:
        try:
            structlog.configure(
                processors=[
                    structlog.contextvars.merge_contextvars,
                    structlog.stdlib.filter_by_level,
                    structlog.stdlib.add_logger_name,
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.StackInfoRenderer(),
                    structlog.processors.format_exc_info,
                    structlog.processors.UnicodeDecoder(),
                    PIIRedactingProcessor() if PII_REDACTION_AVAILABLE else structlog.processors.UnicodeDecoder(),
                    structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
                ],
                logger_factory=structlog.stdlib.LoggerFactory(),
                wrapper_class=structlog.stdlib.BoundLogger,
                cache_logger_on_first_use=True,
            )
        except Exception as e:
            logging.warning(f"Failed to configure structlog: {e}. Using standard logging.")
    
    # Configure standard logging
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add new handler
    if settings.structured_logging and JSONLOGGER_AVAILABLE:
        try:
            handler = logging.StreamHandler(sys.stdout)
            formatter = StructuredLogFormatter()
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)
        except Exception as e:
            logging.warning(f"Failed to configure structured logging: {e}. Using basic logging.")
            logging.basicConfig(
                level=log_level,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[logging.StreamHandler(sys.stdout)],
            )
    else:
        # Simple console logging for development
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )


class StructuredLogFormatter(jsonlogger.JsonFormatter if JSONLOGGER_AVAILABLE else logging.Formatter):
    """JSON formatter with PII redaction and correlation IDs."""
    
    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to log record."""
        if JSONLOGGER_AVAILABLE:
            super().add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record["timestamp"] = datetime.utcnow().isoformat()
        
        # Add service name
        log_record["service"] = "quanthire-api"
        log_record["environment"] = settings.app_env
        
        # Add correlation ID if available (from context)
        import contextvars
        correlation_id = contextvars.ContextVar("correlation_id", default=None)
        if correlation_id.get():
            log_record["correlation_id"] = correlation_id.get()
        
        # Redact PII
        if "message" in log_record and PII_REDACTION_AVAILABLE:
            log_record["message"] = PIIRedactor.redact_text(str(log_record["message"]))


class PIIRedactingProcessor:
    """Structlog processor that redacts PII."""
    
    def __call__(self, logger: Any, name: str, event_dict: Dict) -> Dict:
        """Process log event and redact PII."""
        if not PII_REDACTION_AVAILABLE:
            return event_dict
        
        # Redact PII from event message
        if "event" in event_dict:
            event_dict["event"] = PIIRedactor.redact_text(str(event_dict["event"]))
        
        # Redact PII from extra fields
        for key, value in event_dict.items():
            if isinstance(value, str):
                event_dict[key] = PIIRedactor.redact_text(value)
            elif isinstance(value, dict):
                event_dict[key] = PIIRedactor.redact_dict(value)
        
        return event_dict


def get_logger(name: str) -> Any:
    """
    Get a logger instance with proper configuration.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name)


# Context management for correlation IDs
import contextvars

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for request tracking."""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id_var.get()












