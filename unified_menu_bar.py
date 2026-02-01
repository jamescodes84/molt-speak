#!/usr/bin/env python3
"""
Unified macOS menu bar application for OpenClaw Voice Loop.

Controls:
- Integration Coordinator (echo prevention)
- OpenClaw Mouth (voice output)
- OpenClaw Ears (voice input)
"""

import logging
import subprocess
import os
import signal
from pathlib import Path
from typing import Optional, Tuple
import rumps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VoiceLoopMenuBar(rumps.App):
    """Unified menu bar application for OpenClaw Voice Loop."""

    def __init__(self):
        """Initialize menu bar app."""
        super().__init__("🔴🎙️", quit_button=None)  # Start with red (inactive)

        # Paths
        self.project_dir = Path(__file__).parent
        self.openclaw_dir = Path.home() / ".openclaw"

        # PID files
        self.integration_pid_file = self.openclaw_dir / "integration.pid"
        self.mouth_pid_file = self.openclaw_dir / "mouth.pid"
        self.ears_pid_file = self.openclaw_dir / "ears.pid"

        # State
        self.integration_running = False
        self.mouth_running = False
        self.ears_running = False

        # Build initial menu
        self.build_menu()

        # Start status update timer
        self.timer = rumps.Timer(self.update_status, 2.0)
        self.timer.start()

        logger.info("Unified Voice Loop Menu Bar initialized")

    def build_menu(self):
        """Build the menu structure."""
        self.menu.clear()

        # Header - System Status
        all_running = self.integration_running and self.mouth_running and self.ears_running

        if all_running:
            self.menu.add(rumps.MenuItem("✅ Voice Loop Active", callback=None))
        else:
            self.menu.add(rumps.MenuItem("⚪ Voice Loop Inactive", callback=None))

        self.menu.add(rumps.separator)

        # Individual system status
        status_menu = rumps.MenuItem("System Status")

        int_status = "✅" if self.integration_running else "⚪"
        status_menu.add(rumps.MenuItem(f"{int_status} Integration Coordinator", callback=None))

        mouth_status = "✅" if self.mouth_running else "⚪"
        status_menu.add(rumps.MenuItem(f"{mouth_status} OpenClaw Mouth", callback=None))

        ears_status = "✅" if self.ears_running else "⚪"
        status_menu.add(rumps.MenuItem(f"{ears_status} OpenClaw Ears", callback=None))

        self.menu.add(status_menu)

        self.menu.add(rumps.separator)

        # Control menu
        if all_running:
            self.menu.add(rumps.MenuItem("⏹️  Stop Voice Loop", callback=self.on_stop_all))
        else:
            self.menu.add(rumps.MenuItem("▶️  Start Voice Loop", callback=self.on_start_all))

        self.menu.add(rumps.separator)

        # Individual controls submenu
        controls = rumps.MenuItem("Individual Controls")

        if self.integration_running:
            controls.add(rumps.MenuItem("Stop Integration", callback=self.on_stop_integration))
        else:
            controls.add(rumps.MenuItem("Start Integration", callback=self.on_start_integration))

        if self.mouth_running:
            controls.add(rumps.MenuItem("Stop Mouth", callback=self.on_stop_mouth))
        else:
            controls.add(rumps.MenuItem("Start Mouth", callback=self.on_start_mouth))

        if self.ears_running:
            controls.add(rumps.MenuItem("Stop Ears", callback=self.on_stop_ears))
        else:
            controls.add(rumps.MenuItem("Start Ears", callback=self.on_start_ears))

        self.menu.add(controls)

        self.menu.add(rumps.separator)

        # Logs submenu
        logs_menu = rumps.MenuItem("📋 View Logs")
        logs_menu.add(rumps.MenuItem("Integration Log", callback=self.on_view_integration_log))
        logs_menu.add(rumps.MenuItem("Mouth Log", callback=self.on_view_mouth_log))
        logs_menu.add(rumps.MenuItem("Ears Log", callback=self.on_view_ears_log))
        logs_menu.add(rumps.separator)
        logs_menu.add(rumps.MenuItem("All Logs (Combined)", callback=self.on_view_all_logs))
        self.menu.add(logs_menu)

        # Configuration submenu
        config_menu = rumps.MenuItem("⚙️  Configuration")
        config_menu.add(rumps.MenuItem("Open Config Directory", callback=self.on_open_config_dir))
        config_menu.add(rumps.MenuItem("View Agent Instructions", callback=self.on_view_instructions))
        config_menu.add(rumps.MenuItem("Window Targeting Settings", callback=self.on_window_targeting_help))
        self.menu.add(config_menu)

        self.menu.add(rumps.separator)

        # Quick actions
        self.menu.add(rumps.MenuItem("📁 Open Project Folder", callback=self.on_open_project))
        self.menu.add(rumps.MenuItem("🔄 Refresh Status", callback=lambda _: self.update_status(None)))

        self.menu.add(rumps.separator)

        # Setup Instructions
        setup_menu = rumps.MenuItem("📝 Setup")
        setup_menu.add(rumps.MenuItem("1️⃣ Copy This Echo Command", callback=self.on_copy_title_command))
        setup_menu.add(rumps.MenuItem("2️⃣ Paste in Terminal, Start Agent", callback=self.on_show_full_setup))
        setup_menu.add(rumps.separator)
        setup_menu.add(rumps.MenuItem("Show Setup Steps", callback=self.on_show_setup_steps))
        setup_menu.add(rumps.MenuItem("Configure Window Pattern", callback=self.on_configure_pattern))
        self.menu.add(setup_menu)

        # Help
        help_menu = rumps.MenuItem("❓ Help")
        help_menu.add(rumps.MenuItem("Quick Start Guide", callback=self.on_quick_start))
        help_menu.add(rumps.MenuItem("Window Targeting Docs", callback=self.on_window_targeting_docs))
        help_menu.add(rumps.MenuItem("Troubleshooting", callback=self.on_troubleshooting))
        self.menu.add(help_menu)

        self.menu.add(rumps.separator)

        # Quit
        self.menu.add(rumps.MenuItem("Quit Menu Bar App", callback=self.on_quit))

    def check_process(self, pid_file: Path) -> bool:
        """Check if a process is running by PID file."""
        if not pid_file.exists():
            return False

        try:
            pid = int(pid_file.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError, PermissionError):
            return False

    def update_status(self, sender):
        """Update status of all systems."""
        integration_was_running = self.integration_running
        mouth_was_running = self.mouth_running
        ears_was_running = self.ears_running

        # Check each system
        self.integration_running = self.check_process(self.integration_pid_file)
        self.mouth_running = self.check_process(self.mouth_pid_file)
        self.ears_running = self.check_process(self.ears_pid_file)

        # Update title based on status
        all_running = self.integration_running and self.mouth_running and self.ears_running

        if all_running:
            self.title = "🟢🎙️"  # Green circle for active
        else:
            self.title = "🔴🎙️"  # Red circle for inactive

        # Rebuild menu if anything changed
        if (integration_was_running != self.integration_running or
            mouth_was_running != self.mouth_running or
            ears_was_running != self.ears_running):
            self.build_menu()

    def on_start_all(self, sender):
        """Start the complete voice loop."""
        try:
            logger.info("Starting voice loop...")

            # Run start script
            script_path = self.project_dir / "start_voice_loop.sh"
            result = subprocess.run(
                [str(script_path)],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                rumps.notification(
                    "Voice Loop Started",
                    "",
                    "All systems are now running"
                )
                self.update_status(None)
            else:
                rumps.alert(
                    "Start Failed",
                    f"Failed to start voice loop:\n\n{result.stderr}"
                )
        except Exception as e:
            logger.error(f"Error starting voice loop: {e}")
            rumps.alert("Error", f"Failed to start: {e}")

    def on_stop_all(self, sender):
        """Stop the complete voice loop."""
        try:
            logger.info("Stopping voice loop...")

            # Run stop script
            script_path = self.project_dir / "stop_voice_loop.sh"
            result = subprocess.run(
                [str(script_path)],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Clear speech output queue to prevent old messages on restart
                speech_output = self.openclaw_dir / "speech_output.txt"
                try:
                    speech_output.write_text("")
                    logger.info("Cleared speech output queue")
                except Exception as e:
                    logger.warning(f"Failed to clear speech queue: {e}")

                rumps.notification(
                    "Voice Loop Stopped",
                    "",
                    "All systems have been shut down"
                )
                self.update_status(None)
            else:
                rumps.alert(
                    "Stop Failed",
                    f"Failed to stop voice loop:\n\n{result.stderr}"
                )
        except Exception as e:
            logger.error(f"Error stopping voice loop: {e}")
            rumps.alert("Error", f"Failed to stop: {e}")

    def on_start_integration(self, sender):
        """Start Integration Coordinator."""
        self._start_component("integration", "Integration Coordinator",
                             "python main.py")

    def on_start_mouth(self, sender):
        """Start OpenClaw Mouth."""
        self._start_component("mouth", "OpenClaw Mouth",
                             "cd open_mouth && ./start_speech_system.sh")

    def on_start_ears(self, sender):
        """Start OpenClaw Ears."""
        self._start_component("ears", "OpenClaw Ears",
                             "cd open_ears && ./start_voice_system.sh")

    def _start_component(self, name: str, display_name: str, command: str):
        """Start a component."""
        try:
            subprocess.Popen(
                command,
                shell=True,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            rumps.notification(f"{display_name} Started", "", f"{display_name} is now running")
            self.update_status(None)
        except Exception as e:
            logger.error(f"Error starting {name}: {e}")
            rumps.alert("Error", f"Failed to start {display_name}: {e}")

    def on_stop_integration(self, sender):
        """Stop Integration Coordinator."""
        self._stop_component(self.integration_pid_file, "Integration Coordinator")

    def on_stop_mouth(self, sender):
        """Stop OpenClaw Mouth."""
        self._stop_component(self.mouth_pid_file, "OpenClaw Mouth")

    def on_stop_ears(self, sender):
        """Stop OpenClaw Ears."""
        self._stop_component(self.ears_pid_file, "OpenClaw Ears")

    def _stop_component(self, pid_file: Path, display_name: str):
        """Stop a component by PID file."""
        try:
            if pid_file.exists():
                pid = int(pid_file.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                rumps.notification(f"{display_name} Stopped", "", f"{display_name} has been shut down")
                self.update_status(None)
            else:
                rumps.alert("Not Running", f"{display_name} is not currently running")
        except Exception as e:
            logger.error(f"Error stopping {display_name}: {e}")
            rumps.alert("Error", f"Failed to stop {display_name}: {e}")

    def on_view_integration_log(self, sender):
        """View integration log."""
        self._open_log(self.openclaw_dir / "logs" / "integration.log", "Integration")

    def on_view_mouth_log(self, sender):
        """View mouth log."""
        self._open_log(self.openclaw_dir / "logs" / "mouth.log", "Mouth")

    def on_view_ears_log(self, sender):
        """View ears log."""
        self._open_log(self.openclaw_dir / "logs" / "ears.log", "Ears")

    def on_view_all_logs(self, sender):
        """View all logs in separate tabs."""
        logs = [
            (self.openclaw_dir / "logs" / "integration.log", "Integration"),
            (self.openclaw_dir / "logs" / "mouth.log", "Mouth"),
            (self.openclaw_dir / "logs" / "ears.log", "Ears")
        ]

        for log_path, name in logs:
            if log_path.exists():
                self._open_log(log_path, name)

    def _open_log(self, log_path: Path, name: str):
        """Open a log file in Terminal."""
        if not log_path.exists():
            rumps.alert("Log Not Found", f"{name} log file doesn't exist yet.\n\nStart the system to create logs.")
            return

        script = f'''
        tell application "Terminal"
            activate
            do script "tail -f '{log_path}'"
        end tell
        '''

        try:
            subprocess.run(["osascript", "-e", script], check=True)
        except Exception as e:
            logger.error(f"Error opening log: {e}")
            rumps.alert("Error", f"Failed to open log: {e}")

    def on_open_config_dir(self, sender):
        """Open .openclaw directory."""
        subprocess.run(["open", str(self.openclaw_dir)])

    def on_view_instructions(self, sender):
        """View agent instructions."""
        instructions_file = self.openclaw_dir / "agent_instructions.active"

        if instructions_file.exists():
            subprocess.run(["open", "-a", "TextEdit", str(instructions_file)])
        else:
            rumps.alert(
                "Instructions Not Available",
                "Agent instructions are created when the voice loop starts.\n\nStart the voice loop to see the instructions."
            )

    def on_window_targeting_help(self, sender):
        """Show window targeting help."""
        msg = """Window Targeting Configuration

Set terminal tab name:
echo -n -e "\\033]0;OpenClaw Agent\\007"

Configure in open_ears/.env:
TARGET_WINDOW_PATTERN=openclaw
ACTIVATE_TARGET_WINDOW=true

See: open_ears/WINDOW_TARGETING.md"""

        rumps.alert("Window Targeting", msg)

    def on_open_project(self, sender):
        """Open project folder."""
        subprocess.run(["open", str(self.project_dir)])

    def on_copy_title_command(self, sender):
        """Copy terminal title command to clipboard."""
        command = 'echo -n -e "\\033]0;OpenClaw Agent\\007"'

        # Copy to clipboard using pbcopy
        try:
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(command.encode('utf-8'))

            rumps.notification(
                "Command Copied",
                "",
                "Terminal title command copied to clipboard!\n\nPaste in your agent's terminal."
            )

            # Also show the command in an alert
            rumps.alert(
                "Terminal Title Command",
                f"Copied to clipboard:\n\n{command}\n\n" +
                "Paste this in your OpenClaw agent's terminal to set the window title.\n\n" +
                "This allows OpenClaw Ears to find and type into the correct terminal window."
            )
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            rumps.alert(
                "Copy Command Manually",
                f"Please copy this command:\n\n{command}\n\n" +
                "Then paste it in your OpenClaw agent's terminal."
            )

    def on_show_full_setup(self, sender):
        """Show full setup with echo command visible."""
        command = 'echo -n -e "\\033]0;OpenClaw Agent\\007"'

        setup_text = f"""Paste This Into Your Terminal, Then Start OpenClaw TUI

STEP 1: Paste this echo command in your terminal:

{command}

STEP 2: Start your OpenClaw agent/TUI in that terminal

STEP 3: The voice loop will now find your terminal automatically!

Why this works:
• Sets your terminal tab name to "OpenClaw Agent"
• OpenClaw Ears searches for "openclaw" in tab names
• Automatically types voice commands into the right window

Click "1️⃣ Copy This Echo Command" to copy to clipboard."""

        rumps.alert("Terminal Setup Command", setup_text)

    def on_show_setup_steps(self, sender):
        """Show setup steps for voice loop."""
        steps = """Quick Setup Guide

1. Start the voice loop:
   Click "▶️  Start Voice Loop" in menu

2. Set your agent's terminal title:
   Click "1️⃣ Copy This Echo Command"
   Paste in your agent's terminal

3. Speak to your agent:
   Voice commands will appear in your agent's terminal
   No need to focus the window!

Configuration:
• Pattern: "openclaw" (default)
• Change in open_ears/.env

See: Window Targeting Docs for details"""

        rumps.alert("Setup Steps", steps)

    def on_configure_pattern(self, sender):
        """Show window pattern configuration."""
        current_pattern = "openclaw"  # Default

        # Try to read from settings
        env_file = self.project_dir / "open_ears" / ".env"
        if env_file.exists():
            try:
                content = env_file.read_text()
                for line in content.split('\n'):
                    if line.startswith('TARGET_WINDOW_PATTERN='):
                        current_pattern = line.split('=', 1)[1].strip().strip('"')
                        break
            except Exception:
                pass

        msg = f"""Window Pattern Configuration

Current Pattern: {current_pattern}

This pattern is used to find your agent's terminal window.

To change:
1. Edit: open_ears/.env
2. Add/modify: TARGET_WINDOW_PATTERN=yourpattern
3. Restart OpenClaw Ears

Examples:
• TARGET_WINDOW_PATTERN=openclaw
• TARGET_WINDOW_PATTERN=agent
• TARGET_WINDOW_PATTERN=claude
• TARGET_WINDOW_PATTERN="" (use frontmost)

The pattern matches against terminal tab names (case-insensitive)."""

        rumps.alert("Window Pattern Config", msg)

    def on_quick_start(self, sender):
        """Show quick start guide."""
        quick_start = self.project_dir / "QUICK_START.md"
        if quick_start.exists():
            subprocess.run(["open", str(quick_start)])
        else:
            rumps.alert("Not Found", "QUICK_START.md not found in project directory")

    def on_window_targeting_docs(self, sender):
        """Show window targeting documentation."""
        docs = self.project_dir / "open_ears" / "WINDOW_TARGETING.md"
        if docs.exists():
            subprocess.run(["open", str(docs)])
        else:
            rumps.alert("Not Found", "WINDOW_TARGETING.md not found")

    def on_troubleshooting(self, sender):
        """Show troubleshooting."""
        msg = """Common Issues:

1. Not receiving voice commands
   → Set terminal name with escape sequence
   → Check TARGET_WINDOW_PATTERN matches

2. Echo/feedback
   → Ensure Integration is running
   → Check all 3 systems are active

3. Commands to wrong window
   → Set terminal tab name
   → Configure TARGET_WINDOW_PATTERN

View full docs in AGENT_INSTRUCTIONS.txt"""

        rumps.alert("Troubleshooting", msg)

    def on_quit(self, sender):
        """Quit the menu bar app and stop all voice loop processes."""
        # Check if voice loop is running
        any_running = self.integration_running or self.mouth_running or self.ears_running

        if any_running:
            response = rumps.alert(
                "Quit Menu Bar App",
                "The voice loop is currently running.\n\nQuitting will stop all voice systems.",
                ok="Stop & Quit",
                cancel="Cancel"
            )

            if response == 1:  # OK = Stop & Quit
                self.on_stop_all(None)
                rumps.quit_application()
            # else: Cancel, do nothing
        else:
            # Nothing running, just quit
            rumps.quit_application()


def main():
    """Main entry point."""
    app = VoiceLoopMenuBar()
    app.run()


if __name__ == "__main__":
    main()
