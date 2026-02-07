#!/usr/bin/env python3
"""
Ears Status Monitor

Monitors runtime/ears_status.txt to detect when user is speaking,
enabling barge-in (stopping TTS playback when user interrupts).
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


class EarsStatusMonitor:
    """
    Monitors OpenClaw Ears status file to detect when user is speaking.

    This enables barge-in by providing a flag that the playback loop
    can check to stop audio when the user starts talking.
    """

    def __init__(
        self,
        status_file_path: Optional[str] = None,
        poll_interval: float = 0.05,  # Fast polling for responsive barge-in
        speech_timeout: float = 0.3   # How long after speech to still consider "speaking"
    ):
        """
        Initialize the ears status monitor.

        Args:
            status_file_path: Path to ears_status.txt (default: runtime/ears_status.txt)
            poll_interval: How often to poll the status file in seconds
            speech_timeout: Seconds to wait after last speech detection before clearing
        """
        self.status_file = Path(status_file_path) if status_file_path else \
            settings.RUNTIME_DIR / "ears_status.txt"
        self.poll_interval = poll_interval
        self.speech_timeout = speech_timeout

        self._user_speaking = False
        self._last_speech_time = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start monitoring the ears status file."""
        if self._running:
            logger.warning("Ears monitor already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Ears status monitor started (barge-in enabled)")

    def stop(self) -> None:
        """Stop monitoring."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("Ears status monitor stopped")

    def is_user_speaking(self) -> bool:
        """
        Check if the user is currently speaking.

        Returns:
            True if user is speaking (playback should stop)
            False if user is silent (playback can continue)
        """
        with self._lock:
            # Check if we recently detected speech
            if self._user_speaking:
                return True

            # Apply timeout - keep returning True briefly after speech ends
            if self._last_speech_time > 0:
                time_since_speech = time.time() - self._last_speech_time
                if time_since_speech < self.speech_timeout:
                    return True

            return False

    def _poll_loop(self) -> None:
        """Polling thread that monitors the ears status file."""
        while self._running:
            try:
                is_speaking = self._check_status()

                with self._lock:
                    if is_speaking:
                        self._user_speaking = True
                        self._last_speech_time = time.time()
                    else:
                        self._user_speaking = False

            except Exception as e:
                logger.debug(f"Error monitoring ears status: {e}")

            time.sleep(self.poll_interval)

    def _check_status(self) -> bool:
        """
        Read and parse the ears status file.

        Returns:
            True if status is SPEECH_DETECTED, False otherwise
        """
        try:
            if not self.status_file.exists():
                return False

            content = self.status_file.read_text().strip()
            if not content:
                return False

            # Parse format: timestamp|status|amplitude
            parts = content.split('|')
            if len(parts) < 2:
                return False

            timestamp = float(parts[0])
            status = parts[1].upper()

            # Only consider recent speech detections (within last 500ms)
            age = time.time() - timestamp
            if age > 0.5:
                return False

            return status == "SPEECH_DETECTED"

        except Exception as e:
            logger.debug(f"Failed to read ears status: {e}")
            return False
