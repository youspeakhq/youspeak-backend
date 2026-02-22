"""Structured JSON Logging Configuration"""

import logging
import sys
from typing import Any
from pythonjsonlogger import jsonlogger

from app.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        """Add custom fields to log record"""
        super().add_fields(log_record, record, message_dict)
        
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["environment"] = settings.ENVIRONMENT
        log_record["app_name"] = settings.APP_NAME
        
        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = record.correlation_id


def setup_logging() -> None:
    """Configure application logging"""
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.LOG_FORMAT == "json":
        # JSON format for production
        formatter = CustomJsonFormatter(
            fmt="%(asctime)s %(level)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
