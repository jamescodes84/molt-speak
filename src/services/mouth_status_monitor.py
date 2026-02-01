"""
OpenClaw Mouth Status Monitor

Monitors the speaking status file written by OpenClaw Mouth to enable
echo prevention during TTS output. When the agent is speaking, this monitor
signals the voice pipeline to pause the microphone.

File: ~/.openclaw/mouth_status.txt
Format: timestamp|status|details

Status values:
- IDLE: Not speaking, safe to listen
- SPEAKING: Agent actively speaking - PAUSE MICROPHONE
- QUEUED: Speech queued but not yet playing
- ERROR: System error occurred

Author: OpenClaw Integration
Date: 2026-02-01
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class MouthStatusMonitor:
    """
    Monitors OpenClaw Mouth speaking status file to prevent echo/feedback.

    Uses polling to monitor the status file and provides callbacks when
    speaking state changes. Includes debouncing to prevent rapid state changes.

    Thread-safe and fault-tolerant - defaults to "not speaking" on errors.
    """

    def __init__(
        self,
        status_file: Path,
        poll_interval: float = 0.1,
        debounce_ms: int = 200,
        on_speaking_start: Optional[Callable[[], None]] = None,
        on_speaking_stop: Optional[Callable[[], None]] = None
    ):
        """
        Initialize the status monitor.

        Args:
            status_file: Path to mouth_status.txt
            poll_interval: Polling interval in seconds (default: 0.1 = 100ms)
            debounce_ms: Debounce time in milliseconds (default: 200ms)
            on_speaking_start: Callback when agent starts speaking
            on_speaking_stop: Callback when agent stops speaking
        """
        self.status_file = status_file
        self.poll_interval = poll_interval
        self.debounce_ms = debounce_ms

        # Callbacks
        self.on_speaking_start = on_speaking_start
        self.on_speaking_stop = on_speaking_stop

        # Thread management
        self._poll_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # State tracking
        self._is_speaking = False
        self._last_speaking_time = 0.0
        self._last_idle_time = 0.0
        self._file_available = False
        self._error_logged = False  # Prevent log spam

        # Check initial availability
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if the status file exists."""
        self._file_available = self.status_file.exists()
        if self._file_available:
            logger.info(f"OpenClaw Mouth status file found: {self.status_file}")
        else:
            logger.debug(f"OpenClaw Mouth status file not found: {self.status_file}")

    def is_available(self) -> bool:
        """
        Check if OpenClaw Mouth integration is available.

        Returns:
            True if status file exists, False otherwise
        """
        return self._file_available

    def start(self) -> None:
        """Start the monitoring thread."""
        if self._running:
            logger.warning("Monitor already running")
            return

        if not self.is_available():
            logger.info("OpenClaw Mouth not available, monitor not started")
            return

        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="MouthStatusMonitor",
            daemon=True
        )
        self._poll_thread.start()
        logger.info("OpenClaw Mouth monitor started")

    def stop(self) -> None:
        """Stop the monitoring thread."""
        if not self._running:
            return

        self._running = False

        if self._poll_thread:
            self._poll_thread.join(timeout=1.0)
            self._poll_thread = None

        logger.info("OpenClaw Mouth monitor stopped")

    def is_agent_speaking(self) -> bool:
        """
        Check if the agent is currently speaking.

        Returns:
            True if agent is speaking (microphone should be paused)
            False otherwise (safe to listen)
        """
        with self._lock:
            # Apply debouncing
            if self._is_speaking:
                return True

            # Check if we recently stopped speaking (within debounce window)
            now = time.time() * 1000
            time_since_speaking = now - self._last_speaking_time

            if time_since_speaking < self.debounce_ms:
                return True

            return False

    def _poll_loop(self) -> None:
        """
        Main polling loop (runs in dedicated thread).
        """
        while self._running:
            try:
                # Check if file still exists
                if not self.status_file.exists():
                    if self._file_available:
                        logger.info("OpenClaw Mouth status file removed, integration disabled")
                        self._file_available = False
                        with self._lock:
                            self._is_speaking = False
                    time.sleep(self.poll_interval)
                    continue

                # File exists - update availability
                if not self._file_available:
                    logger.info("OpenClaw Mouth status file detected, integration enabled")
                    self._file_available = True

                # Check current status
                is_speaking = self._check_status()

                # Update state with thread safety
                with self._lock:
                    now = time.time() * 1000

                    if is_speaking and not self._is_speaking:
                        # Transition: IDLE → SPEAKING
                        self._is_speaking = True
                        self._last_speaking_time = now
                        logger.debug("OpenClaw Mouth started speaking")

                        # Trigger callback
                        if self.on_speaking_start:
                            try:
                                self.on_speaking_start()
                            except Exception as e:
                                logger.error(f"Error in speaking_start callback: {e}")

                    elif not is_speaking and self._is_speaking:
                        # Transition: SPEAKING → IDLE
                        self._is_speaking = False
                        self._last_idle_time = now
                        logger.debug("OpenClaw Mouth stopped speaking")

                        # Trigger callback (after debounce)
                        if self.on_speaking_stop:
                            # Schedule callback after debounce
                            threading.Timer(
                                self.debounce_ms / 1000.0,
                                self._delayed_stop_callback
                            ).start()

            except Exception as e:
                if not self._error_logged:
                    logger.error(f"Error in mouth status monitor: {e}", exc_info=True)
                    self._error_logged = True

            time.sleep(self.poll_interval)

    def _delayed_stop_callback(self) -> None:
        """Trigger stop callback after debounce period."""
        with self._lock:
            # Only trigger if still not speaking
            if not self._is_speaking:
                if self.on_speaking_stop:
                    try:
                        self.on_speaking_stop()
                    except Exception as e:
                        logger.error(f"Error in speaking_stop callback: {e}")

    def _check_status(self) -> bool:
        """
        Read and parse the status file.

        Returns:
            True if status is "SPEAKING", False otherwise
        """
        try:
            content = self.status_file.read_text().strip()

            if not content:
                return False

            # Parse format: timestamp|status|details
            parts = content.split("|")

            if len(parts) < 2:
                if not self._error_logged:
                    logger.warning(f"Malformed status file content: {content}")
                    self._error_logged = True
                return False

            status = parts[1].strip()
            self._error_logged = False  # Reset on success

            return status == "SPEAKING"

        except FileNotFoundError:
            return False
        except PermissionError:
            if not self._error_logged:
                logger.error(f"Permission denied reading: {self.status_file}")
                self._error_logged = True
            return False
        except Exception as e:
            if not self._error_logged:
                logger.error(f"Error reading status file: {e}")
                self._error_logged = True
            return False
