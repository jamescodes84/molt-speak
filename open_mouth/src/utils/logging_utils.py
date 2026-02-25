"""Logging utilities for OpenClaw Mouth."""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10_000_000,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file (None = stdout only)
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]

    # Add file handler if path is configured
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True  # Override any existing configuration
    )

    # Reduce noise from third-party libraries
    logging.getLogger("watchdog").setLevel(logging.WARNING)


def log_thought(logger: logging.Logger, message: str) -> None:
    """
    Log a processing thought/step.

    Args:
        logger: Logger instance
        message: Message to log
    """
    logger.debug(f"💭 {message}")


def log_speaking(logger: logging.Logger, text: str) -> None:
    """
    Log when text is being spoken.

    Args:
        logger: Logger instance
        text: Text being spoken
    """
    preview = text[:100] + "..." if len(text) > 100 else text
    logger.info(f"📢 Speaking: {preview}")


def log_queued(logger: logging.Logger, text: str) -> None:
    """
    Log when text is queued for synthesis.

    Args:
        logger: Logger instance
        text: Text queued
    """
    preview = text[:100] + "..." if len(text) > 100 else text
    logger.debug(f"⏳ Queued: {preview}")


def log_error(logger: logging.Logger, error: Exception, context: str = "") -> None:
    """
    Log an error with context.

    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Additional context about where/why the error occurred
    """
    if context:
        logger.error(f"❌ Error in {context}: {error}", exc_info=True)
    else:
        logger.error(f"❌ Error: {error}", exc_info=True)
