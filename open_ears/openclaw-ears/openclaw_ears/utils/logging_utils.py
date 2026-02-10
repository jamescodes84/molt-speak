"""
Logging configuration utilities.

Provides centralized logging setup for the OpenClaw Ears application.
"""

# Standard library
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

# Module configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    max_bytes: int = 10_000_000,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to LOG_LEVEL env var or INFO.
        log_file: Optional path to log file. If provided, logs will be
                 written to both stdout and the file with rotation.
                 Defaults to LOG_FILE env var or None.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of backup files to keep.

    Example:
        >>> configure_logging(level="DEBUG", log_file="/var/log/app.log")
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started")
    """
    # Resolve log level
    log_level_str = level or os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Resolve log file
    log_file_path = log_file or os.getenv("LOG_FILE")

    # Create handlers
    handlers = [logging.StreamHandler(sys.stdout)]

    # Add file handler if path is configured
    if log_file_path:
        # Ensure directory exists
        log_dir = os.path.dirname(log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
        handlers=handlers
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Log configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={log_level_str}, file={log_file_path or 'stdout only'}")
