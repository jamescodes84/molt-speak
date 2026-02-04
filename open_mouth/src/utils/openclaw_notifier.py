"""OpenClaw integration utilities for notifying other components."""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


class OpenClawNotifier:
    """Handles notifications to OpenClaw ecosystem components."""

    def __init__(self, runtime_dir: Optional[Path] = None):
        """
        Initialize the notifier.

        Args:
            runtime_dir: Runtime directory (defaults to project's runtime/)
        """
        self.runtime_dir = runtime_dir or settings.RUNTIME_DIR
        self.runtime_dir.mkdir(exist_ok=True)

        # Status file for inter-component communication
        self.status_file = self.runtime_dir / "mouth_status.txt"

        # Create status file immediately so ears can monitor it
        self.notify_idle()

    def update_status(self, status: str, details: str = "") -> None:
        """
        Update the Mouth status file.

        Args:
            status: Current status (IDLE, SPEAKING, QUEUED, ERROR)
            details: Additional details about the status
        """
        try:
            timestamp = datetime.now().isoformat()
            status_content = f"{timestamp}|{status}|{details}\n"

            with open(self.status_file, "w") as f:
                f.write(status_content)

        except Exception as e:
            logger.warning(f"Failed to update status file: {e}")

    def notify_speaking(self, text_preview: str) -> None:
        """
        Notify that speech is in progress.

        Args:
            text_preview: Preview of the text being spoken
        """
        preview = text_preview[:50] + "..." if len(text_preview) > 50 else text_preview
        self.update_status("SPEAKING", preview)

    def notify_idle(self) -> None:
        """Notify that the system is idle."""
        self.update_status("IDLE")

    def notify_queued(self, queue_size: int) -> None:
        """
        Notify that items are queued for speech.

        Args:
            queue_size: Number of items in the queue
        """
        self.update_status("QUEUED", f"{queue_size} items")

    def notify_error(self, error_message: str) -> None:
        """
        Notify of an error.

        Args:
            error_message: Error message
        """
        self.update_status("ERROR", error_message)

    def cleanup(self) -> None:
        """Clean up status file on shutdown."""
        try:
            if self.status_file.exists():
                self.status_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to cleanup status file: {e}")
