#!/usr/bin/env python3
"""
OpenClaw Mouth Status Monitor

Monitors mouth_status.txt to detect when the agent is speaking,
enabling echo prevention by pausing the microphone during TTS output.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


class MouthStatusMonitor:
    """
    Monitors OpenClaw Mouth status file to detect when agent is speaking.

    This enables echo prevention by providing a flag that the voice pipeline
    can check before processing audio input.
    """

    def __init__(
        self,
        status_file_path: Optional[str] = None,
        poll_interval: float = 0.05,  # Fast polling for responsive echo prevention
        cooldown_seconds: float = 1.0  # Stay quiet for 1s after TTS ends
    ):
        """
        Initialize the mouth status monitor.

        Args:
            status_file_path: Path to mouth_status.txt (default: runtime/mouth_status.txt)
            poll_interval: How often to poll the status file in seconds
            cooldown_seconds: How long to stay quiet after TTS ends (prevents echo)
        """
        self.status_file = Path(status_file_path) if status_file_path else \
            settings.RUNTIME_DIR / "mouth_status.txt"
        self.poll_interval = poll_interval
        self.cooldown_seconds = cooldown_seconds

        self._is_speaking = False
        self._last_speaking_time = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Ensure status file directory exists
        self.status_file.parent.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Start monitoring the status file."""
        if self._running:
            logger.warning("Monitor already running")
            return

        # Always start - don't require file to exist first
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"Mouth status monitor started (cooldown: {self.cooldown_seconds}s)")

    def stop(self) -> None:
        """Stop monitoring the status file."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("OpenClaw Mouth monitor stopped")

    def is_available(self) -> bool:
        """Check if the mouth status file exists."""
        return self.status_file.exists()

    def is_agent_speaking(self) -> bool:
        """
        Check if the agent is currently speaking OR recently finished.

        Returns:
            True if agent is speaking or in cooldown (microphone should be paused)
            False if agent is idle and cooldown expired (microphone can listen)
        """
        with self._lock:
            # Currently speaking
            if self._is_speaking:
                return True

            # In cooldown period after speaking ended
            if self._last_speaking_time is not None:
                time_since_speaking = time.time() - self._last_speaking_time
                if time_since_speaking < self.cooldown_seconds:
                    return True  # Still in cooldown - don't listen yet

            return False

    def _poll_loop(self) -> None:
        """Polling thread that monitors the status file."""
        while self._running:
            try:
                is_speaking = self._check_status()

                with self._lock:
                    if is_speaking:
                        self._is_speaking = True
                        self._last_speaking_time = time.time()
                    else:
                        if self._is_speaking:
                            # Just transitioned from speaking to idle - start cooldown
                            self._last_speaking_time = time.time()
                            logger.debug(f"TTS ended, starting {self.cooldown_seconds}s cooldown")
                        self._is_speaking = False

            except Exception as e:
                logger.debug(f"Error monitoring mouth status: {e}")

            time.sleep(self.poll_interval)

    def _check_status(self) -> bool:
        """
        Read and parse the status file.

        Returns:
            True if status is SPEAKING or QUEUED, False otherwise
        """
        try:
            if not self.status_file.exists():
                return False

            content = self.status_file.read_text().strip()
            if not content:
                return False

            # Parse format: timestamp|status|details
            parts = content.split('|')
            if len(parts) < 2:
                return False

            status = parts[1].upper()

            # Consider both SPEAKING and QUEUED as "agent is speaking"
            # to prevent cutting off the beginning of speech
            return status in ('SPEAKING', 'QUEUED')

        except Exception as e:
            logger.debug(f"Failed to read mouth status: {e}")
            return False  # Fail safe: assume not speaking
