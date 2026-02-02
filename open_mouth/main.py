"""
OpenClaw Mouth - Text-to-Speech Output System for AI Agents

Main entry point for the speech system.
"""

import argparse
import logging
import sys
from pathlib import Path

from src.config import settings
from src.core.mouth_pipeline import MouthPipeline
from src.utils.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="OpenClaw Mouth - Text-to-Speech Output System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with default settings
  python main.py

  # Use a different voice
  python main.py --voice en-US-AriaNeural

  # Adjust speech rate (faster)
  python main.py --rate 1.2

  # Use custom input file
  python main.py --input /path/to/custom/file.txt

  # Enable debug logging
  python main.py --log-level DEBUG

  # Compact display mode
  python main.py --compact
"""
    )

    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        help=f"TTS voice identifier (default: {settings.DEFAULT_VOICE})"
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help=f"Speech rate multiplier (default: {settings.DEFAULT_RATE})"
    )

    parser.add_argument(
        "--volume",
        type=float,
        default=None,
        help=f"Volume multiplier 0.0-1.0 (default: {settings.DEFAULT_VOLUME})"
    )

    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help=f"Input file to monitor (default: {settings.INPUT_FILE})"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=settings.LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=f"Logging level (default: {settings.LOG_LEVEL})"
    )

    parser.add_argument(
        "--compact",
        action="store_true",
        help="Use compact display mode (single line)"
    )

    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local TTS (macOS 'say') for INSTANT playback with zero network latency"
    )

    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available TTS voices and exit"
    )

    parser.add_argument(
        "--enable-control",
        action="store_true",
        help="Enable control server for runtime voice changes via menu bar app"
    )

    return parser.parse_args()


async def list_available_voices() -> None:
    """List all available Edge-TTS voices."""
    from src.services.tts_service import TTSService

    print("\nFetching available voices...\n")

    voices = await TTSService.list_voices()

    if not voices:
        print("No voices found or error occurred.")
        return

    # Filter to English voices for simplicity
    english_voices = [v for v in voices if v.get("Locale", "").startswith("en-")]

    print(f"Found {len(english_voices)} English voices:\n")
    print(f"{'Voice ID':<40} {'Gender':<10} {'Locale':<10}")
    print("-" * 65)

    for voice in english_voices[:20]:  # Show first 20
        voice_id = voice.get("ShortName", "Unknown")
        gender = voice.get("Gender", "Unknown")
        locale = voice.get("Locale", "Unknown")
        print(f"{voice_id:<40} {gender:<10} {locale:<10}")

    print(f"\nShowing 20 of {len(english_voices)} English voices.")
    print("For full list, see: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support")


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        args = parse_arguments()

        # Configure logging
        configure_logging(
            level=args.log_level,
            log_file=settings.LOG_FILE
        )

        # Handle --list-voices
        if args.list_voices:
            import asyncio
            asyncio.run(list_available_voices())
            return 0

        logger.info("=" * 80)
        logger.info("OpenClaw Mouth - Text-to-Speech Output System")
        logger.info("=" * 80)

        # Prepare input file path
        input_file = Path(args.input) if args.input else settings.INPUT_FILE

        # Ensure input file exists
        input_file.parent.mkdir(parents=True, exist_ok=True)
        if not input_file.exists():
            input_file.touch()
            logger.info(f"Created input file: {input_file}")

        # Create and start pipeline
        pipeline = MouthPipeline(
            voice=args.voice,
            rate=args.rate,
            volume=args.volume,
            input_file=input_file,
            compact_display=args.compact,
            use_local_tts=args.local,
            enable_control=args.enable_control
        )

        pipeline.start()

        return 0

    except KeyboardInterrupt:
        logger.info("\nReceived keyboard interrupt, shutting down...")
        return 0

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
