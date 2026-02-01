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
# OpenClaw Directories
# ============================================================================
OPENCLAW_DIR: Path = Path.home() / ".openclaw"
EARS_OUTPUT_FILE: Path = OPENCLAW_DIR / "voice" / "transcriptions.txt"
MOUTH_STATUS_FILE: Path = OPENCLAW_DIR / "mouth_status.txt"
MOUTH_INPUT_FILE: Path = OPENCLAW_DIR / "speech_output.txt"

# ============================================================================
# Monitoring Configuration
# ============================================================================
# Mouth status monitoring
MOUTH_STATUS_POLL_INTERVAL: float = float(os.getenv("MOUTH_STATUS_POLL_INTERVAL", "0.1"))
MOUTH_STATUS_DEBOUNCE_MS: int = int(os.getenv("MOUTH_STATUS_DEBOUNCE_MS", "200"))

# Ears pause signal file
EARS_PAUSE_SIGNAL_FILE: Path = OPENCLAW_DIR / "ears_pause.signal"

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
