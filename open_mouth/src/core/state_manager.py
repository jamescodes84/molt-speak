"""State management for the speech system."""

import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class SpeechState:
    """Current state of the speech system."""

    status: str = "IDLE"  # IDLE, QUEUED, SPEAKING, ERROR
    current_text: str = ""
    queue_size: int = 0
    total_spoken: int = 0
    voice: str = "en-US-ChristopherNeural"
    progress: float = 0.0  # 0.0 to 1.0
    error_message: str = ""
    queued_items: list = field(default_factory=list)  # Preview of queued text items

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary.

        Returns:
            State as dictionary
        """
        return {
            "status": self.status,
            "current_text": self.current_text,
            "queue_size": self.queue_size,
            "total_spoken": self.total_spoken,
            "voice": self.voice,
            "progress": self.progress,
            "error_message": self.error_message,
            "queued_items": self.queued_items,
        }


class StateManager:
    """Thread-safe state manager for the speech system."""

    def __init__(self, voice: str = "en-US-ChristopherNeural"):
        """
        Initialize state manager.

        Args:
            voice: Initial voice setting
        """
        self._state = SpeechState(voice=voice)
        self._lock = Lock()
        logger.debug("State manager initialized")

    def get_state(self) -> SpeechState:
        """
        Get current state (thread-safe).

        Returns:
            Current speech state
        """
        with self._lock:
            # Return a copy to prevent external modification
            return SpeechState(
                status=self._state.status,
                current_text=self._state.current_text,
                queue_size=self._state.queue_size,
                total_spoken=self._state.total_spoken,
                voice=self._state.voice,
                progress=self._state.progress,
                error_message=self._state.error_message,
                queued_items=self._state.queued_items.copy(),
            )

    def set_idle(self) -> None:
        """Set state to IDLE."""
        with self._lock:
            self._state.status = "IDLE"
            self._state.current_text = ""
            self._state.progress = 0.0
            self._state.error_message = ""

    def set_queued(self, queue_size: int) -> None:
        """
        Set state to QUEUED.

        Args:
            queue_size: Number of items in queue
        """
        with self._lock:
            self._state.status = "QUEUED"
            self._state.queue_size = queue_size

    def set_speaking(self, text: str, progress: float = 0.0) -> None:
        """
        Set state to SPEAKING.

        Args:
            text: Text being spoken
            progress: Progress (0.0 to 1.0)
        """
        with self._lock:
            self._state.status = "SPEAKING"
            self._state.current_text = text
            self._state.progress = progress

    def update_progress(self, progress: float) -> None:
        """
        Update speaking progress.

        Args:
            progress: Progress (0.0 to 1.0)
        """
        with self._lock:
            self._state.progress = min(1.0, max(0.0, progress))

    def increment_spoken(self) -> None:
        """Increment the count of spoken utterances."""
        with self._lock:
            self._state.total_spoken += 1

    def update_queue_size(self, size: int) -> None:
        """
        Update queue size.

        Args:
            size: Current queue size
        """
        with self._lock:
            self._state.queue_size = size

    def set_error(self, error_message: str) -> None:
        """
        Set error state.

        Args:
            error_message: Error message
        """
        with self._lock:
            self._state.status = "ERROR"
            self._state.error_message = error_message
            logger.error(f"State error: {error_message}")

    def get_status(self) -> str:
        """
        Get current status.

        Returns:
            Current status string
        """
        with self._lock:
            return self._state.status

    def get_current_text(self) -> str:
        """
        Get current text being spoken.

        Returns:
            Current text
        """
        with self._lock:
            return self._state.current_text

    def get_queue_size(self) -> int:
        """
        Get current queue size.

        Returns:
            Queue size
        """
        with self._lock:
            return self._state.queue_size

    def get_total_spoken(self) -> int:
        """
        Get total number of utterances spoken.

        Returns:
            Total spoken count
        """
        with self._lock:
            return self._state.total_spoken

    def update_queued_items(self, items: list) -> None:
        """
        Update the preview of queued items.

        Args:
            items: List of text items currently in queue (up to 3 items)
        """
        with self._lock:
            self._state.queued_items = items[:3]  # Keep only first 3 items

    def set_voice(self, voice: str) -> None:
        """
        Set the current voice.

        Args:
            voice: Voice identifier
        """
        with self._lock:
            self._state.voice = voice
            logger.info(f"Voice updated to: {voice}")

    def get_voice(self) -> str:
        """
        Get the current voice.

        Returns:
            Current voice identifier
        """
        with self._lock:
            return self._state.voice
