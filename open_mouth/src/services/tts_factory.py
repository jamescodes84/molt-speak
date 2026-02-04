"""Factory for creating TTS service instances based on provider."""

import logging
from typing import Union

from .tts_service import TTSService
from .elevenlabs_tts_service import ElevenLabsTTSService

logger = logging.getLogger(__name__)


class TTSFactory:
    """Factory for creating TTS service instances."""

    @staticmethod
    def create_tts_service(
        provider: str = "edge-tts",
        voice: str = None,
        api_key: str = None,
        **kwargs
    ) -> Union[TTSService, ElevenLabsTTSService]:
        """
        Create a TTS service instance based on the provider.

        Args:
            provider: TTS provider ("edge-tts" or "elevenlabs")
            voice: Voice identifier (provider-specific)
            api_key: API key (required for elevenlabs)
            **kwargs: Additional provider-specific arguments

        Returns:
            TTS service instance

        Raises:
            ValueError: If provider is invalid or required parameters are missing
        """
        provider = provider.lower()

        if provider == "edge-tts":
            logger.info("Creating Edge-TTS service")
            return TTSFactory._create_edge_tts_service(voice, **kwargs)

        elif provider == "elevenlabs":
            logger.info("Creating ElevenLabs TTS service")
            return TTSFactory._create_elevenlabs_service(voice, api_key, **kwargs)

        else:
            raise ValueError(f"Unknown TTS provider: {provider}. Supported providers: edge-tts, elevenlabs")

    @staticmethod
    def _create_edge_tts_service(voice: str = None, **kwargs) -> TTSService:
        """
        Create an Edge-TTS service instance.

        Args:
            voice: Edge-TTS voice identifier
            **kwargs: Additional Edge-TTS parameters (rate, volume, pitch)

        Returns:
            TTSService instance
        """
        params = {
            "voice": voice or "en-US-ChristopherNeural",
            "rate": kwargs.get("rate", 1.0),
            "volume": kwargs.get("volume", 1.0),
            "pitch": kwargs.get("pitch", 0.0)
        }

        return TTSService(**params)

    @staticmethod
    def _create_elevenlabs_service(
        voice_id: str = None,
        api_key: str = None,
        **kwargs
    ) -> ElevenLabsTTSService:
        """
        Create an ElevenLabs TTS service instance.

        Args:
            voice_id: ElevenLabs voice ID
            api_key: ElevenLabs API key (required)
            **kwargs: Additional ElevenLabs parameters

        Returns:
            ElevenLabsTTSService instance

        Raises:
            ValueError: If API key is not provided
        """
        if not api_key:
            raise ValueError("ElevenLabs API key is required. Use 'molt-speak elo' to configure.")

        params = {
            "api_key": api_key,
            "voice_id": voice_id or "21m00Tcm4TlvDq8ikWAM",  # Rachel (default)
            "model": kwargs.get("model", "eleven_turbo_v2_5"),
            "stability": kwargs.get("stability", 0.5),
            "similarity_boost": kwargs.get("similarity_boost", 0.75),
            "style": kwargs.get("style", 0.0),
            "use_speaker_boost": kwargs.get("use_speaker_boost", True)
        }

        return ElevenLabsTTSService(**params)

    @staticmethod
    def get_default_voice(provider: str) -> str:
        """
        Get the default voice for a provider.

        Args:
            provider: TTS provider name

        Returns:
            Default voice identifier for that provider
        """
        defaults = {
            "edge-tts": "en-US-ChristopherNeural",
            "elevenlabs": "21m00Tcm4TlvDq8ikWAM"  # Rachel
        }

        return defaults.get(provider.lower(), defaults["edge-tts"])
