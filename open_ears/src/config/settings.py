"""
Configuration settings for OpenClaw Ears.

Loads configuration from environment variables with sensible defaults.
"""

# Standard library
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# Project Paths
# ============================================================================
PROJECT_DIR = Path(__file__).parent.parent.parent.parent  # open_speak root
RUNTIME_DIR = PROJECT_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)

# ============================================================================
# Logging Configuration
# ============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Optional[str] = os.getenv("LOG_FILE")

# ============================================================================
# Model Configuration
# ============================================================================
# Model sizes: tiny (fastest), base, small (better accuracy), medium, large
# "small" provides much better transcription accuracy with reasonable speed
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
COMPUTE_TYPE: str = os.getenv("COMPUTE_TYPE", "int8")

# ============================================================================
# Audio Configuration
# ============================================================================
SAMPLE_RATE: int = int(os.getenv("SAMPLE_RATE", "16000"))
# Speech threshold - lower = more sensitive (picks up quieter speech)
# Default 150 is more forgiving than 200
SPEECH_THRESHOLD: int = int(os.getenv("SPEECH_THRESHOLD", "150"))
# Silence duration - how long to wait after speech stops before processing
# Higher = allows more natural pauses while speaking
SEGMENT_DURATION: float = float(os.getenv("SEGMENT_DURATION", "2.5"))

# ============================================================================
# Performance Tuning
# ============================================================================
MAX_CONCURRENT_TRANSCRIPTIONS: int = int(os.getenv("MAX_CONCURRENT_TRANSCRIPTIONS", "3"))
CPU_THREADS: int = int(os.getenv("CPU_THREADS", "4"))

# ============================================================================
# TTS Configuration
# ============================================================================
ENABLE_TTS: bool = os.getenv("ENABLE_TTS", "false").lower() == "true"
TTS_VOICE: str = os.getenv("TTS_VOICE", "us_male")
TTS_RATE: str = os.getenv("TTS_RATE", "+0%")
TTS_VOLUME: str = os.getenv("TTS_VOLUME", "+0%")

# ============================================================================
# OpenClaw Integration
# ============================================================================
VOICE_DIR = RUNTIME_DIR / "voice"
VOICE_DIR.mkdir(exist_ok=True)
OPENCLAW_VOICE_DIR: str = os.getenv("OPENCLAW_VOICE_DIR", str(VOICE_DIR))
ENABLE_HISTORY: bool = os.getenv("ENABLE_HISTORY", "true").lower() == "true"

# Window Targeting Configuration
# Pattern to identify the target Terminal window (case-insensitive substring match)
# Examples: "openclaw", "agent", "claude", or leave empty to use frontmost Terminal
TARGET_WINDOW_PATTERN: str = os.getenv("TARGET_WINDOW_PATTERN", "openclaw")
# Whether to activate (bring to front) the target window before typing
ACTIVATE_TARGET_WINDOW: bool = os.getenv("ACTIVATE_TARGET_WINDOW", "true").lower() == "true"

# ============================================================================
# Feature Flags
# ============================================================================
USE_CACHE: bool = os.getenv("USE_CACHE", "false").lower() == "true"
DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
