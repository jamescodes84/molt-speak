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

    def __init__(self, debug_mode=False):
        """Initialize unified audio system."""
        self.mouth_process = None
        self.ears_process = None
        self.mouth_log_file = None
        self.ears_log_file = None
        self.running = False
        self.debug_mode = debug_mode
        self.project_root = Path(__file__).parent.parent.resolve()

        # Use project-local directories
        self.runtime_dir = self.project_root / "runtime"
        self.logs_dir = self.project_root / "logs"
        self.runtime_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

        # Speech output directory - use project runtime directory
        self.speech_output_dir = self.runtime_dir

        logger.info("Initializing Unified Audio System")

    def start_mouth(self):
        """Start OpenClaw Mouth (TTS output) subprocess."""
        mouth_dir = self.project_root / "open_mouth"
        main_venv = self.project_root / "venv" / "bin" / "python"
        mouth_main = mouth_dir / "main.py"

        # Use main project venv if available, otherwise system python
        python_cmd = str(main_venv) if main_venv.exists() else "python3"

        # Open log file for Mouth (project-local)
        mouth_log = self.logs_dir / "mouth.log"
        self.mouth_log_file = open(mouth_log, "a")

        # Let MouthPipeline read TTS provider from ConfigManager
        # (no --local flag = use cloud TTS based on config)
        logger.info("Starting OpenClaw Mouth (TTS based on config)...")
        self.mouth_process = subprocess.Popen(
            [python_cmd, str(mouth_main)],
            cwd=str(mouth_dir),
            stdout=self.mouth_log_file,
            stderr=subprocess.STDOUT
        )
        logger.info(f"✓ OpenClaw Mouth started (PID: {self.mouth_process.pid})")

    def start_ears(self):
        """Start OpenClaw Ears (voice input) subprocess."""
        ears_dir = self.project_root / "open_ears"
        main_venv = self.project_root / "venv" / "bin" / "python"
        ears_main = ears_dir / "main.py"

        # Use main project venv if available, otherwise system python
        python_cmd = str(main_venv) if main_venv.exists() else "python3"

        # Open log file for Ears (project-local)
        ears_log = self.logs_dir / "ears.log"
        self.ears_log_file = open(ears_log, "a")

        logger.info("Starting OpenClaw Ears (voice input)...")

        # Disable MPS to avoid PyTorch sparse tensor bug on Apple Silicon
        import os
        env = os.environ.copy()
        env['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'

        cmd = [python_cmd, str(ears_main)]
        if self.debug_mode:
            env['DEBUG_MODE'] = 'true'
            cmd.append('--debug')
            logger.info("  Debug mode enabled for Ears")
        logger.info(f"  Ears command: {' '.join(cmd)}")
        logger.info(f"  DEBUG_MODE env: {env.get('DEBUG_MODE', 'not set')}")

        self.ears_process = subprocess.Popen(
            cmd,
            cwd=str(ears_dir),
            stdout=self.ears_log_file,
            stderr=subprocess.STDOUT,
            env=env
        )
        logger.info(f"✓ OpenClaw Ears started (PID: {self.ears_process.pid})")

    def start(self):
        """Start both systems as subprocesses."""
        logger.info("=" * 60)
        logger.info("Starting Unified Audio System")
        logger.info("=" * 60)

        # Clear speech output file to start fresh
        # The text monitor only reads NEW content after startup
        speech_file = self.speech_output_dir / "speech_output.txt"
        try:
            speech_file.write_text("")
            logger.info(f"Cleared speech output file: {speech_file}")
        except Exception as e:
            logger.warning(f"Could not clear speech file: {e}")

        # Clear mouth status so ears monitor starts clean
        mouth_status_file = self.runtime_dir / "mouth_status.txt"
        try:
            mouth_status_file.write_text("")
        except Exception as e:
            logger.warning(f"Could not clear mouth status: {e}")

        # Clear session archive logs so each session starts fresh
        for log_name in ["session_temperature_log.jsonl", "session_barge_in_log.jsonl"]:
            log_file = self.runtime_dir / log_name
            try:
                log_file.write_text("")
                logger.info(f"Cleared session log: {log_file}")
            except Exception as e:
                logger.warning(f"Could not clear session log {log_name}: {e}")

        self.running = True

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            # Start Ears first — mic is the #1 startup priority
            self.start_ears()
            time.sleep(0.3)

            # Then start Mouth
            self.start_mouth()
            time.sleep(0.5)

            logger.info("=" * 60)
            logger.info("Unified Audio System running")
            if self.mouth_process:
                logger.info(f"  • Mouth PID: {self.mouth_process.pid}")
            if self.ears_process:
                logger.info(f"  • Ears PID:  {self.ears_process.pid}")
            logger.info("=" * 60)

            # Monitor subprocesses
            while self.running:
                # Check if mouth process is still running
                if self.mouth_process and self.mouth_process.poll() is not None:
                    logger.error("OpenClaw Mouth process died unexpectedly")
                    self.running = False
                    break

                # Check if ears process is still running
                if self.ears_process and self.ears_process.poll() is not None:
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

        # Close log file handles
        for fh in (self.mouth_log_file, self.ears_log_file):
            if fh and not fh.closed:
                try:
                    fh.close()
                except OSError:
                    pass

        logger.info("Unified Audio System stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"\nReceived signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='OpenClaw Unified Audio System')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode (inline tags in agent messages)')
    args = parser.parse_args()

    mode_label = " (DEBUG MODE)" if args.debug else ""
    print(f"""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║           OpenClaw Unified Audio System{mode_label:>20s}║
║                                                            ║
║  Managing Mouth (TTS) + Ears (Voice Input) together       ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")

    system = UnifiedAudioSystem(debug_mode=args.debug)

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
