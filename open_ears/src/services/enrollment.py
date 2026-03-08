"""Enrollment session manager for Crowd Control.

Handles the recording and validation of voice enrollment phrases.
Can be driven by the CLI script or by the menu bar UI.
"""
from __future__ import annotations

import logging
import time

import numpy as np

logger = logging.getLogger("open_ears.enrollment")

# Enrollment prompts — diverse phonemes, natural length, mix of intonations
ENROLLMENT_PROMPTS = [
    "The quick brown fox jumps over the lazy dog",
    "How is the weather looking today",
    "I need to set a reminder for tomorrow morning",
    "What's the latest news about technology",
    "Tell me something interesting about science",
]

# Recording parameters
SAMPLE_RATE = 16000
RECORD_DURATION = 4.0  # seconds per phrase
MIN_AMPLITUDE = 200  # minimum RMS amplitude to accept a recording


class EnrollmentSession:
    """Manages a voice enrollment session."""

    def __init__(self, speaker_gate, num_phrases: int = 5):
        self.speaker_gate = speaker_gate
        self.num_phrases = min(num_phrases, len(ENROLLMENT_PROMPTS))
        self.recordings: list[np.ndarray] = []
        self.prompts = ENROLLMENT_PROMPTS[:self.num_phrases]

    def record_phrase(self, duration: float = RECORD_DURATION,
                      device: int | None = None) -> np.ndarray | None:
        """Record a single phrase from the microphone.

        Args:
            duration: Recording duration in seconds.
            device: Audio device index (None = default).

        Returns:
            Recorded audio as numpy array, or None if recording failed.
        """
        try:
            import sounddevice as sd
            audio = sd.rec(
                int(duration * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='float32',
                device=device,
            )
            sd.wait()
            audio = audio.flatten()

            # Validate: check that there's actual speech (not silence)
            rms = np.sqrt(np.mean(audio ** 2)) * 10000
            if rms < MIN_AMPLITUDE:
                logger.warning("Recording too quiet (RMS: %.1f). Please speak louder.", rms)
                return None

            return audio

        except Exception as e:
            logger.error("Recording failed: %s", e)
            return None

    def validate_recording(self, audio: np.ndarray) -> bool:
        """Basic quality check on a recorded phrase."""
        if audio is None:
            return False
        duration = len(audio) / SAMPLE_RATE
        if duration < 1.0:
            logger.warning("Recording too short (%.1fs)", duration)
            return False
        rms = np.sqrt(np.mean(audio ** 2)) * 10000
        if rms < MIN_AMPLITUDE:
            logger.warning("Recording too quiet (RMS: %.1f)", rms)
            return False
        return True

    def add_recording(self, audio: np.ndarray) -> bool:
        """Add a validated recording to the session.

        Returns True if the recording was accepted.
        """
        if not self.validate_recording(audio):
            return False
        self.recordings.append(audio)
        return True

    @property
    def is_complete(self) -> bool:
        """Whether enough phrases have been recorded."""
        return len(self.recordings) >= self.num_phrases

    @property
    def phrases_remaining(self) -> int:
        return max(0, self.num_phrases - len(self.recordings))

    def finalize(self) -> bool:
        """Finalize enrollment by passing recordings to the speaker gate.

        Returns True if enrollment succeeded.
        """
        if not self.is_complete:
            logger.error("Not enough recordings (%d/%d)",
                         len(self.recordings), self.num_phrases)
            return False

        return self.speaker_gate.enroll(self.recordings)

    def reset(self):
        """Reset the session for a fresh enrollment."""
        self.recordings = []
