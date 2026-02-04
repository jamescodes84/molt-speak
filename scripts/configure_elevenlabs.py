#!/usr/bin/env python3
"""
ElevenLabs API Key Setup - Simple API key configuration.

Usage: python scripts/configure_elevenlabs.py
       or: molt-speak elapi
"""

import sys
import re
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_manager import ConfigManager


def validate_api_key(key: str) -> bool:
    """Validate that input looks like an ElevenLabs API key."""
    # ElevenLabs keys start with sk_ and contain only alphanumeric + underscore
    if not key:
        return False
    # Must start with sk_
    if not key.startswith("sk_"):
        return False
    # Only allow alphanumeric and underscore (no shell metacharacters)
    if not re.match(r'^[a-zA-Z0-9_]+$', key):
        return False
    # Reasonable length (ElevenLabs keys are typically 40-60 chars)
    if len(key) < 20 or len(key) > 100:
        return False
    return True


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

    # Validate format before doing anything with it
    if not validate_api_key(api_key):
        print("Invalid API key format.")
        print("ElevenLabs keys start with 'sk_' and contain only letters, numbers, and underscores.")
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
