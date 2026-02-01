#!/usr/bin/env python3
"""
OpenClaw Voice Loop Integration

Coordinates OpenClaw Ears (voice input) and OpenClaw Mouth (TTS output)
to prevent echo and feedback in full voice conversations.

Usage:
    python main.py

Environment Variables:
    ENABLE_INTEGRATION - Enable/disable integration (default: true)
    MOUTH_STATUS_POLL_INTERVAL - Polling interval in seconds (default: 0.1)
    MOUTH_STATUS_DEBOUNCE_MS - Debounce time in milliseconds (default: 200)
    LOG_LEVEL - Logging level (default: INFO)

Author: OpenClaw
Version: 1.0.0
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import settings
from src.core.coordinator import VoiceLoopCoordinator


def configure_logging() -> None:
    """Configure application-wide logging."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configure format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure handlers
    handlers = [logging.StreamHandler(sys.stdout)]

    if settings.LOG_FILE:
        log_file = Path(settings.LOG_FILE)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(settings.LOG_FILE))

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

    # Reduce noise from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main() -> int:
    """Main entry point."""
    # Configure logging
    configure_logging()

    logger = logging.getLogger(__name__)

    try:
        # Create and start coordinator
        coordinator = VoiceLoopCoordinator()
        coordinator.start()
        return 0

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
