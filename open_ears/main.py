#!/usr/bin/env python3
"""
OpenClaw Ears - Main Entry Point

Ultra-fast voice input system for OpenClaw agents.
Provides optimized STT → Agent → TTS pipeline.
"""

# Standard library
import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for analytics import
sys.path.insert(0, str(Path(__file__).parent.parent))
# Add open_ears directory to path for local imports (inserted last = searched first)
sys.path.insert(0, str(Path(__file__).parent))

# Local imports
from src.config import settings
from src.utils.logging_utils import configure_logging

# Analytics
try:
    from src.services.analytics import get_analytics
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False

# Module-level logger
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Main entry point for OpenClaw Ears.

    Parses command-line arguments and starts the appropriate mode.
    """
    parser = argparse.ArgumentParser(
        description='OpenClaw Ears - Ultra-Fast Voice Input for AI Agents'
    )

    parser.add_argument(
        '--model',
        default=settings.WHISPER_MODEL,
        help='Whisper model size (tiny, base, small, medium)'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=settings.SPEECH_THRESHOLD,
        help='Speech detection threshold (lower = more sensitive)'
    )
    parser.add_argument(
        '--duration',
        type=float,
        default=settings.SEGMENT_DURATION,
        help='Segment duration in seconds (lower = faster response)'
    )
    parser.add_argument(
        '--tts',
        action='store_true',
        default=settings.ENABLE_TTS,
        help='Enable text-to-speech responses'
    )
    parser.add_argument(
        '--log-level',
        default=settings.LOG_LEVEL,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level'
    )

    args = parser.parse_args()

    # Configure logging
    configure_logging(level=args.log_level, log_file=settings.LOG_FILE)

    logger.info("=" * 70)
    logger.info("OpenClaw Ears - Ultra-Fast Voice Input")
    logger.info("=" * 70)
    logger.info(f"Model: {args.model}")
    logger.info(f"Compute Type: {settings.COMPUTE_TYPE}")
    logger.info(f"Silence Duration: {args.duration}s (wait for silence before submitting)")
    logger.info(f"Speech Threshold: {args.threshold}")
    logger.info(f"TTS Enabled: {args.tts}")
    logger.info(f"Log Level: {args.log_level}")
    logger.info("=" * 70)

    # Initialize analytics
    analytics = None
    if ANALYTICS_AVAILABLE:
        try:
            analytics = get_analytics()
            analytics.track_event("ears_started", {
                "model": args.model,
                "compute_type": settings.COMPUTE_TYPE,
                "speech_threshold": args.threshold,
                "silence_duration": args.duration,
                "tts_enabled": args.tts
            })
        except Exception as e:
            logger.warning(f"Analytics initialization failed: {e}")

    # Import and run ultra-fast mode
    try:
        from src.core.voice_pipeline import UltraFastVoicePipeline

        pipeline = UltraFastVoicePipeline(
            model_size=args.model,
            speech_threshold=args.threshold,
            silence_duration=args.duration,
            enable_tts=args.tts,
            analytics=analytics
        )

        pipeline.start()

        if analytics:
            analytics.track_event("ears_stopped", {"reason": "normal_shutdown"})

    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
        if analytics:
            analytics.track_event("ears_stopped", {"reason": "user_interrupt"})
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        if analytics:
            analytics.track_event("ears_error", {
                "error": str(e),
                "error_type": type(e).__name__
            })
        sys.exit(1)


if __name__ == '__main__':
    main()
