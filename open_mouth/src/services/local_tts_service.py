"""Local TTS service using system speech for instant playback."""

import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional, Union

logger = logging.getLogger(__name__)


class LocalTTSService:
    """
    Local TTS synthesis service using macOS 'say' command.

    This provides near-instant speech with zero network latency,
    perfect for real-time agent responses. Supports barge-in.
    """

    def __init__(
        self,
        voice: str = "Alex",
        rate: int = 200,  # Words per minute
    ):
        """
        Initialize local TTS service.

        Args:
            voice: macOS voice name (e.g., "Alex", "Samantha", "Daniel")
            rate: Speech rate in words per minute (default: 200)
        """
        self.voice = voice
        self.rate = rate
        self._process = None
        self._interrupted = False

        logger.info(f"Local TTS Service initialized with voice: {voice}")

    def synthesize_to_file(self, text: str, output_path: Union[Path, str]) -> bool:
        """
        Synthesize text to an audio file using macOS 'say' command.

        Args:
            text: Text to synthesize
            output_path: Path to save the audio file

        Returns:
            True if synthesis succeeded, False otherwise
        """
        try:
            # Use 'say' command to generate audio file
            # -v voice, -r rate, -o output file
            result = subprocess.run(
                [
                    "say",
                    "-v", self.voice,
                    "-r", str(self.rate),
                    "-o", str(output_path),
                    text
                ],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                logger.error(f"Local TTS synthesis failed: {result.stderr}")
                return False

            logger.debug(f"Synthesized to {output_path}")
            return True

        except FileNotFoundError:
            logger.error("'say' command not found - macOS TTS not available")
            return False

        except Exception as e:
            logger.error(f"Local TTS synthesis failed: {e}")
            return False

    def synthesize_direct(
        self,
        text: str,
        interrupt_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Synthesize and speak text directly without creating a file.
        This is the FASTEST method - near-instant playback.
        Supports barge-in via interrupt_check callback.

        Args:
            text: Text to speak
            interrupt_check: Optional callable that returns True to interrupt

        Returns:
            True if synthesis succeeded, False if failed or interrupted
        """
        try:
            self._interrupted = False

            # Use Popen for interruptible playback
            self._process = subprocess.Popen(
                [
                    "say",
                    "-v", self.voice,
                    "-r", str(self.rate),
                    text
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Poll for completion or interruption
            while self._process.poll() is None:
                if interrupt_check and interrupt_check():
                    logger.info("Barge-in detected - stopping local TTS")
                    self.stop()
                    self._interrupted = True
                    return False
                time.sleep(0.05)

            if self._process.returncode != 0 and not self._interrupted:
                stderr = self._process.stderr.read().decode() if self._process.stderr else ""
                logger.error(f"Direct speech failed: {stderr}")
                return False

            return True

        except Exception as e:
            logger.error(f"Direct speech failed: {e}")
            return False

        finally:
            self._process = None

    def stop(self) -> None:
        """Stop current speech immediately (barge-in)."""
        try:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                self._process.wait(timeout=0.5)
                self._interrupted = True
                logger.info("Local TTS stopped (barge-in)")
        except Exception as e:
            logger.error(f"Failed to stop local TTS: {e}")
            try:
                if self._process:
                    self._process.kill()
            except:
                pass

    def test_voice(self) -> bool:
        """
        Test if the configured voice works.

        Returns:
            True if voice is available, False otherwise
        """
        try:
            test_text = "Hello, this is a test."
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=True) as tmp_file:
                tmp_path = Path(tmp_file.name)
                return self.synthesize_to_file(test_text, tmp_path)

        except Exception as e:
            logger.error(f"Voice test failed: {e}")
            return False

    @staticmethod
    def list_voices() -> list:
        """
        List all available macOS voices.

        Returns:
            List of voice names
        """
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                return []

            # Parse voice list
            voices = []
            for line in result.stdout.strip().split("\n"):
                # Format: "VoiceName    locale    # description"
                parts = line.split()
                if parts:
                    voices.append(parts[0])

            return voices

        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
