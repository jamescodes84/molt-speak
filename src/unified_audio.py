#!/usr/bin/env python3
"""
Unified Audio System - Runs both OpenClaw Mouth and Ears as subprocesses.

Acts as a supervisor: detects crashes, classifies them, auto-restarts
transient failures with exponential backoff, and enters degraded mode
(one component alive) when a non-restartable failure occurs.
"""

import json
import os
import sys
import subprocess
import signal
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ─── Restart policy ──────────────────────────────────────────────────────────

@dataclass
class RestartPolicy:
    """Tracks restart attempts for a single component."""
    max_retries: int = 3
    backoff_delays: tuple = (1, 3, 8)  # seconds between attempts
    retry_count: int = 0
    last_crash_time: float = 0.0
    last_start_time: float = 0.0
    cooldown_window: float = 60.0  # reset retry_count after this many seconds of stability

    def get_delay(self) -> float:
        """Get the backoff delay for the current retry attempt."""
        idx = min(self.retry_count, len(self.backoff_delays) - 1)
        return self.backoff_delays[idx]

    def can_restart(self) -> bool:
        """Return True if we haven't exhausted retries."""
        return self.retry_count < self.max_retries

    def record_crash(self):
        """Record a crash and increment retry counter."""
        self.last_crash_time = time.time()
        self.retry_count += 1

    def record_start(self):
        """Record a successful start."""
        self.last_start_time = time.time()

    def check_stability_reset(self):
        """Reset retry counter if component has been stable long enough."""
        if self.last_start_time and self.retry_count > 0:
            uptime = time.time() - self.last_start_time
            if uptime >= self.cooldown_window:
                logger.info(f"Component stable for {uptime:.0f}s — resetting retry counter")
                self.retry_count = 0


class UnifiedAudioSystem:
    """Manages OpenClaw Mouth and Ears as coordinated subprocesses with auto-recovery."""

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

        # Restart policies — one per component
        self._restart_policy = {
            "ears": RestartPolicy(),
            "mouth": RestartPolicy(),
        }

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
        self._restart_policy["mouth"].record_start()

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
        self._restart_policy["ears"].record_start()

    def start(self):
        """Start both systems as subprocesses with supervisor loop."""
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

        # Clear any stale crash report
        crash_file = self.runtime_dir / "last_crash.json"
        try:
            crash_file.unlink(missing_ok=True)
        except Exception:
            pass

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

            # ── Supervisor loop ──────────────────────────────────────
            while self.running:
                # Check stability resets (component stable long enough → reset retries)
                for policy in self._restart_policy.values():
                    policy.check_stability_reset()

                # Check Mouth
                if self.mouth_process and self.mouth_process.poll() is not None:
                    self._handle_component_crash("mouth")

                # Check Ears
                if self.ears_process and self.ears_process.poll() is not None:
                    self._handle_component_crash("ears")

                # If BOTH are dead and unrecoverable, exit
                mouth_dead = self.mouth_process is None
                ears_dead = self.ears_process is None
                if mouth_dead and ears_dead:
                    logger.error("Both components are down — exiting")
                    self.running = False
                    break

                time.sleep(1)

        except Exception as e:
            logger.error(f"Error in Unified Audio System: {e}", exc_info=True)
        finally:
            self.stop()

    def _handle_component_crash(self, component: str):
        """Handle a crashed component: diagnose, classify, restart or degrade."""
        process = self.mouth_process if component == "mouth" else self.ears_process
        exit_code = process.returncode if process else 1
        policy = self._restart_policy[component]

        # Close the old log file handle so we can reopen on restart
        log_fh = self.mouth_log_file if component == "mouth" else self.ears_log_file
        if log_fh and not log_fh.closed:
            try:
                log_fh.close()
            except OSError:
                pass

        # Diagnose the crash
        diag = self._diagnose_crash(component, exit_code)
        logger.error(f"OpenClaw {diag['component']} crashed: {diag['message']}")

        if diag["restartable"] and policy.can_restart():
            # ── Transient failure: auto-restart with backoff ──
            policy.record_crash()
            delay = policy.get_delay()
            attempt = policy.retry_count
            max_retries = policy.max_retries

            logger.info(
                f"Restarting {component} in {delay}s "
                f"(attempt {attempt}/{max_retries})"
            )

            diag["action"] = "auto_restarted"
            diag["retry_count"] = attempt
            self._write_crash_json(diag)

            time.sleep(delay)

            try:
                if component == "mouth":
                    self.start_mouth()
                else:
                    self.start_ears()
                logger.info(f"✓ {component.capitalize()} restarted successfully")
            except Exception as e:
                logger.error(f"Failed to restart {component}: {e}")
                # Mark as dead — enter degraded mode
                if component == "mouth":
                    self.mouth_process = None
                else:
                    self.ears_process = None
                diag["action"] = "restart_failed"
                self._write_crash_json(diag)

        elif diag["restartable"] and not policy.can_restart():
            # ── Retries exhausted ──
            logger.error(
                f"{component.capitalize()} keeps crashing "
                f"({policy.retry_count} attempts failed)"
            )
            diag["action"] = "retries_exhausted"
            diag["retry_count"] = policy.retry_count
            self._write_crash_json(diag)

            # Enter degraded mode — mark component as dead
            if component == "mouth":
                self.mouth_process = None
            else:
                self.ears_process = None

        else:
            # ── Non-restartable: user action needed ──
            logger.error(f"Fix: {diag['fix']}")
            diag["action"] = "needs_user_action"
            self._write_crash_json(diag)

            # Enter degraded mode — mark component as dead
            if component == "mouth":
                self.mouth_process = None
            else:
                self.ears_process = None

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

    def _diagnose_crash(self, component: str, exit_code: int) -> dict:
        """Analyze crash log and return plain-English diagnosis."""
        from src.errors import classify_crash

        log_file = self.logs_dir / f"{component}.log"
        log_tail = ""
        try:
            if log_file.exists():
                lines = log_file.read_text().splitlines()
                log_tail = "\n".join(lines[-50:])
        except Exception:
            pass

        err = classify_crash(component, exit_code, log_tail)
        return err.to_crash_dict(
            component=component.capitalize(),
            exit_code=exit_code,
        )

    def _write_crash_json(self, diag: dict):
        """Write crash info to runtime/last_crash.json for menu bar to read."""
        try:
            crash_file = self.runtime_dir / "last_crash.json"
            crash_file.write_text(json.dumps(diag, indent=2))
        except Exception as e:
            logger.warning(f"Could not write crash file: {e}")

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
