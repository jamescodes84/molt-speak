#!/usr/bin/env python3
"""
Ears Status Notifier

Writes status to runtime/ears_status.txt so mouth can detect
when user is speaking and implement barge-in (stop TTS).
"""

import logging
import time
from pathlib import Path
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


class EarsStatusNotifier:
    """
    Notifies other systems when ears detects speech.

    Writes to runtime/ears_status.txt with format:
    timestamp|status|amplitude

    Status values:
    - LISTENING: Waiting for speech
    - SPEECH_DETECTED: User is speaking (mouth should stop)
    - PAUSED: Ears is paused (mouth is speaking)
    """

    def __init__(self, status_file_path: Optional[str] = None):
        """
        Initialize the ears status notifier.

        Args:
            status_file_path: Path to ears_status.txt (default: runtime/ears_status.txt)
        """
        self.status_file = Path(status_file_path) if status_file_path else \
            settings.RUNTIME_DIR / "ears_status.txt"

        # Ensure directory exists
        self.status_file.parent.mkdir(parents=True, exist_ok=True)

        self._last_status = None

        # Create status file immediately so mouth can monitor it
        self.notify_listening()

    def notify_listening(self) -> None:
        """Notify that ears is listening (waiting for speech)."""
        self._write_status("LISTENING", 0)

    def notify_speech_detected(self, amplitude: float = 0) -> None:
        """
        Notify that speech is detected (user is speaking).

        This signals mouth to stop TTS playback (barge-in).
        """
        self._write_status("SPEECH_DETECTED", amplitude)

    def notify_paused(self) -> None:
        """Notify that ears is paused (mouth is speaking)."""
        self._write_status("PAUSED", 0)

    def _write_status(self, status: str, amplitude: float) -> None:
        """Write status to file."""
        # Only write if status changed (reduce I/O)
        if status == self._last_status and status != "SPEECH_DETECTED":
            return

        try:
            timestamp = time.time()
            content = f"{timestamp}|{status}|{amplitude}"
            self.status_file.write_text(content)
            self._last_status = status
        except Exception as e:
            logger.debug(f"Failed to write ears status: {e}")

    def cleanup(self) -> None:
        """Clean up status file."""
        try:
            if self.status_file.exists():
                self.status_file.unlink()
        except Exception as e:
            logger.debug(f"Failed to cleanup ears status: {e}")
