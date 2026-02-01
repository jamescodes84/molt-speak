#!/usr/bin/env python3
"""
Unified Audio System - Runs both OpenClaw Mouth and Ears as subprocesses.

This solves audio device conflicts by managing both systems from a single
parent Python process with coordinated lifecycle management.
"""

import sys
import subprocess
import signal
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedAudioSystem:
    """Manages OpenClaw Mouth and Ears as coordinated subprocesses."""

    def __init__(self):
        """Initialize unified audio system."""
        self.mouth_process = None
        self.ears_process = None
        self.running = False
        self.project_root = Path(__file__).parent.parent

        logger.info("Initializing Unified Audio System")

    def start_mouth(self):
        """Start OpenClaw Mouth (TTS output) subprocess."""
        mouth_dir = self.project_root / "open_mouth"
        mouth_venv = mouth_dir / "venv" / "bin" / "python"
        mouth_main = mouth_dir / "main.py"

        # Use venv python if available, otherwise system python
        python_cmd = str(mouth_venv) if mouth_venv.exists() else "python3"

        logger.info("Starting OpenClaw Mouth (TTS)...")
        self.mouth_process = subprocess.Popen(
            [python_cmd, str(mouth_main)],
            cwd=str(mouth_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        logger.info(f"✓ OpenClaw Mouth started (PID: {self.mouth_process.pid})")

    def start_ears(self):
        """Start OpenClaw Ears (voice input) subprocess."""
        ears_dir = self.project_root / "open_ears"
        ears_venv = ears_dir / "venv" / "bin" / "python"
        ears_main = ears_dir / "main.py"

        # Use venv python if available, otherwise system python
        python_cmd = str(ears_venv) if ears_venv.exists() else "python3"

        logger.info("Starting OpenClaw Ears (voice input)...")
        self.ears_process = subprocess.Popen(
            [python_cmd, str(ears_main)],
            cwd=str(ears_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        logger.info(f"✓ OpenClaw Ears started (PID: {self.ears_process.pid})")

    def start(self):
        """Start both systems as subprocesses."""
        logger.info("=" * 60)
        logger.info("Starting Unified Audio System")
        logger.info("=" * 60)

        self.running = True

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            # Start Mouth first
            self.start_mouth()
            time.sleep(2)

            # Then start Ears
            self.start_ears()
            time.sleep(1)

            logger.info("=" * 60)
            logger.info("Unified Audio System running")
            logger.info(f"  • Mouth PID: {self.mouth_process.pid}")
            logger.info(f"  • Ears PID:  {self.ears_process.pid}")
            logger.info("=" * 60)

            # Monitor subprocesses
            while self.running:
                # Check if mouth process is still running
                if self.mouth_process.poll() is not None:
                    logger.error("OpenClaw Mouth process died unexpectedly")
                    self.running = False
                    break

                # Check if ears process is still running
                if self.ears_process.poll() is not None:
                    logger.error("OpenClaw Ears process died unexpectedly")
                    self.running = False
                    break

                time.sleep(1)

        except Exception as e:
            logger.error(f"Error in Unified Audio System: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Stop both systems gracefully."""
        logger.info("Stopping Unified Audio System...")
        self.running = False

        # Stop Ears first (voice input)
        if self.ears_process and self.ears_process.poll() is None:
            logger.info("Stopping OpenClaw Ears...")
            self.ears_process.terminate()
            try:
                self.ears_process.wait(timeout=5)
                logger.info("✓ OpenClaw Ears stopped")
            except subprocess.TimeoutExpired:
                logger.warning("Force killing OpenClaw Ears...")
                self.ears_process.kill()

        # Then stop Mouth (TTS output)
        if self.mouth_process and self.mouth_process.poll() is None:
            logger.info("Stopping OpenClaw Mouth...")
            self.mouth_process.terminate()
            try:
                self.mouth_process.wait(timeout=5)
                logger.info("✓ OpenClaw Mouth stopped")
            except subprocess.TimeoutExpired:
                logger.warning("Force killing OpenClaw Mouth...")
                self.mouth_process.kill()

        logger.info("Unified Audio System stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"\nReceived signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point."""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║           OpenClaw Unified Audio System                    ║
║                                                            ║
║  Managing Mouth (TTS) + Ears (Voice Input) together       ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")

    system = UnifiedAudioSystem()

    try:
        system.start()
    except KeyboardInterrupt:
        print("\n\nShutdown requested...")
        system.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
