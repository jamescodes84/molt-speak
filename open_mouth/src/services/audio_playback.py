"""Audio playback service for playing synthesized speech."""

import logging
import subprocess
import tempfile
from pathlib import Path
from threading import Event
from typing import Union

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Audio playback service using system audio player with barge-in support."""

    def __init__(self):
        """Initialize the audio player."""
        self.is_playing = Event()
        self._process = None
        self._interrupted = False
        logger.info("Audio player initialized (barge-in capable)")

    def play_file(self, audio_path: Union[Path, str], interrupt_check=None) -> bool:
        """
        Play an audio file using system audio player.

        Args:
            audio_path: Path to the audio file to play
            interrupt_check: Optional callable that returns True to interrupt playback

        Returns:
            True if playback was successful, False if failed or interrupted
        """
        try:
            self.is_playing.set()
            self._interrupted = False
            audio_path = Path(audio_path)

            if not audio_path.exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False

            # Use Popen for interruptible playback
            self._process = subprocess.Popen(
                ["afplay", str(audio_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Poll for completion or interruption
            while self._process.poll() is None:
                # Check if we should interrupt (barge-in)
                if interrupt_check and interrupt_check():
                    logger.info("Barge-in detected - stopping playback")
                    self.stop()
                    self._interrupted = True
                    return False

                # Small sleep to avoid busy-waiting
                import time
                time.sleep(0.05)

            if self._process.returncode != 0 and not self._interrupted:
                stderr = self._process.stderr.read().decode() if self._process.stderr else ""
                logger.error(f"Audio playback failed: {stderr}")
                return False

            logger.debug(f"Successfully played {audio_path}")
            return True

        except FileNotFoundError:
            logger.error("afplay not found - macOS audio player not available")
            return False

        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            return False

        finally:
            self.is_playing.clear()
            self._process = None

    def play_bytes(self, audio_data: bytes) -> bool:
        """
        Play audio from bytes.

        Args:
            audio_data: Audio data as bytes

        Returns:
            True if playback was successful, False otherwise
        """
        try:
            # Write bytes to temporary file and play
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(audio_data)

            try:
                return self.play_file(tmp_path)
            finally:
                # Clean up temp file after playback
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            logger.error(f"Failed to play audio from bytes: {e}")
            return False

    def stop(self) -> None:
        """Stop current playback immediately (barge-in)."""
        try:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                self._process.wait(timeout=0.5)
                self._interrupted = True
                self.is_playing.clear()
                logger.info("Playback stopped (barge-in)")
        except Exception as e:
            logger.error(f"Failed to stop playback: {e}")
            # Force kill if terminate didn't work
            try:
                if self._process:
                    self._process.kill()
            except:
                pass

    def is_busy(self) -> bool:
        """
        Check if audio is currently playing.

        Returns:
            True if audio is playing, False otherwise
        """
        return self.is_playing.is_set()


class AudioPlayerAdvanced:
    """
    Advanced audio player using sounddevice (optional).

    This provides more control over playback but requires additional dependencies.
    Use this if you need features like interruption or real-time control.
    """

    def __init__(self, sample_rate: int = 24000):
        """
        Initialize advanced audio player.

        Args:
            sample_rate: Audio sample rate
        """
        try:
            import sounddevice as sd
            import soundfile as sf

            self.sd = sd
            self.sf = sf
            self.sample_rate = sample_rate
            self.is_playing = Event()
            logger.info("Advanced audio player initialized")

        except ImportError:
            logger.warning(
                "sounddevice or soundfile not available. "
                "Install with: pip install sounddevice soundfile"
            )
            raise

    def play_file(self, audio_path: Union[Path, str]) -> bool:
        """
        Play an audio file.

        Args:
            audio_path: Path to the audio file

        Returns:
            True if playback was successful, False otherwise
        """
        try:
            self.is_playing.set()
            audio_path = Path(audio_path)

            if not audio_path.exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False

            # Read audio file
            data, samplerate = self.sf.read(audio_path)

            # Play audio (blocking)
            self.sd.play(data, samplerate)
            self.sd.wait()  # Wait until playback is finished

            logger.debug(f"Successfully played {audio_path}")
            return True

        except Exception as e:
            logger.error(f"Advanced audio playback error: {e}")
            return False

        finally:
            self.is_playing.clear()

    def stop(self) -> None:
        """Stop current playback immediately."""
        try:
            self.sd.stop()
            self.is_playing.clear()
            logger.debug("Playback stopped")
        except Exception as e:
            logger.error(f"Failed to stop playback: {e}")

    def is_busy(self) -> bool:
        """
        Check if audio is currently playing.

        Returns:
            True if audio is playing, False otherwise
        """
        return self.is_playing.is_set()
