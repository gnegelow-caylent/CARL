"""
Logging configuration for CARL.
"""

import logging
import os
import sys
from typing import Any

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in [
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "thread",
                    "threadName",
                    "message",
                ]:
                    log_record[key] = value

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        # Use JSON formatting in Lambda (production)
        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            handler.setFormatter(JSONFormatter())
        else:
            # Human-readable format for local development
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )

        logger.addHandler(handler)
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    return logger


def log_event(logger: logging.Logger, event_type: str, **kwargs: Any) -> None:
    """
    Log a structured event.

    Args:
        logger: Logger instance
        event_type: Type of event being logged
        **kwargs: Additional event data
    """
    logger.info(event_type, extra=kwargs)
