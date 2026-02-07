"""
Voice Loop Coordinator

Coordinates OpenClaw Ears (voice input) and OpenClaw Mouth (TTS output)
to prevent echo and feedback in full voice conversations.

Monitors OpenClaw Mouth's speaking status and signals OpenClaw Ears to
pause the microphone when TTS is active.
"""

import logging
import signal
import sys
import time
from pathlib import Path

from ..config import settings
from ..services.mouth_status_monitor import MouthStatusMonitor
from ..services.agent_messenger import AgentMessenger

logger = logging.getLogger(__name__)


class VoiceLoopCoordinator:
    """
    Coordinates voice input and output to prevent echo/feedback.

    Monitors OpenClaw Mouth's speaking status and creates a pause signal
    file that OpenClaw Ears can check to pause its microphone.
    """

    def __init__(self, analytics=None):
        """Initialize the voice loop coordinator."""
        # Ensure runtime directory exists
        settings.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

        # Analytics
        self.analytics = analytics

        # Pause signal file for Ears
        self.pause_signal_file = settings.EARS_PAUSE_SIGNAL_FILE

        # Initialize mouth status monitor
        self.mouth_monitor = MouthStatusMonitor(
            status_file=settings.MOUTH_STATUS_FILE,
            poll_interval=settings.MOUTH_STATUS_POLL_INTERVAL,
            debounce_ms=settings.MOUTH_STATUS_DEBOUNCE_MS,
            on_speaking_start=self._on_mouth_speaking,
            on_speaking_stop=self._on_mouth_idle
        )

        # Initialize agent messenger
        instructions_file = Path(__file__).parent.parent.parent / "AGENT_INSTRUCTIONS.txt"
        self.messenger = AgentMessenger(
            openclaw_dir=settings.RUNTIME_DIR,
            instructions_file=instructions_file
        )

        # Running flag
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _on_mouth_speaking(self) -> None:
        """Called when OpenClaw Mouth starts speaking."""
        logger.info("Agent started speaking - signaling Ears to pause")

        # Track event
        if self.analytics:
            self.analytics.track_event("echo_prevention_activated", {
                "action": "pause_microphone"
            })

        # Create pause signal file
        try:
            self.pause_signal_file.write_text(f"{time.time()}\n")
            logger.debug(f"Created pause signal: {self.pause_signal_file}")
        except Exception as e:
            logger.error(f"Failed to create pause signal: {e}")

    def _on_mouth_idle(self) -> None:
        """Called when OpenClaw Mouth stops speaking."""
        logger.info("Agent stopped speaking - signaling Ears to resume")

        # Track event
        if self.analytics:
            self.analytics.track_event("echo_prevention_deactivated", {
                "action": "resume_microphone"
            })

        # Remove pause signal file
        try:
            if self.pause_signal_file.exists():
                self.pause_signal_file.unlink()
                logger.debug(f"Removed pause signal: {self.pause_signal_file}")
        except Exception as e:
            logger.error(f"Failed to remove pause signal: {e}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def start(self) -> None:
        """Start the voice loop coordinator."""
        if not settings.ENABLE_INTEGRATION:
            logger.warning("Integration disabled in settings")
            return

        logger.info("=" * 60)
        logger.info("OpenClaw Voice Loop Coordinator")
        logger.info("=" * 60)
        logger.info(f"Monitoring: {settings.MOUTH_STATUS_FILE}")
        logger.info(f"Signal file: {settings.EARS_PAUSE_SIGNAL_FILE}")
        logger.info(f"Poll interval: {settings.MOUTH_STATUS_POLL_INTERVAL}s")
        logger.info(f"Debounce: {settings.MOUTH_STATUS_DEBOUNCE_MS}ms")
        logger.info("=" * 60)

        # Check if OpenClaw Mouth is available
        if not self.mouth_monitor.is_available():
            logger.warning(
                f"OpenClaw Mouth status file not found: {settings.MOUTH_STATUS_FILE}"
            )
            logger.warning("Waiting for OpenClaw Mouth to start...")

        # Send startup instructions to agent
        logger.info("")
        if self.messenger.send_startup_instructions():
            logger.info("✅ Agent instructions sent")
            logger.info(f"   Agent should read: {settings.RUNTIME_DIR}/agent_instructions.active")
        else:
            logger.warning("⚠️  Failed to send agent instructions")

        # Start monitoring
        self.mouth_monitor.start()
        self.running = True

        logger.info("")
        logger.info("✅ Coordinator started")
        logger.info("Press Ctrl+C to stop")

        # Main loop - just keep running
        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.stop()

    def stop(self) -> None:
        """Stop the voice loop coordinator."""
        if not self.running:
            return

        logger.info("")
        logger.info("Stopping coordinator...")
        self.running = False

        # Send shutdown message to agent
        if self.messenger.send_shutdown_message():
            logger.info("✅ Agent shutdown notification sent")
            logger.info(f"   Agent should read: {settings.RUNTIME_DIR}/agent_shutdown.signal")
        else:
            logger.warning("⚠️  Failed to send shutdown notification")

        # Stop monitor
        self.mouth_monitor.stop()

        # Clean up pause signal file
        try:
            if self.pause_signal_file.exists():
                self.pause_signal_file.unlink()
                logger.debug("Cleaned up pause signal file")
        except Exception as e:
            logger.error(f"Error cleaning up pause signal: {e}")

        # Clean up messenger files (after a delay to allow agent to read shutdown)
        time.sleep(1.0)  # Give agent time to read shutdown message
        self.messenger.cleanup()

        logger.info("")
        logger.info("✅ Coordinator stopped")
