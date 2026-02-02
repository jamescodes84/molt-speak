"""Text file monitoring service for detecting new text to speak."""

import logging
import time
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

logger = logging.getLogger(__name__)


class TextFileHandler(FileSystemEventHandler):
    """Handler for file system events on the speech input file."""

    def __init__(self, file_path: Path, text_queue: Queue, last_position: int = 0):
        """
        Initialize the file handler.

        Args:
            file_path: Path to the file being monitored
            text_queue: Queue to put new text into
            last_position: Last read position in the file
        """
        super().__init__()
        self.file_path = file_path
        self.text_queue = text_queue
        self.last_position = last_position

    def on_modified(self, event: FileModifiedEvent) -> None:
        """
        Handle file modification events.

        Args:
            event: File system event
        """
        if event.src_path != str(self.file_path):
            return

        try:
            self.read_new_content()
        except Exception as e:
            logger.error(f"Error reading file on modification: {e}")

    def read_new_content(self) -> None:
        """Read new content from the file and queue it."""
        try:
            if not self.file_path.exists():
                return

            with open(self.file_path, "r", encoding="utf-8") as f:
                # Seek to last position
                f.seek(self.last_position)

                # Read new content
                new_content = f.read()

                # Update position
                self.last_position = f.tell()

                if new_content.strip():
                    # Split into lines and queue each non-empty line
                    lines = new_content.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if line:
                            self.text_queue.put(line)
                            logger.debug(f"Queued new text: {line[:50]}...")

        except Exception as e:
            logger.error(f"Error reading new content: {e}")


class TextMonitor:
    """Monitor a text file for new content to speak."""

    def __init__(
        self,
        file_path: Path,
        text_queue: Queue,
        monitor_interval: float = 0.1
    ):
        """
        Initialize the text monitor.

        Args:
            file_path: Path to the file to monitor
            text_queue: Queue to put detected text into
            monitor_interval: How often to poll the file (seconds)
        """
        self.file_path = Path(file_path)
        self.text_queue = text_queue
        self.monitor_interval = monitor_interval

        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file if it doesn't exist
        if not self.file_path.exists():
            self.file_path.touch()

        # Track file position
        self.last_position = self._get_file_size()

        # Watchdog observer
        self.observer = None
        self.file_handler = None

        # Thread control
        self.running = Event()
        self.monitor_thread = None

        logger.info(f"Text monitor initialized for {file_path}")

    def _get_file_size(self) -> int:
        """
        Get current file size.

        Returns:
            File size in bytes
        """
        try:
            if self.file_path.exists():
                return self.file_path.stat().st_size
            return 0
        except Exception as e:
            logger.error(f"Error getting file size: {e}")
            return 0

    def start(self) -> None:
        """Start monitoring the file."""
        try:
            self.running.set()

            # Use watchdog for file monitoring
            self.file_handler = TextFileHandler(
                self.file_path,
                self.text_queue,
                self.last_position
            )

            self.observer = Observer()
            self.observer.schedule(
                self.file_handler,
                str(self.file_path.parent),
                recursive=False
            )
            self.observer.start()

            logger.info(f"Started monitoring {self.file_path}")

        except Exception as e:
            logger.error(f"Failed to start text monitor: {e}")
            raise

    def stop(self) -> None:
        """Stop monitoring the file."""
        try:
            self.running.clear()

            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=2.0)

            logger.info("Text monitor stopped")

        except Exception as e:
            logger.error(f"Error stopping text monitor: {e}")

    def read_existing_content(self) -> list[str]:
        """
        Read all existing content from the file (for initial load).

        Returns:
            List of text lines
        """
        try:
            if not self.file_path.exists():
                return []

            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.last_position = f.tell()

                lines = [line.strip() for line in content.split("\n") if line.strip()]
                return lines

        except Exception as e:
            logger.error(f"Error reading existing content: {e}")
            return []


class PollingTextMonitor:
    """
    Alternative text monitor using polling instead of file system events.

    This is simpler and more reliable but less efficient.
    """

    def __init__(
        self,
        file_path: Path,
        text_queue: Queue,
        poll_interval: float = 0.1
    ):
        """
        Initialize the polling text monitor.

        Args:
            file_path: Path to the file to monitor
            text_queue: Queue to put detected text into
            poll_interval: How often to check the file (seconds)
        """
        self.file_path = Path(file_path)
        self.text_queue = text_queue
        self.poll_interval = poll_interval

        # Ensure file exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.touch()

        # Track position
        self.last_position = self._get_file_size()

        # Thread control
        self.running = Event()
        self.poll_thread = None

        logger.info(f"Polling text monitor initialized for {file_path}")

    def _get_file_size(self) -> int:
        """Get current file size."""
        try:
            if self.file_path.exists():
                return self.file_path.stat().st_size
            return 0
        except Exception:
            return 0

    def _poll_loop(self) -> None:
        """Main polling loop running in a thread."""
        while self.running.is_set():
            try:
                self._check_for_new_content()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

    def _check_for_new_content(self) -> None:
        """Check file for new content."""
        try:
            # Always try to read, regardless of file size
            # This catches writes that haven't been flushed yet
            with open(self.file_path, "r", encoding="utf-8") as f:
                f.seek(self.last_position)
                new_content = f.read()

                if new_content:
                    # Update position immediately
                    self.last_position = f.tell()

                    # Process any complete lines (ending with \n)
                    # Also process the last line if it doesn't end with \n
                    if new_content.strip():
                        lines = new_content.split("\n")

                        # Process all complete lines (all except possibly the last)
                        for line in lines:
                            line = line.strip()
                            if line:
                                self.text_queue.put(line)
                                logger.debug(f"Queued: {line[:50]}...")

        except Exception as e:
            logger.error(f"Error checking for new content: {e}")

    def start(self) -> None:
        """Start the polling monitor."""
        self.running.set()
        self.poll_thread = Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        logger.info(f"Started polling monitor for {self.file_path}")

    def stop(self) -> None:
        """Stop the polling monitor."""
        self.running.clear()
        if self.poll_thread:
            self.poll_thread.join(timeout=1.0)
        logger.info("Polling monitor stopped")
