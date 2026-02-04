"""Voice configuration persistence."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from . import settings

logger = logging.getLogger(__name__)


class VoiceConfig:
    """Manages voice preferences and configuration."""

    def __init__(self, config_path: str = None):
        """
        Initialize voice config.

        Args:
            config_path: Path to configuration file (defaults to project runtime)
        """
        if config_path is None:
            config_path = str(settings.RUNTIME_DIR / "voice_preferences.json")
        self.config_path = Path(config_path).expanduser()
        self.config_path.parent.mkdir(exist_ok=True)

        # Default configuration
        self.config = {
            "last_voice": "Alex",
            "last_mode": "local",
            "last_rate": 1.0,
            "last_volume": 1.0,
            "favorites": [],
            "recent_voices": []
        }

        # Load existing config
        self.load()

    def load(self) -> bool:
        """
        Load configuration from file.

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if not self.config_path.exists():
                logger.info("No config file found, using defaults")
                return False

            with open(self.config_path, "r") as f:
                loaded_config = json.load(f)

            # Merge with defaults (in case new keys were added)
            self.config.update(loaded_config)

            logger.info(f"Loaded config from {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return False

    def save(self) -> bool:
        """
        Save configuration to file.

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Atomic write (write to temp file, then rename)
            temp_file = self.config_path.with_suffix(".tmp")

            with open(temp_file, "w") as f:
                json.dump(self.config, f, indent=2)

            temp_file.replace(self.config_path)

            logger.debug(f"Saved config to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    # Last used settings
    def set_last_voice(self, voice: str, mode: str) -> None:
        """
        Set last used voice.

        Args:
            voice: Voice identifier
            mode: TTS mode ("local" or "cloud")
        """
        self.config["last_voice"] = voice
        self.config["last_mode"] = mode
        self.add_recent_voice(voice, mode)
        self.save()

    def get_last_voice(self) -> tuple:
        """
        Get last used voice.

        Returns:
            Tuple of (voice, mode)
        """
        return (self.config["last_voice"], self.config["last_mode"])

    def set_last_rate(self, rate: float) -> None:
        """Set last used rate."""
        self.config["last_rate"] = rate
        self.save()

    def get_last_rate(self) -> float:
        """Get last used rate."""
        return self.config["last_rate"]

    def set_last_volume(self, volume: float) -> None:
        """Set last used volume."""
        self.config["last_volume"] = volume
        self.save()

    def get_last_volume(self) -> float:
        """Get last used volume."""
        return self.config["last_volume"]

    # Favorites
    def add_favorite(self, voice: str, voice_type: str) -> bool:
        """
        Add voice to favorites.

        Args:
            voice: Voice identifier
            voice_type: "local" or "cloud"

        Returns:
            True if added, False if already in favorites
        """
        favorite = {"name": voice, "type": voice_type}

        # Check if already in favorites
        for fav in self.config["favorites"]:
            if fav["name"] == voice and fav["type"] == voice_type:
                return False

        self.config["favorites"].append(favorite)
        self.save()
        logger.info(f"Added {voice} to favorites")
        return True

    def remove_favorite(self, voice: str, voice_type: str) -> bool:
        """
        Remove voice from favorites.

        Args:
            voice: Voice identifier
            voice_type: "local" or "cloud"

        Returns:
            True if removed, False if not in favorites
        """
        initial_len = len(self.config["favorites"])

        self.config["favorites"] = [
            fav for fav in self.config["favorites"]
            if not (fav["name"] == voice and fav["type"] == voice_type)
        ]

        if len(self.config["favorites"]) < initial_len:
            self.save()
            logger.info(f"Removed {voice} from favorites")
            return True

        return False

    def get_favorites(self) -> List[Dict[str, str]]:
        """
        Get list of favorite voices.

        Returns:
            List of favorite voice dictionaries
        """
        return self.config["favorites"]

    def is_favorite(self, voice: str, voice_type: str) -> bool:
        """
        Check if voice is in favorites.

        Args:
            voice: Voice identifier
            voice_type: "local" or "cloud"

        Returns:
            True if voice is in favorites
        """
        for fav in self.config["favorites"]:
            if fav["name"] == voice and fav["type"] == voice_type:
                return True
        return False

    # Recent voices
    def add_recent_voice(self, voice: str, voice_type: str, max_recent: int = 10) -> None:
        """
        Add voice to recent voices list.

        Args:
            voice: Voice identifier
            voice_type: "local" or "cloud"
            max_recent: Maximum number of recent voices to keep
        """
        recent = {
            "name": voice,
            "type": voice_type,
            "last_used": datetime.now().isoformat()
        }

        # Remove if already in list
        self.config["recent_voices"] = [
            r for r in self.config["recent_voices"]
            if not (r["name"] == voice and r["type"] == voice_type)
        ]

        # Add to front
        self.config["recent_voices"].insert(0, recent)

        # Trim to max_recent
        self.config["recent_voices"] = self.config["recent_voices"][:max_recent]

        self.save()

    def get_recent_voices(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Get list of recently used voices.

        Args:
            limit: Maximum number to return, None for all

        Returns:
            List of recent voice dictionaries
        """
        recent = self.config["recent_voices"]
        if limit:
            return recent[:limit]
        return recent

    # Utility
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.config = {
            "last_voice": "Alex",
            "last_mode": "local",
            "last_rate": 1.0,
            "last_volume": 1.0,
            "favorites": [],
            "recent_voices": []
        }
        self.save()
        logger.info("Reset configuration to defaults")
