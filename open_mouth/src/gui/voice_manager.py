"""Voice management and enumeration."""

import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import asyncio

from ..config import settings

logger = logging.getLogger(__name__)


class VoiceManager:
    """Manages voice discovery and caching."""

    def __init__(self, cache_ttl_hours: int = 24):
        """
        Initialize voice manager.

        Args:
            cache_ttl_hours: Hours before cached voices expire
        """
        self.cache_dir = settings.RUNTIME_DIR
        self.cache_file = self.cache_dir / "voice_cache.json"
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        # Ensure cache directory exists
        self.cache_dir.mkdir(exist_ok=True)

    def get_local_voices(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """
        Get list of local macOS voices.

        Args:
            force_refresh: Force refresh instead of using cache

        Returns:
            List of voice dictionaries with name, locale, and description
        """
        try:
            # Check cache first
            if not force_refresh:
                cached = self._load_cached_voices("local")
                if cached:
                    return cached

            # Run say -v "?" to get voice list
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                logger.error("Failed to get local voices")
                return []

            # Parse voice list
            voices = []
            for line in result.stdout.strip().split("\n"):
                # Format: "VoiceName    locale    # description"
                parts = line.split("#", 1)
                if len(parts) == 2:
                    name_locale = parts[0].strip().split()
                    if len(name_locale) >= 2:
                        name = name_locale[0]
                        locale = name_locale[1]
                        description = parts[1].strip()

                        voices.append({
                            "name": name,
                            "locale": locale,
                            "description": description,
                            "type": "local"
                        })

            # Cache the results
            self._save_cached_voices("local", voices)

            logger.info(f"Found {len(voices)} local voices")
            return voices

        except Exception as e:
            logger.error(f"Error getting local voices: {e}")
            return []

    def get_cloud_voices(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """
        Get list of Edge-TTS cloud voices.

        Args:
            force_refresh: Force refresh instead of using cache

        Returns:
            List of voice dictionaries with name, locale, gender
        """
        try:
            # Check cache first
            if not force_refresh:
                cached = self._load_cached_voices("cloud")
                if cached:
                    return cached

            # Import edge_tts
            try:
                import edge_tts
            except ImportError:
                logger.error("edge_tts not installed")
                return []

            # Fetch voices asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            voices_data = loop.run_until_complete(edge_tts.list_voices())
            loop.close()

            # Filter to English voices and format
            voices = []
            for voice in voices_data:
                locale = voice.get("Locale", "")
                if locale.startswith("en-"):
                    voices.append({
                        "name": voice.get("ShortName", ""),
                        "locale": locale,
                        "gender": voice.get("Gender", "Unknown"),
                        "description": f"{voice.get('FriendlyName', '')} ({locale})",
                        "type": "cloud"
                    })

            # Cache the results
            self._save_cached_voices("cloud", voices)

            logger.info(f"Found {len(voices)} cloud voices")
            return voices

        except Exception as e:
            logger.error(f"Error getting cloud voices: {e}")
            return []

    def get_all_voices(self, force_refresh: bool = False) -> Dict[str, List[Dict[str, str]]]:
        """
        Get all available voices (local and cloud).

        Args:
            force_refresh: Force refresh instead of using cache

        Returns:
            Dictionary with 'local' and 'cloud' keys containing voice lists
        """
        return {
            "local": self.get_local_voices(force_refresh),
            "cloud": self.get_cloud_voices(force_refresh)
        }

    def search_voices(self, query: str, voice_type: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Search for voices by name, locale, or description.

        Args:
            query: Search query
            voice_type: Filter by type ("local" or "cloud"), None for all

        Returns:
            List of matching voices
        """
        query = query.lower()
        results = []

        # Get voices to search
        if voice_type == "local":
            voices = self.get_local_voices()
        elif voice_type == "cloud":
            voices = self.get_cloud_voices()
        else:
            all_voices = self.get_all_voices()
            voices = all_voices["local"] + all_voices["cloud"]

        # Search
        for voice in voices:
            if (query in voice["name"].lower() or
                query in voice["locale"].lower() or
                query in voice.get("description", "").lower()):
                results.append(voice)

        return results

    def _load_cached_voices(self, voice_type: str) -> Optional[List[Dict[str, str]]]:
        """
        Load cached voices if available and not expired.

        Args:
            voice_type: "local" or "cloud"

        Returns:
            List of voices or None if cache invalid/expired
        """
        try:
            if not self.cache_file.exists():
                return None

            with open(self.cache_file, "r") as f:
                cache_data = json.load(f)

            # Check if cache has this type
            if voice_type not in cache_data:
                return None

            entry = cache_data[voice_type]

            # Check expiration
            cached_time = datetime.fromisoformat(entry["timestamp"])
            if datetime.now() - cached_time > self.cache_ttl:
                logger.debug(f"{voice_type} voice cache expired")
                return None

            logger.debug(f"Using cached {voice_type} voices")
            return entry["voices"]

        except Exception as e:
            logger.warning(f"Error loading voice cache: {e}")
            return None

    def _save_cached_voices(self, voice_type: str, voices: List[Dict[str, str]]) -> None:
        """
        Save voices to cache.

        Args:
            voice_type: "local" or "cloud"
            voices: List of voices to cache
        """
        try:
            # Load existing cache
            cache_data = {}
            if self.cache_file.exists():
                with open(self.cache_file, "r") as f:
                    cache_data = json.load(f)

            # Update with new data
            cache_data[voice_type] = {
                "timestamp": datetime.now().isoformat(),
                "voices": voices
            }

            # Save atomically
            temp_file = self.cache_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            temp_file.replace(self.cache_file)

            logger.debug(f"Cached {len(voices)} {voice_type} voices")

        except Exception as e:
            logger.error(f"Error saving voice cache: {e}")
