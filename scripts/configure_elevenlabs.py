#!/usr/bin/env python3
"""
ElevenLabs API Key Setup - Simple API key configuration.

Usage: python scripts/configure_elevenlabs.py
       or: molt-speak elapi
"""

import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_manager import ConfigManager


def main():
    """Simple API key setup."""
    print()
    print("=" * 50)
    print("       ElevenLabs API Key Setup")
    print("=" * 50)
    print()
    print("Get your API key at: https://elevenlabs.io")
    print()

    # Get API key
    api_key = input("Enter your ElevenLabs API key: ").strip()

    if not api_key:
        print("API key cannot be empty")
        sys.exit(1)

    # Verify API key
    print()
    print("Verifying API key...")

    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        voices_response = client.voices.get_all()
        voices = voices_response.voices
        print(f"API key valid. Found {len(voices)} voices.")
    except Exception as e:
        print(f"API key validation failed: {e}")
        sys.exit(1)

    # Save config with defaults
    config = ConfigManager()
    config.elevenlabs_api_key = api_key
    config.elevenlabs_voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel (default)
    config.elevenlabs_model = "eleven_turbo_v2_5"  # Turbo for low latency
    config.tts_provider = "elevenlabs"

    print()
    print("=" * 50)
    print("API key saved.")
    print()
    print("Select your voice from the menu bar:")
    print("  Voice > (choose from ElevenLabs voices)")
    print()
    print("To switch providers, use:")
    print("  TTS Provider > Edge-TTS or ElevenLabs")
    print("=" * 50)
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("Cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
