"""Audio playback service for playing synthesized speech."""

import collections
import logging
import subprocess
import tempfile
import threading
from pathlib import Path
from threading import Event
from typing import Union

import numpy as np
import sounddevice as sd

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
            except OSError:
                pass

    def is_busy(self) -> bool:
        """
        Check if audio is currently playing.

        Returns:
            True if audio is playing, False otherwise
        """
        return self.is_playing.is_set()


class StreamingAudioPlayer:
    """
    Streaming audio player using sounddevice OutputStream callback.

    Enables real-time playback of PCM data as it arrives (e.g. from ffmpeg decode).
    Zero subprocess overhead, instant barge-in via callback abort.
    """

    def __init__(self, sample_rate: int = 24000, channels: int = 1,
                 blocksize: int = 256, interrupt_check=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self._interrupt_check = interrupt_check  # Callable returning True to stop

        # Thread-safe PCM buffer (deque of bytes objects)
        self._buffer = collections.deque()
        self._buffer_lock = threading.Lock()
        self._partial = b""  # leftover bytes from previous callback

        # State flags
        self._finished = threading.Event()   # No more data will arrive
        self._interrupted = threading.Event()  # Barge-in requested
        self._done = threading.Event()       # Playback fully complete
        self._playing = threading.Event()

        self._stream = None
        self._interrupted_flag = False  # Public read-only after playback
        self._frames_played = 0  # Tracks actual audio output for barge-in accuracy

    def _callback(self, outdata, frames, time_info, status):
        """sounddevice OutputStream callback — runs in C audio thread."""
        if self._interrupted.is_set():
            outdata[:] = 0
            raise sd.CallbackAbort()

        # Inline barge-in check: polls is_user_speaking() every callback
        # cycle (~10ms at blocksize=256/24kHz) so barge-in triggers even
        # while the Python main loop is blocked on synthesis/decode.
        if self._interrupt_check is not None:
            try:
                if self._interrupt_check():
                    self._interrupted.set()
                    self._interrupted_flag = True
                    outdata[:] = 0
                    raise sd.CallbackAbort()
            except sd.CallbackAbort:
                raise
            except Exception:
                pass  # Don't let check errors kill audio

        # How many bytes we need: frames * channels * 2 (int16 = 2 bytes)
        needed = frames * self.channels * 2
        data = self._partial

        with self._buffer_lock:
            while len(data) < needed and self._buffer:
                data += self._buffer.popleft()

        if len(data) >= needed:
            self._partial = data[needed:]
            self._frames_played += frames
            outdata[:] = np.frombuffer(data[:needed], dtype=np.int16).reshape(frames, self.channels)
        elif data:
            # Partial fill — pad with silence
            self._partial = b""
            samples = np.frombuffer(data, dtype=np.int16)
            n = len(samples) // self.channels
            self._frames_played += n
            outdata[:n] = samples.reshape(n, self.channels)
            outdata[n:] = 0
            if self._finished.is_set():
                raise sd.CallbackStop()
        else:
            # Buffer empty
            outdata[:] = 0
            if self._finished.is_set():
                raise sd.CallbackStop()

    def _on_stream_finished(self):
        """Called by sounddevice when stream stops (CallbackStop or CallbackAbort)."""
        self._playing.clear()
        self._done.set()

    def start_stream(self):
        """Open and start the audio output stream."""
        self._finished.clear()
        self._interrupted.clear()
        self._done.clear()
        self._partial = b""
        self._interrupted_flag = False
        self._frames_played = 0

        with self._buffer_lock:
            self._buffer.clear()

        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.blocksize,
            callback=self._callback,
            finished_callback=self._on_stream_finished,
        )
        self._stream.start()
        self._playing.set()

    def feed(self, pcm_data: bytes):
        """Append raw PCM data to the playback buffer."""
        with self._buffer_lock:
            self._buffer.append(pcm_data)

    def mark_finished(self):
        """Signal that no more PCM data will arrive."""
        self._finished.set()

    def interrupt(self):
        """Instantly stop playback (barge-in). Callback will abort on next tick."""
        self._interrupted.set()
        self._interrupted_flag = True

    def wait_until_done(self, timeout: float = 60.0) -> bool:
        """Block until playback finishes or is interrupted. Returns True if completed normally."""
        self._done.wait(timeout=timeout)
        return not self._interrupted_flag

    def stop(self):
        """Close the stream and clean up."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._playing.clear()
        self._done.set()

    def is_busy(self) -> bool:
        return self._playing.is_set()

    @property
    def seconds_played(self) -> float:
        """Actual seconds of audio output by the sounddevice callback."""
        return self._frames_played / self.sample_rate


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
