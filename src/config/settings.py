"""
Configuration settings for OpenClaw Integration.

Loads configuration from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# Logging Configuration
# ============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Optional[str] = os.getenv("LOG_FILE")

# ============================================================================
# Project Directories
# ============================================================================
PROJECT_DIR: Path = Path(__file__).parent.parent.parent  # molt-speak root
RUNTIME_DIR: Path = PROJECT_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# Configuration file
CONFIG_FILE: Path = RUNTIME_DIR / "molt_speak_config.json"

# Speech output directory - uses runtime directory for reliable permissions
SPEECH_OUTPUT_DIR: Path = RUNTIME_DIR
# No need to mkdir since RUNTIME_DIR is already created above

EARS_OUTPUT_FILE: Path = RUNTIME_DIR / "transcriptions.txt"
MOUTH_STATUS_FILE: Path = RUNTIME_DIR / "mouth_status.txt"
MOUTH_INPUT_FILE: Path = SPEECH_OUTPUT_DIR / "speech_output.txt"

# ============================================================================
# Monitoring Configuration
# ============================================================================
# Mouth status monitoring
MOUTH_STATUS_POLL_INTERVAL: float = float(os.getenv("MOUTH_STATUS_POLL_INTERVAL", "0.1"))
MOUTH_STATUS_DEBOUNCE_MS: int = int(os.getenv("MOUTH_STATUS_DEBOUNCE_MS", "200"))

# Ears pause signal file
EARS_PAUSE_SIGNAL_FILE: Path = RUNTIME_DIR / "ears_pause.signal"

# ============================================================================
# Integration Mode
# ============================================================================
ENABLE_INTEGRATION: bool = os.getenv("ENABLE_INTEGRATION", "true").lower() == "true"
ENABLE_BIDIRECTIONAL: bool = os.getenv("ENABLE_BIDIRECTIONAL", "false").lower() == "true"

# ============================================================================
# Performance Tuning
# ============================================================================
MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", "10"))
PROCESSING_TIMEOUT: float = float(os.getenv("PROCESSING_TIMEOUT", "30.0"))

# ============================================================================
# Analytics (PostHog)
# ============================================================================
POSTHOG_API_KEY: Optional[str] = os.getenv("POSTHOG_API_KEY")
POSTHOG_HOST: str = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
POSTHOG_DISABLED: bool = os.getenv("POSTHOG_DISABLED", "false").lower() == "true"
