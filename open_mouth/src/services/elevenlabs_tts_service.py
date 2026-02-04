"""Text-to-Speech service using ElevenLabs API."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional, Union

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

logger = logging.getLogger(__name__)


class ElevenLabsTTSService:
    """Text-to-Speech synthesis service using ElevenLabs API."""

    def __init__(
        self,
        api_key: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel (default)
        model: str = "eleven_turbo_v2_5",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True
    ):
        """
        Initialize ElevenLabs TTS service.

        Args:
            api_key: ElevenLabs API key
            voice_id: ElevenLabs voice ID
            model: Model to use (eleven_turbo_v2_5 for low latency, eleven_multilingual_v2 for quality)
            stability: Voice stability (0.0-1.0)
            similarity_boost: Voice similarity boost (0.0-1.0)
            style: Style exaggeration (0.0-1.0)
            use_speaker_boost: Enable speaker boost for clarity
        """
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model

        # Initialize ElevenLabs client
        self.client = ElevenLabs(api_key=api_key)

        # Voice settings
        self.voice_settings = VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=use_speaker_boost
        )

        logger.info(f"ElevenLabs TTS Service initialized with voice: {voice_id}, model: {model}")

    async def synthesize_to_file(self, text: str, output_path: Union[Path, str]) -> None:
        """
        Synthesize text to an audio file.

        Args:
            text: Text to synthesize
            output_path: Path to save the audio file

        Raises:
            Exception: If synthesis fails
        """
        try:
            # Run the synchronous API call in a thread pool
            loop = asyncio.get_event_loop()
            audio_generator = await loop.run_in_executor(
                None,
                lambda: self.client.text_to_speech.convert(
                    text=text,
                    voice_id=self.voice_id,
                    model_id=self.model,
                    voice_settings=self.voice_settings
                )
            )

            # Write audio to file
            with open(str(output_path), "wb") as audio_file:
                for chunk in audio_generator:
                    if chunk:
                        audio_file.write(chunk)

            logger.debug(f"Synthesized to {output_path}")

        except Exception as e:
            logger.error(f"ElevenLabs TTS synthesis failed: {e}")
            raise

    async def synthesize_streaming(self, text: str, output_path: Union[Path, str]) -> None:
        """
        Synthesize text to an audio file using streaming.

        ElevenLabs API returns a generator by default, so this is essentially
        the same as synthesize_to_file but provided for interface compatibility.

        Args:
            text: Text to synthesize
            output_path: Path to save the audio file

        Raises:
            Exception: If synthesis fails
        """
        # ElevenLabs already streams by default
        await self.synthesize_to_file(text, output_path)

    async def synthesize_to_bytes(self, text: str) -> bytes:
        """
        Synthesize text to audio bytes.

        Args:
            text: Text to synthesize

        Returns:
            Audio data as bytes

        Raises:
            Exception: If synthesis fails
        """
        try:
            # Use a temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            try:
                await self.synthesize_to_file(text, tmp_path)

                # Read the file back as bytes
                with open(tmp_path, "rb") as f:
                    audio_data = f.read()

                return audio_data

            finally:
                # Clean up temp file
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            logger.error(f"ElevenLabs TTS synthesis to bytes failed: {e}")
            raise

    async def test_voice(self) -> bool:
        """
        Test if the configured voice and API key work.

        Returns:
            True if voice is available, False otherwise
        """
        try:
            test_text = "Hello, this is a test."
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            try:
                await self.synthesize_to_file(test_text, tmp_path)
                return True
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            logger.error(f"ElevenLabs voice test failed: {e}")
            return False

    async def list_voices(self) -> list:
        """
        List all available ElevenLabs voices for this account.

        Returns:
            List of voice objects with name, voice_id, etc.
        """
        try:
            loop = asyncio.get_event_loop()
            voices_response = await loop.run_in_executor(
                None,
                lambda: self.client.voices.get_all()
            )
            return voices_response.voices
        except Exception as e:
            logger.error(f"Failed to list ElevenLabs voices: {e}")
            return []
