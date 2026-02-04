#!/usr/bin/env python3
"""
ElevenLabs Onboarding Script - Configure ElevenLabs TTS credentials.

Usage: python scripts/configure_elevenlabs.py
       or: molt-speak elo (if installed via setup.py)
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_manager import ConfigManager
from elevenlabs.client import ElevenLabs


def print_header():
    """Print welcome header."""
    print()
    print("=" * 70)
    print("                  ElevenLabs TTS Configuration")
    print("=" * 70)
    print()
    print("This will configure Molt Speak to use ElevenLabs for TTS.")
    print("You'll need an ElevenLabs API key (get one at elevenlabs.io)")
    print()


def get_api_key():
    """Prompt user for API key."""
    print("Step 1: API Key")
    print("-" * 70)
    api_key = input("Enter your ElevenLabs API key: ").strip()

    if not api_key:
        print("❌ API key cannot be empty")
        sys.exit(1)

    return api_key


def test_api_key(api_key):
    """Test API key by trying to list voices."""
    print()
    print("Step 2: Verifying API Key")
    print("-" * 70)
    print("Testing API key by fetching available voices...")

    try:
        client = ElevenLabs(api_key=api_key)
        voices_response = client.voices.get_all()
        voices = voices_response.voices

        if not voices:
            print("⚠️  API key is valid but no voices found in your account")
            return []

        print(f"✅ API key verified! Found {len(voices)} voices in your account")
        return voices

    except Exception as e:
        print(f"❌ API key validation failed: {e}")
        print()
        print("Please check your API key and try again.")
        sys.exit(1)


def select_voice(voices):
    """Let user select a voice from available voices."""
    print()
    print("Step 3: Select Voice")
    print("-" * 70)

    if not voices:
        print("No voices available. Using default voice (Rachel).")
        return "21m00Tcm4TlvDq8ikWAM", "Rachel"

    print("Available voices:")
    print()

    for i, voice in enumerate(voices[:10], 1):  # Show first 10 voices
        name = voice.name
        voice_id = voice.voice_id
        labels = getattr(voice, 'labels', {})
        gender = labels.get('gender', 'unknown') if labels else 'unknown'
        age = labels.get('age', '') if labels else ''

        description = f"{name} ({gender}"
        if age:
            description += f", {age}"
        description += ")"

        print(f"  {i}. {description}")
        print(f"     ID: {voice_id}")

    if len(voices) > 10:
        print(f"\n  ... and {len(voices) - 10} more voices")

    print()
    print("Enter the number of the voice you want to use,")
    print("or press Enter to use the default (Rachel):")

    choice = input("Choice: ").strip()

    if not choice:
        # Use default
        return "21m00Tcm4TlvDq8ikWAM", "Rachel"

    try:
        index = int(choice) - 1
        if 0 <= index < len(voices):
            selected_voice = voices[index]
            return selected_voice.voice_id, selected_voice.name
        else:
            print("Invalid choice. Using default (Rachel).")
            return "21m00Tcm4TlvDq8ikWAM", "Rachel"
    except ValueError:
        print("Invalid input. Using default (Rachel).")
        return "21m00Tcm4TlvDq8ikWAM", "Rachel"


def select_model():
    """Let user select TTS model."""
    print()
    print("Step 4: Select Model")
    print("-" * 70)
    print("Available models:")
    print()
    print("  1. Turbo v2.5 (Recommended - lowest latency, great for real-time)")
    print("  2. Multilingual v2 (Higher quality, supports more languages)")
    print()

    choice = input("Enter your choice (1 or 2, default: 1): ").strip()

    if choice == "2":
        return "eleven_multilingual_v2", "Multilingual v2"
    else:
        return "eleven_turbo_v2_5", "Turbo v2.5"


async def test_voice_async(api_key, voice_id, model):
    """Test the selected voice with a sample synthesis."""
    print()
    print("Step 5: Testing Voice")
    print("-" * 70)

    test_response = input("Would you like to test the voice? (y/n, default: y): ").strip().lower()

    if test_response == 'n':
        return

    print("Generating test audio...")

    try:
        from open_mouth.src.services.elevenlabs_tts_service import ElevenLabsTTSService
        import tempfile
        import subprocess

        tts = ElevenLabsTTSService(
            api_key=api_key,
            voice_id=voice_id,
            model=model
        )

        test_text = "Hello! This is a test of the ElevenLabs voice. How do I sound?"

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            await tts.synthesize_to_file(test_text, tmp_path)
            print("✅ Audio generated successfully!")
            print()
            print("Playing audio...")

            # Play audio using macOS afplay
            subprocess.run(["afplay", str(tmp_path)], check=True)

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        print("✅ Voice test complete!")

    except Exception as e:
        print(f"⚠️  Voice test failed: {e}")
        print("Configuration will still be saved.")


def test_voice(api_key, voice_id, model):
    """Sync wrapper for async test_voice."""
    asyncio.run(test_voice_async(api_key, voice_id, model))


def save_config(api_key, voice_id, model):
    """Save configuration."""
    print()
    print("Step 6: Saving Configuration")
    print("-" * 70)

    config = ConfigManager()
    config.elevenlabs_api_key = api_key
    config.elevenlabs_voice_id = voice_id
    config.elevenlabs_model = model
    config.tts_provider = "elevenlabs"

    print("✅ Configuration saved!")
    print()
    print("ElevenLabs TTS settings:")
    print(f"  • Provider: ElevenLabs")
    print(f"  • Voice ID: {voice_id}")
    print(f"  • Model: {model}")


def print_footer():
    """Print completion message."""
    print()
    print("=" * 70)
    print("                    Setup Complete!")
    print("=" * 70)
    print()
    print("✅ Molt Speak is now configured to use ElevenLabs TTS")
    print()
    print("Next steps:")
    print("  • Start the voice loop: ./scripts/start_voice_loop.sh")
    print("  • Or use the menu bar app")
    print()
    print("To switch back to Edge-TTS (free), you can change the provider")
    print("in the menu bar or edit ~/open-claw-workspace/molt-speak/app/runtime/molt_speak_config.json")
    print()


def main():
    """Main onboarding flow."""
    print_header()

    # Step 1: Get API key
    api_key = get_api_key()

    # Step 2: Test API key
    voices = test_api_key(api_key)

    # Step 3: Select voice
    voice_id, voice_name = select_voice(voices)
    print(f"✅ Selected voice: {voice_name}")

    # Step 4: Select model
    model, model_name = select_model()
    print(f"✅ Selected model: {model_name}")

    # Step 5: Test voice
    test_voice(api_key, voice_id, model)

    # Step 6: Save configuration
    save_config(api_key, voice_id, model)

    # Done!
    print_footer()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        print("❌ Configuration cancelled")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
