"""Configuration settings for OpenClaw Mouth TTS system."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Voice Configuration
DEFAULT_VOICE = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")
DEFAULT_RATE = float(os.getenv("TTS_RATE", "1.0"))
DEFAULT_VOLUME = float(os.getenv("TTS_VOLUME", "1.0"))
DEFAULT_PITCH = float(os.getenv("TTS_PITCH", "0.0"))

# Input Configuration
# Use project-local runtime directory instead of ~/.openclaw
PROJECT_DIR = Path(__file__).parent.parent.parent.parent  # open_speak root
RUNTIME_DIR = PROJECT_DIR / "runtime"
INPUT_FILE = Path(os.getenv("INPUT_FILE", str(RUNTIME_DIR / "speech_output.txt")))
MONITOR_INTERVAL = float(os.getenv("MONITOR_INTERVAL", "0.1"))  # Check file every 0.1s

# Status file for echo prevention coordination
MOUTH_STATUS_FILE = RUNTIME_DIR / "mouth_status.txt"

# Audio Configuration
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "24000"))
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", "1024"))

# Queue Configuration
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "10"))  # Prevent memory issues

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE")  # Optional file logging

# Display Configuration
DISPLAY_UPDATE_RATE = float(os.getenv("DISPLAY_UPDATE_RATE", "0.05"))  # 20Hz
ENABLE_COLORS = os.getenv("ENABLE_COLORS", "true").lower() == "true"

# System Paths
RUNTIME_DIR.mkdir(exist_ok=True)
INPUT_FILE.parent.mkdir(exist_ok=True)

# Available voices (common Edge-TTS voices)
AVAILABLE_VOICES = {
    "christopher": "en-US-ChristopherNeural",
    "aria": "en-US-AriaNeural",
    "jenny": "en-US-JennyNeural",
    "guy": "en-US-GuyNeural",
    "davis": "en-US-DavisNeural",
    "amber": "en-US-AmberNeural",
}


def get_voice(voice_name: Optional[str] = None) -> str:
    """
    Get voice identifier from name or use default.

    Args:
        voice_name: Voice name (e.g., 'christopher', 'aria') or full identifier

    Returns:
        Full voice identifier for Edge-TTS
    """
    if voice_name is None:
        return DEFAULT_VOICE

    # Check if it's a shorthand name
    if voice_name.lower() in AVAILABLE_VOICES:
        return AVAILABLE_VOICES[voice_name.lower()]

    # Otherwise assume it's a full identifier
    return voice_name
