"""
Configuration manager for Molt-Speak agent preferences.

Handles reading and writing agent configuration such as preferred voice
and user preferences.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Define paths directly to avoid import issues when loaded via importlib
# Use project directory (molt-speak root) for runtime files
PROJECT_DIR = Path(__file__).parent.parent.parent  # molt-speak root
RUNTIME_DIR = PROJECT_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = RUNTIME_DIR / "molt_speak_config.json"


class ConfigManager:
    """Manages Molt-Speak configuration stored in JSON format."""

    # Default configuration values
    DEFAULT_CONFIG = {
        "preferred_voice": "en-US-ChristopherNeural",
        "user_title": "sir",  # Options: "sir", "madam", or custom name
        "tts_provider": "edge-tts",  # Options: "edge-tts", "elevenlabs"
        "elevenlabs_api_key": None,
        "elevenlabs_voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel (default)
        "elevenlabs_model": "eleven_turbo_v2_5",  # Turbo for low latency
        "mic_sensitivity": "medium",  # Options: "low", "medium", "high", "max"
        "mic_threshold": 40,  # Sensitivity 1-100 (higher = more sensitive)
        "barge_sensitivity": "medium",  # Options: "off", "low", "medium", "high"
        "barge_threshold": 50,  # Sensitivity 1-100 (higher = easier to barge in)
        "agent_boldness": 40,  # Disposition 1-100 (higher = bolder, default = somewhat timid)
        "debug_mode": False,  # Show inline temp/barge-in tags in agent messages
        "crowd_control_enabled": False  # Speaker verification gate (opt-in)
    }

    # Mic sensitivity presets on 1-100 scale (higher = more sensitive)
    # Converted to raw threshold via get_speech_threshold()
    MIC_SENSITIVITY_PRESETS = {
        "low": 1,        # Less sensitive - only loud speech
        "medium": 40,    # Balanced
        "high": 70,      # Sensitive
        "max": 80        # Maximum sensitivity - may pick up noise
    }

    # Barge-in sensitivity presets on 1-100 scale (higher = easier to barge in)
    # Converted to raw multiplier via get_barge_multiplier()
    BARGE_SENSITIVITY_PRESETS = {
        "off": 1,        # Can't interrupt
        "low": 25,       # Hard to interrupt - speak loudly
        "medium": 50,    # Balanced - clear speech interrupts
        "high": 75       # Easy to interrupt - normal speech works
    }

    # Agent boldness presets — controls response threshold and conversation persistence
    # Based on Gray's BIS/BAS model: higher = more behavioral activation, less inhibition
    AGENT_BOLDNESS_PRESETS = {
        "very_timid": 10,    # Only responds to very clear directives
        "timid": 25,         # Conservative, waits for strong signals
        "somewhat_timid": 40, # Default — current behavior
        "balanced": 60,      # Responds readily to directedness
        "bold": 80           # Engages enthusiastically
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the config manager.

        Args:
            config_path: Path to config file. Defaults to CONFIG_FILE from settings.
        """
        self.config_path = config_path or CONFIG_FILE
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """Create config file with defaults if it doesn't exist."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_config(self.DEFAULT_CONFIG)

    def _read_config(self) -> Dict[str, Any]:
        """
        Read configuration from file.

        Returns:
            Configuration dictionary
        """
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            # Ensure all default keys exist
            for key, value in self.DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
        except (json.JSONDecodeError, FileNotFoundError):
            # If file is corrupted or missing, return defaults
            return self.DEFAULT_CONFIG.copy()

    def _write_config(self, config: Dict[str, Any]) -> None:
        """
        Write configuration to file.

        Args:
            config: Configuration dictionary to write
        """
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
            f.flush()  # Ensure data is written to OS buffer
            os.fsync(f.fileno())  # Force write to disk
        # Restrict to owner-only (config may contain API keys)
        os.chmod(self.config_path, 0o600)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key doesn't exist

        Returns:
            Configuration value
        """
        config = self._read_config()
        return config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        config = self._read_config()
        config[key] = value
        self._write_config(config)

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            Complete configuration dictionary
        """
        return self._read_config()

    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple configuration values at once.

        Args:
            updates: Dictionary of key-value pairs to update
        """
        config = self._read_config()
        config.update(updates)
        self._write_config(config)

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self._write_config(self.DEFAULT_CONFIG.copy())

    @property
    def preferred_voice(self) -> str:
        """Get preferred voice setting."""
        return self.get("preferred_voice", self.DEFAULT_CONFIG["preferred_voice"])

    @preferred_voice.setter
    def preferred_voice(self, voice: str) -> None:
        """Set preferred voice setting."""
        self.set("preferred_voice", voice)

    @property
    def user_title(self) -> str:
        """Get user title setting (sir/madam)."""
        return self.get("user_title", self.DEFAULT_CONFIG["user_title"])

    @user_title.setter
    def user_title(self, title: str) -> None:
        """Set user title setting."""
        self.set("user_title", title)

    @property
    def tts_provider(self) -> str:
        """Get TTS provider setting."""
        return self.get("tts_provider", self.DEFAULT_CONFIG["tts_provider"])

    @tts_provider.setter
    def tts_provider(self, provider: str) -> None:
        """Set TTS provider setting."""
        self.set("tts_provider", provider)

    @property
    def elevenlabs_api_key(self) -> Optional[str]:
        """Get ElevenLabs API key."""
        return self.get("elevenlabs_api_key", self.DEFAULT_CONFIG["elevenlabs_api_key"])

    @elevenlabs_api_key.setter
    def elevenlabs_api_key(self, api_key: str) -> None:
        """Set ElevenLabs API key."""
        self.set("elevenlabs_api_key", api_key)

    @property
    def elevenlabs_voice_id(self) -> str:
        """Get ElevenLabs voice ID."""
        return self.get("elevenlabs_voice_id", self.DEFAULT_CONFIG["elevenlabs_voice_id"])

    @elevenlabs_voice_id.setter
    def elevenlabs_voice_id(self, voice_id: str) -> None:
        """Set ElevenLabs voice ID."""
        self.set("elevenlabs_voice_id", voice_id)

    @property
    def elevenlabs_model(self) -> str:
        """Get ElevenLabs model."""
        return self.get("elevenlabs_model", self.DEFAULT_CONFIG["elevenlabs_model"])

    @elevenlabs_model.setter
    def elevenlabs_model(self, model: str) -> None:
        """Set ElevenLabs model."""
        self.set("elevenlabs_model", model)

    @property
    def mic_sensitivity(self) -> str:
        """Get mic sensitivity level (low, medium, high, max)."""
        return self.get("mic_sensitivity", self.DEFAULT_CONFIG["mic_sensitivity"])

    @mic_sensitivity.setter
    def mic_sensitivity(self, level: str) -> None:
        """Set mic sensitivity level and sync the sensitivity value."""
        if level in self.MIC_SENSITIVITY_PRESETS:
            self.set("mic_sensitivity", level)
            self.set("mic_threshold", self.MIC_SENSITIVITY_PRESETS[level])

    @property
    def mic_threshold(self) -> int:
        """Get direct microphone threshold value."""
        return self.get("mic_threshold", self.DEFAULT_CONFIG["mic_threshold"])

    @mic_threshold.setter
    def mic_threshold(self, value: int) -> None:
        """Set mic sensitivity value (1-100, higher = more sensitive)."""
        value = max(1, min(100, int(value)))
        self.set("mic_threshold", value)

    def get_speech_threshold(self) -> int:
        """Convert user-facing sensitivity (1-100) to raw pipeline threshold.

        Higher sensitivity → lower raw threshold → picks up quieter sounds.
        """
        sensitivity = self.mic_threshold
        return max(10, int(500 * (1 - sensitivity / 100)))

    @property
    def barge_sensitivity(self) -> str:
        """Get barge-in sensitivity level (off, low, medium, high)."""
        return self.get("barge_sensitivity", self.DEFAULT_CONFIG["barge_sensitivity"])

    @barge_sensitivity.setter
    def barge_sensitivity(self, level: str) -> None:
        """Set barge-in sensitivity level and sync the threshold value."""
        if level in self.BARGE_SENSITIVITY_PRESETS:
            self.set("barge_sensitivity", level)
            self.set("barge_threshold", self.BARGE_SENSITIVITY_PRESETS[level])

    @property
    def barge_threshold(self) -> int:
        """Get direct barge-in threshold value."""
        return self.get("barge_threshold", self.DEFAULT_CONFIG["barge_threshold"])

    @barge_threshold.setter
    def barge_threshold(self, value: int) -> None:
        """Set barge-in sensitivity value (1-100, higher = easier to barge in)."""
        value = max(1, min(100, int(value)))
        self.set("barge_threshold", value)

    def get_barge_multiplier(self) -> float:
        """Convert user-facing barge sensitivity (1-100) to raw multiplier.

        Higher sensitivity → lower multiplier → easier to interrupt.
        """
        sensitivity = self.barge_threshold
        return max(1.0, (100 - sensitivity) / 10)

    @property
    def agent_boldness(self) -> int:
        """Get agent boldness value (1-100, higher = bolder)."""
        return self.get("agent_boldness", self.DEFAULT_CONFIG["agent_boldness"])

    @agent_boldness.setter
    def agent_boldness(self, value: int) -> None:
        """Set agent boldness value (1-100, higher = bolder)."""
        value = max(1, min(100, int(value)))
        self.set("agent_boldness", value)

    def get_boldness_label(self) -> str:
        """Map boldness value to human-readable disposition label."""
        v = self.agent_boldness
        if v <= 15:
            return "very_timid"
        elif v <= 35:
            return "timid"
        elif v <= 50:
            return "somewhat_timid"
        elif v <= 70:
            return "balanced"
        else:
            return "bold"

    @property
    def debug_mode(self) -> bool:
        """Get debug mode setting."""
        return self.get("debug_mode", self.DEFAULT_CONFIG["debug_mode"])

    @debug_mode.setter
    def debug_mode(self, enabled: bool) -> None:
        """Set debug mode setting."""
        self.set("debug_mode", enabled)

    @property
    def crowd_control_enabled(self) -> bool:
        """Get Crowd Control (speaker verification gate) setting."""
        return self.get("crowd_control_enabled", self.DEFAULT_CONFIG["crowd_control_enabled"])

    @crowd_control_enabled.setter
    def crowd_control_enabled(self, enabled: bool) -> None:
        """Set Crowd Control setting."""
        self.set("crowd_control_enabled", enabled)
