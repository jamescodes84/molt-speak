"""Speaker Gate: Owner voice verification for crowd control.

Uses Resemblyzer (GE2E d-vectors) to verify whether detected speech
belongs to the enrolled owner. Lazy-loads the encoder on first use.

This is an opt-in feature — only active when the user enables
"Crowd Control" from the menu bar AND has an enrolled voice profile.
"""

import logging
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger("open_ears.speaker_gate")

# Minimum audio duration (seconds) needed for a reliable embedding
MIN_VERIFICATION_AUDIO = 0.5

# Default cosine similarity threshold for accepting speech as the owner
DEFAULT_THRESHOLD = 0.65


class SpeakerGate:
    """Verifies whether detected speech belongs to the enrolled owner."""

    def __init__(self, profile_path: Path, threshold: float = DEFAULT_THRESHOLD,
                 sample_rate: int = 16000):
        self._profile_path = profile_path
        self._threshold = threshold
        self._sample_rate = sample_rate

        # Lazy-loaded
        self._encoder = None
        self._voiceprint = None
        self._loaded = False

        # Verification buffer — accumulates frames until we have enough audio
        self._verification_buffer: list[np.ndarray] = []
        self._verification_decided = False

        # Load voiceprint from disk if it exists (cheap — just a numpy load)
        if self._profile_path.exists():
            try:
                self._voiceprint = np.load(str(self._profile_path))
                logger.info("Speaker profile loaded from %s", self._profile_path)
            except Exception as e:
                logger.warning("Failed to load speaker profile: %s", e)
                self._voiceprint = None

    @property
    def is_enrolled(self) -> bool:
        """Whether a voice profile exists."""
        return self._voiceprint is not None

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        self._threshold = max(0.0, min(1.0, value))

    def _load_encoder(self):
        """Lazy-load the Resemblyzer encoder. ~200ms on first call."""
        if self._encoder is not None:
            return True
        try:
            from resemblyzer import VoiceEncoder
            start = time.time()
            self._encoder = VoiceEncoder()
            elapsed = time.time() - start
            logger.info("Resemblyzer encoder loaded in %.1fms", elapsed * 1000)
            return True
        except ImportError:
            logger.error("resemblyzer not installed. Run: pip install resemblyzer")
            return False
        except Exception as e:
            logger.error("Failed to load Resemblyzer encoder: %s", e)
            return False

    def verify(self, audio_data: np.ndarray) -> tuple[bool, float]:
        """Check if audio belongs to the enrolled owner.

        Accumulates audio frames internally until enough data is available
        for a reliable embedding (~500ms). Returns (True, 1.0) while still
        accumulating (benefit of the doubt).

        Args:
            audio_data: Raw audio as numpy array (16kHz, mono).

        Returns:
            (is_owner, similarity_score) tuple.
        """
        if not self.is_enrolled:
            return True, 1.0

        # If we already decided for this utterance, return cached result
        if self._verification_decided:
            return self._last_result

        # Accumulate audio
        self._verification_buffer.append(audio_data)
        total_audio = np.concatenate(self._verification_buffer)
        duration = len(total_audio) / self._sample_rate

        if duration < MIN_VERIFICATION_AUDIO:
            # Not enough audio yet — let it through
            return True, 1.0

        # We have enough audio — make the decision
        if not self._load_encoder():
            return True, 1.0  # Encoder failed — don't block speech

        try:
            audio_float = total_audio.astype(np.float32)
            # Normalize to [-1, 1] if needed
            max_val = np.max(np.abs(audio_float))
            if max_val > 1.0:
                audio_float = audio_float / max_val

            embedding = self._encoder.embed_utterance(audio_float)
            similarity = float(np.dot(embedding, self._voiceprint) / (
                np.linalg.norm(embedding) * np.linalg.norm(self._voiceprint)
            ))

            is_owner = similarity >= self._threshold
            self._last_result = (is_owner, similarity)
            self._verification_decided = True

            if is_owner:
                logger.debug("Speaker verified (similarity: %.2f)", similarity)
            else:
                logger.debug("Speaker rejected (similarity: %.2f)", similarity)

            return is_owner, similarity

        except Exception as e:
            logger.warning("Speaker verification error: %s", e)
            return True, 1.0  # Don't block on errors

    def reset(self):
        """Reset verification state for a new utterance."""
        self._verification_buffer = []
        self._verification_decided = False
        self._last_result = (True, 1.0)

    def enroll(self, audio_segments: list[np.ndarray]) -> bool:
        """Enroll the owner from multiple audio segments.

        Args:
            audio_segments: List of numpy arrays, each a spoken phrase
                           (16kHz, mono, float32 or int16).

        Returns:
            True if enrollment succeeded.
        """
        if not self._load_encoder():
            return False

        embeddings = []
        for i, audio in enumerate(audio_segments):
            audio_float = audio.astype(np.float32)
            max_val = np.max(np.abs(audio_float))
            if max_val > 1.0:
                audio_float = audio_float / max_val

            embedding = self._encoder.embed_utterance(audio_float)
            embeddings.append(embedding)
            logger.info("Enrolled phrase %d/%d", i + 1, len(audio_segments))

        # Average all embeddings to create the voiceprint
        self._voiceprint = np.mean(embeddings, axis=0)

        # Normalize the voiceprint
        norm = np.linalg.norm(self._voiceprint)
        if norm > 0:
            self._voiceprint = self._voiceprint / norm

        # Save to disk
        self._profile_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(self._profile_path), self._voiceprint)
        logger.info("Voice profile saved to %s (%d phrases averaged)",
                     self._profile_path, len(embeddings))
        return True

    def clear_profile(self):
        """Delete the enrolled voice profile."""
        self._voiceprint = None
        self._verification_buffer = []
        self._verification_decided = False
        if self._profile_path.exists():
            self._profile_path.unlink()
            logger.info("Voice profile deleted")
