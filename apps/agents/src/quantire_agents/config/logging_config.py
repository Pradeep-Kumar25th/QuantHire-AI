"""
Logging Configuration for QuantHire AI Agents
==============================================

Enterprise-level logging setup with structured logging.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


class AgentLogger:
    """Enterprise logging configuration for agents."""
    
    _logger: Optional[logging.Logger] = None
    _configured: bool = False
    
    @classmethod
    def configure(
        cls,
        log_level: int = logging.INFO,
        log_file: Optional[Path] = None,
        log_format: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ) -> None:
        """Configure logging for agents.
        
        Args:
            log_level: Logging level (default: INFO)
            log_file: Optional log file path
            log_format: Optional custom log format
            max_bytes: Maximum log file size before rotation
            backup_count: Number of backup log files to keep
        """
        if cls._configured:
            return
        
        if log_format is None:
            log_format = (
                "%(asctime)s - %(name)s - %(levelname)s - "
                "[%(filename)s:%(lineno)d] - %(message)s"
            )
        
        formatter = logging.Formatter(log_format)
        
        # Root logger
        logger = logging.getLogger("quantire_agents")
        logger.setLevel(log_level)
        logger.propagate = False
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        cls._logger = logger
        cls._configured = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get logger instance for a module.
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            Configured logger instance
        """
        if not cls._configured:
            cls.configure()
        
        return logging.getLogger(f"quantire_agents.{name}")
    
    @classmethod
    def reset(cls) -> None:
        """Reset logging configuration (useful for testing)."""
        cls._configured = False
        cls._logger = None
        # Remove all handlers
        root_logger = logging.getLogger("quantire_agents")
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()


# Initialize logging on import
AgentLogger.configure(
    log_file=Path("logs/quantire_agents.log"),
    log_level=logging.INFO
)















