"""Text-to-Speech service using Edge-TTS."""

import asyncio
import logging
import math
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Union

import edge_tts  # pylint: disable=import-error

logger = logging.getLogger(__name__)


class TTSService:
    """Text-to-Speech synthesis service using Edge-TTS."""

    def __init__(
        self,
        voice: str = "en-US-ChristopherNeural",
        rate: float = 1.0,
        volume: float = 1.0,
        pitch: float = 0.0
    ):
        """
        Initialize TTS service.

        Args:
            voice: Edge-TTS voice identifier
            rate: Speech rate multiplier (0.5 = half speed, 2.0 = double speed)
            volume: Volume multiplier (0.0 to 1.0)
            pitch: Pitch adjustment in Hz (-100 to +100)
        """
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

        logger.info(f"TTS Service initialized with voice: {voice}")

    def _format_rate(self, rate: float) -> str:
        """
        Format rate for Edge-TTS.

        Args:
            rate: Rate multiplier

        Returns:
            Formatted rate string (e.g., '+50%', '-25%')
        """
        if math.isclose(rate, 1.0):
            return "+0%"

        percent = int((rate - 1.0) * 100)
        sign = "+" if percent >= 0 else ""
        return f"{sign}{percent}%"

    def _format_volume(self, volume: float) -> str:
        """
        Format volume for Edge-TTS.

        Args:
            volume: Volume multiplier (0.0 to 1.0)

        Returns:
            Formatted volume string (e.g., '+0%', '-50%')
        """
        percent = int((volume - 1.0) * 100)
        sign = "+" if percent >= 0 else ""
        return f"{sign}{percent}%"

    def _format_pitch(self, pitch: float) -> str:
        """
        Format pitch for Edge-TTS.

        Args:
            pitch: Pitch in Hz

        Returns:
            Formatted pitch string (e.g., '+0Hz', '-50Hz')
        """
        sign = "+" if pitch >= 0 else ""
        return f"{sign}{int(pitch)}Hz"

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
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self._format_rate(self.rate),
                volume=self._format_volume(self.volume),
                pitch=self._format_pitch(self.pitch)
            )

            await communicate.save(str(output_path))
            logger.debug(f"Synthesized to {output_path}")

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise

    async def synthesize_streaming(self, text: str, output_path: Union[Path, str]) -> None:
        """
        Synthesize text to an audio file using streaming for lower latency.

        This method streams audio chunks as they're generated, allowing
        playback to start sooner than waiting for complete synthesis.

        Args:
            text: Text to synthesize
            output_path: Path to save the audio file

        Raises:
            Exception: If synthesis fails
        """
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self._format_rate(self.rate),
                volume=self._format_volume(self.volume),
                pitch=self._format_pitch(self.pitch)
            )

            # Stream audio: write each chunk incrementally via executor
            loop = asyncio.get_running_loop()
            fd = await loop.run_in_executor(
                None, lambda: open(str(output_path), "wb")
            )
            try:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        await loop.run_in_executor(
                            None, fd.write, chunk["data"]
                        )
            finally:
                await loop.run_in_executor(None, fd.close)

            logger.debug(f"Streamed synthesis to {output_path}")

        except Exception as e:
            logger.error(f"Streaming TTS synthesis failed: {e}")
            raise

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
            # Use a temporary file to collect audio data (in executor to avoid blocking)
            loop = asyncio.get_running_loop()

            def _make_temp():
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                    return tmp_file.name

            tmp_path = Path(await loop.run_in_executor(None, _make_temp))

            try:
                await self.synthesize_to_file(text, tmp_path)

                # Read the file back as bytes
                def _read_file():
                    with open(tmp_path, "rb") as f:
                        return f.read()

                audio_data = await loop.run_in_executor(None, _read_file)

                return audio_data

            finally:
                # Clean up temp file
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            logger.error(f"TTS synthesis to bytes failed: {e}")
            raise

    async def test_voice(self) -> bool:
        """
        Test if the configured voice works.

        Returns:
            True if voice is available, False otherwise
        """
        try:
            test_text = "Hello, this is a test."
            loop = asyncio.get_running_loop()

            def _make_temp():
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                    return tmp_file.name

            tmp_path = Path(await loop.run_in_executor(None, _make_temp))

            try:
                await self.synthesize_to_file(test_text, tmp_path)
                return True
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            logger.error(f"Voice test failed: {e}")
            return False

    async def stream_audio_chunks(self, text: str):
        """Yield MP3 audio chunks as they arrive from Edge-TTS (no file I/O)."""
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self._format_rate(self.rate),
            volume=self._format_volume(self.volume),
            pitch=self._format_pitch(self.pitch)
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    @staticmethod
    async def list_voices() -> List[Dict[str, Any]]:
        """
        List all available Edge-TTS voices.

        Returns:
            List of voice dictionaries with name, gender, locale info
        """
        try:
            voices = await edge_tts.list_voices()
            return voices
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
