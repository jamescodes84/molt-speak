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
import time
import atexit
from pathlib import Path
from typing import Optional
import rumps

from src.config.config_manager import ConfigManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VoiceLoopMenuBar(rumps.App):
    """Unified menu bar application for OpenClaw Voice Loop."""

    def __init__(self):
        """Initialize menu bar app."""
        super().__init__("🔴🦞", quit_button=None)  # type: ignore[arg-type]  # rumps accepts None

        # Paths - use project-local directories (resolve to absolute paths)
        self.project_dir = Path(__file__).parent.resolve()
        self.runtime_dir = self.project_dir / "runtime"
        self.logs_dir = self.project_dir / "logs"

        # Speech output directory - use hidden directory in user's home for reliable permissions
        self.speech_output_dir = Path.home() / ".molt-speak" / "runtime"

        # Ensure directories exist with proper permissions
        self.runtime_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.speech_output_dir.mkdir(parents=True, exist_ok=True, mode=0o755)

        # PID files (in runtime dir)
        self.integration_pid_file = self.runtime_dir / "integration.pid"
        self.mouth_pid_file = self.runtime_dir / "mouth.pid"
        self.ears_pid_file = self.runtime_dir / "ears.pid"

        # State
        self.integration_running = False
        self.mouth_running = False
        self.ears_running = False
        self.initializing = True  # Flag to prevent crashes during startup
        self._current_voice = None  # Cache for current voice selection

        # Configuration manager
        self.config = ConfigManager()

        # Build initial menu
        self.build_menu()

        # Start status update timer
        self.timer = rumps.Timer(self.update_status, 2.0)
        self.timer.start()

        # Auto-start voice loop after a short delay using threading
        import threading
        def delayed_start():
            # Must set initializing to False BEFORE calling auto_start
            # otherwise on_start_all will return early due to the guard
            self.initializing = False
            self.auto_start_voice_loop()
        threading.Timer(1.0, delayed_start).start()

        logger.info("Unified Voice Loop Menu Bar initialized")

    def build_menu(self):
        """Build the menu structure."""
        try:
            self.menu.clear()
        except Exception:
            return  # Menu not ready yet

        all_running = self.integration_running and self.mouth_running and self.ears_running

        # Start/Stop Molt Speak
        if all_running:
            self.menu.add(rumps.MenuItem("⏹️  Stop Molt Speak", callback=self.on_stop_all))
        else:
            self.menu.add(rumps.MenuItem("▶️  Start Molt Speak", callback=self.on_start_all))

        self.menu.add(rumps.separator)

        # Voice selection submenu
        voice_menu = rumps.MenuItem("🎤 Voice")
        current_voice = self.get_current_voice()

        # Voice categories
        voice_categories = [
            ("🇺🇸 American", [
                ("Samantha", "Female (default)"),
                ("Alex", "Male (default)"),
                ("Tom", "Male"),
                ("Allison", "Female"),
                ("Ava", "Female"),
                ("Zoe", "Female"),
                ("Nicky", "Female"),
                ("Susan", "Female"),
                ("Evan", "Male"),
                ("Nathan", "Male"),
            ]),
            ("🇬🇧 British", [
                ("Daniel", "Male"),
                ("Kate", "Female"),
                ("Oliver", "Male"),
                ("Serena", "Female"),
                ("Stephanie", "Female"),
            ]),
            ("🇦🇺 Australian", [
                ("Karen", "Female"),
                ("Lee", "Male"),
            ]),
            ("🇮🇪 Irish", [
                ("Moira", "Female"),
            ]),
            ("🇿🇦 South African", [
                ("Tessa", "Female"),
            ]),
            ("🇮🇳 Indian", [
                ("Rishi", "Male"),
                ("Veena", "Female"),
            ]),
            ("🌍 Other English", [
                ("Fiona", "Scottish female"),
                ("Martha", "Female"),
            ]),
        ]

        for category_name, voices in voice_categories:
            category_menu = rumps.MenuItem(category_name)
            for voice_name, description in voices:
                check = "✓ " if voice_name == current_voice else "   "
                item = rumps.MenuItem(
                    f"{check}{voice_name} - {description}",
                    callback=lambda s, v=voice_name: self.on_select_voice(v)
                )
                category_menu.add(item)
            voice_menu.add(category_menu)

        voice_menu.add(rumps.separator)
        voice_menu.add(rumps.MenuItem("🔊 Test Current Voice", callback=self.on_test_voice))
        voice_menu.add(rumps.MenuItem("📋 List All System Voices", callback=self.on_list_voices))

        self.menu.add(voice_menu)

        # Honorific toggle (sir/madam)
        current_honorific = self.get_current_honorific()
        honorific_label = f"🎩 Called: {current_honorific.title()}"
        self.menu.add(rumps.MenuItem(honorific_label, callback=self.on_toggle_honorific))

        self.menu.add(rumps.separator)

        # Quit
        self.menu.add(rumps.MenuItem("Quit", callback=self.on_quit))

    def on_select_voice(self, voice_name):
        """Select a specific voice from the menu."""
        try:
            # Save voice setting to config file
            self.config.preferred_voice = voice_name
            # Also save to runtime/voice.conf for backwards compatibility
            voice_file = self.runtime_dir / "voice.conf"
            voice_file.write_text(voice_name)
            # Update cached value
            self._current_voice = voice_name
            logger.info(f"Voice selected: {voice_name}")
        except Exception as e:
            logger.error(f"Failed to save voice setting: {e}")
            rumps.alert("Error", f"Failed to save voice setting: {e}")
            return

        # Update menu immediately to show the change
        self.build_menu()

        # Restart voice loop if running (no popup notification)
        if self.mouth_running:
            import threading
            def restart_voice_loop():
                try:
                    # Stop current voice loop
                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                    subprocess.run([str(stop_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    # Start with new voice
                    start_script = self.project_dir / "scripts" / "start_voice_loop.sh"
                    subprocess.run([str(start_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    logger.info(f"Voice loop restarted with voice: {voice_name}")

                    # Test the new voice by writing a test message
                    time.sleep(0.5)  # Brief delay to let voice loop restart
                    speech_file = self.speech_output_dir / "speech_output.txt"
                    try:
                        speech_file.write_text("I've changed voices. How is this?")
                        logger.info("Voice test message written to speech output")
                    except Exception as e:
                        logger.error(f"Failed to write voice test message: {e}")
                except Exception as e:
                    logger.error(f"Failed to restart voice loop: {e}")
            threading.Thread(target=restart_voice_loop, daemon=True).start()

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
        try:
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
                self.title = "🟢🦞"  # Green circle for active
            else:
                self.title = "🔴🦞"  # Red circle for inactive

            # Rebuild menu if anything changed
            if (integration_was_running != self.integration_running or
                mouth_was_running != self.mouth_running or
                ears_was_running != self.ears_running):
                self.build_menu()
        except Exception as e:
            logger.warning(f"Error updating status: {e}")

    def auto_start_voice_loop(self, sender=None):
        """Auto-start voice loop on app launch if not already running."""
        # Check if already running
        all_running = (self.check_process(self.integration_pid_file) and
                      self.check_process(self.mouth_pid_file) and
                      self.check_process(self.ears_pid_file))

        if not all_running:
            logger.info("Auto-starting voice loop...")
            self.on_start_all(sender)
        else:
            logger.info("Voice loop already running, skipping auto-start")

    def on_start_all(self, sender):
        """Start the complete voice loop."""
        if getattr(self, 'initializing', False):
            return  # Don't start during initialization
        try:
            logger.info("Starting voice loop...")

            # Run start script
            script_path = self.project_dir / "scripts" / "start_voice_loop.sh"
            result = subprocess.run(
                [str(script_path)],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Don't show notification to avoid macOS notification spam
                logger.info("Voice loop started successfully")
                self.update_status(None)

                # Inject short instruction to read the instructions file
                import threading
                def delayed_injection():
                    time.sleep(1.0)
                    self.inject_agent_instructions()
                threading.Thread(target=delayed_injection, daemon=True).start()

            else:
                logger.error(f"Failed to start voice loop: {result.stderr}")
                # Only show alert if called from main thread (not auto-start)
                if sender is not None:
                    rumps.alert(
                        "Start Failed",
                        f"Failed to start voice loop:\n\n{result.stderr}"
                    )
        except Exception as e:
            logger.error(f"Error starting voice loop: {e}")
            # Only show alert if called from main thread (not auto-start)
            if sender is not None:
                rumps.alert("Error", f"Failed to start: {e}")

    def on_stop_all(self, sender):
        """Stop the complete voice loop."""
        if getattr(self, 'initializing', False):
            return  # Don't stop during initialization
        try:
            logger.info("Stopping voice loop...")

            # Inject close message to tell agent voice mode is off
            self.inject_close_message()

            # Run stop script
            script_path = self.project_dir / "scripts" / "stop_voice_loop.sh"
            result = subprocess.run(
                [str(script_path)],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Clear speech output queue to prevent old messages on restart
                speech_output = self.speech_output_dir / "speech_output.txt"
                try:
                    speech_output.write_text("")
                    logger.info("Cleared speech output queue")
                except Exception as e:
                    logger.warning(f"Failed to clear speech queue: {e}")

                # Notification removed
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
        """Start OpenClaw Mouth standalone."""
        self._start_component("mouth", "OpenClaw Mouth",
                             "cd open_mouth && python main.py")

    def on_start_ears(self, sender):
        """Start OpenClaw Ears standalone."""
        self._start_component("ears", "OpenClaw Ears",
                             "cd open_ears && python main.py")

    def on_start_mouth_only(self, sender):
        """Start Mouth only mode (TTS output, no voice input)."""
        # Stop ears if running
        if self.ears_running:
            self._stop_component(self.ears_pid_file, "OpenClaw Ears")

        # Start integration if not running
        if not self.integration_running:
            self._start_component("integration", "Integration Coordinator",
                                 "python main.py")

        # Start mouth
        self._start_component("mouth", "OpenClaw Mouth",
                             "cd open_mouth && python main.py")
        logger.info("Started Mouth-only mode (TTS output)")

    def on_start_ears_only(self, sender):
        """Start Ears only mode (voice input, no TTS output)."""
        # Stop mouth if running
        if self.mouth_running:
            self._stop_component(self.mouth_pid_file, "OpenClaw Mouth")

        # Start ears
        self._start_component("ears", "OpenClaw Ears",
                             "cd open_ears && python main.py")
        logger.info("Started Ears-only mode (voice input)")

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
            # Notification removed
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
                # Notification removed
                self.update_status(None)
            else:
                rumps.alert("Not Running", f"{display_name} is not currently running")
        except Exception as e:
            logger.error(f"Error stopping {display_name}: {e}")
            rumps.alert("Error", f"Failed to stop {display_name}: {e}")

    def on_view_integration_log(self, sender):
        """View integration log."""
        self._open_log(self.logs_dir / "integration.log", "Integration")

    def on_view_mouth_log(self, sender):
        """View mouth log."""
        self._open_log(self.logs_dir / "mouth.log", "Mouth")

    def on_view_ears_log(self, sender):
        """View ears log."""
        self._open_log(self.logs_dir / "ears.log", "Ears")

    def on_view_all_logs(self, sender):
        """View all logs in separate tabs."""
        logs = [
            (self.logs_dir / "integration.log", "Integration"),
            (self.logs_dir / "mouth.log", "Mouth"),
            (self.logs_dir / "ears.log", "Ears")
        ]

        for log_path, name in logs:
            if log_path.exists():
                self._open_log(log_path, name)

    def on_open_ears_visualizer(self, sender):
        """Open Ears visualizer in new Terminal window."""
        if not self.ears_running:
            rumps.alert("Not Running", "OpenClaw Ears is not currently running.\nStart the voice loop first.")
            return

        ears_log = self.logs_dir / "ears.log"
        if not ears_log.exists():
            rumps.alert("Log Not Found", f"Ears log not found at {ears_log}")
            return

        # Open Terminal with tail showing the visualizer output
        cmd = f"tail -f {ears_log}"
        script = f'''tell application "Terminal"
    activate
    do script "{cmd}"
end tell'''
        subprocess.run(["osascript", "-e", script])
        # Notification removed

    def on_open_mouth_visualizer(self, sender):
        """Open Mouth visualizer in new Terminal window."""
        if not self.mouth_running:
            rumps.alert("Not Running", "OpenClaw Mouth is not currently running.\nStart the voice loop first.")
            return

        mouth_log = self.logs_dir / "mouth.log"
        if not mouth_log.exists():
            rumps.alert("Log Not Found", f"Mouth log not found at {mouth_log}")
            return

        # Open Terminal showing mouth status and TTS activity
        cmd = f"tail -f {mouth_log}"
        script = f'''tell application "Terminal"
    activate
    do script "{cmd}"
end tell'''
        subprocess.run(["osascript", "-e", script])
        # Notification removed

    def on_open_both_visualizers(self, sender):
        """Open both visualizers."""
        self.on_open_ears_visualizer(sender)
        self.on_open_mouth_visualizer(sender)

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

    def inject_agent_instructions(self):
        """Write instructions to file and tell agent to read it."""
        # Dynamic path to speech output file
        speech_file = str(self.speech_output_dir / "speech_output.txt")

        # Path where agent instructions will be saved
        agent_instructions_file = self.speech_output_dir / "agent_instructions.txt"

        # Read the full AGENT_INSTRUCTIONS.txt file
        instructions_file = self.project_dir / "AGENT_INSTRUCTIONS.txt"
        try:
            instruction = instructions_file.read_text()
            # Replace template placeholders
            instruction = instruction.replace("{{SPEECH_FILE}}", speech_file)
            instruction = instruction.replace("{{HONORIFIC}}", self.get_current_honorific())

            # Write instructions to the molt-speak directory
            agent_instructions_file.write_text(instruction)
            logger.info(f"Wrote agent instructions to: {agent_instructions_file}")
        except Exception as e:
            logger.error(f"Failed to write agent instructions: {e}")
            # Fallback to minimal instruction
            instruction = f"VOICE LOOP ACTIVE. Echo responses to: {speech_file}"
            try:
                agent_instructions_file.write_text(instruction)
            except Exception:
                pass

        # Create a short message indicating voice mode is active
        instruction = f"[MOLT SPEAK: ONLINE] - Do not respond until after you've read instructions at {agent_instructions_file}"

        # Read window pattern from open_ears settings
        window_pattern = "openclaw"
        env_file = self.project_dir / "open_ears" / ".env"
        if env_file.exists():
            try:
                for line in env_file.read_text().split('\n'):
                    if line.startswith('TARGET_WINDOW_PATTERN='):
                        window_pattern = line.split('=', 1)[1].strip().strip('"')
                        break
            except Exception:
                pass

        try:
            # Build AppleScript command that sends text directly to TUI
            # Replace newlines with AppleScript's 'return' character for proper multiline handling
            # Split into lines and use AppleScript concatenation
            lines = instruction.split('\n')
            # Escape quotes and backslashes in each line for AppleScript
            escaped_lines = [line.replace('\\', '\\\\').replace('"', '\\"') for line in lines]
            # Build AppleScript string with proper line concatenation using 'return'
            if len(escaped_lines) == 1:
                applescript_text = f'"{escaped_lines[0]}"'
            else:
                # Join lines with AppleScript's 'return' character
                applescript_text = ' & return & '.join(f'"{line}"' for line in escaped_lines)

            logger.info(f"Injecting instructions, looking for window pattern: {window_pattern}")
            logger.info(f"Instructions length: {len(instruction)} chars, {len(lines)} lines")

            # AppleScript: Use do script / write text to inject directly (no bracketed paste warning)
            applescript = f'''
-- Save the currently active app to restore later
set previousApp to ""
tell application "System Events"
    set previousApp to name of first application process whose frontmost is true
end tell

-- Try to find the target terminal window
set targetApp to ""
set foundIt to false
set targetRef to missing value

-- Only support Terminal.app (iTerm2 removed to simplify)
tell application "Terminal"
    repeat with w in windows
        if name of w contains "{window_pattern}" then
            set targetRef to selected tab of w
            set foundIt to true
            exit repeat
        end if
    end repeat
    -- No fallback: only inject into explicitly matched window

    -- Send text directly to TUI (like ears does)
    if foundIt then
        do script {applescript_text} in targetRef
    end if
end tell

-- Restore focus to the previous app
if foundIt then
    delay 0.1
    if previousApp is not "" then
        tell application previousApp to activate
    end if
    return "success"
else
    return "no_terminal_found"
end if
'''
            # Debug: Save AppleScript to file for inspection
            import os
            debug_path = os.path.expanduser('~/.openspeak/last_applescript.txt')
            try:
                with open(debug_path, 'w') as f:
                    f.write(applescript)
                logger.info(f"AppleScript saved to {debug_path} for inspection")
            except Exception:
                pass

            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output == "success":
                    logger.info("Injected agent instructions via do script (no paste warning)")
                else:
                    logger.warning(f"Could not find terminal window: {output}")
            else:
                logger.warning(f"Failed to inject: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning("Timed out trying to inject instructions")
        except Exception as e:
            logger.warning(f"Error injecting agent instructions: {e}")

    def inject_close_message(self):
        """Inject close message to tell agent voice mode is off."""
        # Path where closing instructions will be saved
        closing_instructions_file = self.speech_output_dir / "agent_closing_instructions.txt"

        # Read the closing instructions template
        close_template_file = self.project_dir / "AGENT_INSTRUCTIONS_CLOSE.txt"
        try:
            closing_instructions = close_template_file.read_text()
            # Write closing instructions to the molt-speak directory
            closing_instructions_file.write_text(closing_instructions)
            logger.info(f"Wrote closing instructions to: {closing_instructions_file}")
        except Exception as e:
            logger.error(f"Failed to write closing instructions: {e}")
            # Fallback to minimal instruction
            closing_instructions_file.write_text("Voice mode disabled. Resume normal text-only responses.")

        # Create a short message telling the agent to read the closing instructions
        message = f"[MOLT SPEAK: OFFLINE] - Read the closing prompt at {closing_instructions_file}"

        # Read window pattern from open_ears settings
        window_pattern = "openclaw"
        env_file = self.project_dir / "open_ears" / ".env"
        if env_file.exists():
            try:
                for line in env_file.read_text().split('\n'):
                    if line.startswith('TARGET_WINDOW_PATTERN='):
                        window_pattern = line.split('=', 1)[1].strip().strip('"')
                        break
            except Exception:
                pass

        try:
            # Escape for AppleScript
            escaped_message = message.replace('\\', '\\\\').replace('"', '\\"')

            logger.info(f"Injecting close message, looking for window pattern: {window_pattern}")

            applescript = f'''
tell application "Terminal"
    repeat with w in windows
        if name of w contains "{window_pattern}" then
            set targetRef to selected tab of w
            do script "{escaped_message}" in targetRef
            return "success"
        end if
    end repeat
    return "no_terminal_found"
end tell
'''
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip() == "success":
                logger.info("Injected close message successfully")
            else:
                logger.warning(f"Could not inject close message: {result.stderr}")
        except Exception as e:
            logger.warning(f"Error injecting close message: {e}")

    def inject_honorific_change_message(self, new_honorific):
        """Inject message to tell agent about honorific change and speak it."""
        message = f"I'll call you {new_honorific}."

        # Write to speech output file so it gets spoken (append, don't overwrite)
        try:
            speech_file = self.speech_output_dir / "speech_output.txt"
            with open(speech_file, 'a') as f:
                f.write(message + "\n")
            logger.info(f"Wrote honorific change to speech output: {message}")
        except Exception as e:
            logger.error(f"Failed to write honorific change to speech output: {e}")

        # Also paste into terminal for the agent to see
        window_pattern = "openclaw"
        env_file = self.project_dir / "open_ears" / ".env"
        if env_file.exists():
            try:
                for line in env_file.read_text().split('\n'):
                    if line.startswith('TARGET_WINDOW_PATTERN='):
                        window_pattern = line.split('=', 1)[1].strip().strip('"')
                        break
            except Exception:
                pass

        try:
            # Escape for AppleScript
            escaped_message = message.replace('\\', '\\\\').replace('"', '\\"')

            logger.info(f"Injecting honorific change message into terminal: {message}")

            applescript = f'''
tell application "Terminal"
    repeat with w in windows
        if name of w contains "{window_pattern}" then
            set targetRef to selected tab of w
            do script "{escaped_message}" in targetRef
            return "success"
        end if
    end repeat
    return "no_terminal_found"
end tell
'''
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip() == "success":
                logger.info("Injected honorific change message into terminal successfully")
            else:
                logger.warning(f"Could not inject honorific change message into terminal: {result.stderr}")
        except Exception as e:
            logger.warning(f"Error injecting honorific change message into terminal: {e}")

    def on_open_config_dir(self, sender):
        """Open project runtime directory."""
        subprocess.run(["open", str(self.runtime_dir)])

    def get_current_voice(self):
        """Get the current voice setting."""
        # Use cached value if available
        if self._current_voice is not None:
            return self._current_voice
        # Otherwise read from config
        try:
            voice = self.config.preferred_voice
            # Convert Edge-TTS voice to macOS voice name if needed
            # For now, just cache and return
            self._current_voice = voice
            return voice
        except Exception:
            return "Samantha"

    def get_current_honorific(self):
        """Get the current honorific setting (sir/madam)."""
        try:
            return self.config.user_title
        except Exception:
            return "sir"

    def on_toggle_honorific(self, sender):
        """Toggle between sir and madam."""
        current = self.get_current_honorific()
        new_honorific = "madam" if current == "sir" else "sir"

        try:
            # Save honorific setting to config file
            self.config.user_title = new_honorific
            # Also save to runtime/honorific.conf for backwards compatibility
            honorific_file = self.runtime_dir / "honorific.conf"
            honorific_file.write_text(new_honorific)
            logger.info(f"Honorific changed to: {new_honorific}")

            # Rebuild menu to update label
            self.build_menu()

            # Inject a message telling the agent about the change
            # Always try to inject, even if status check shows not running
            # (status might not be updated yet due to 2-second polling interval)
            self.inject_honorific_change_message(new_honorific)

        except Exception as e:
            logger.error(f"Error changing honorific: {e}")
            rumps.alert("Error", f"Failed to change honorific: {e}")

    def on_change_voice(self, voice_name):
        """Change the TTS voice (called programmatically, not from toggle)."""
        try:
            # Save voice setting to config file
            self.config.preferred_voice = voice_name
            # Also save to runtime/voice.conf for backwards compatibility
            voice_file = self.runtime_dir / "voice.conf"
            voice_file.write_text(voice_name)
            # Update cached value
            self._current_voice = voice_name
            logger.info(f"Voice changed to: {voice_name}")

            # Update menu immediately
            self.build_menu()

            # Restart voice loop in background if running
            if self.mouth_running:
                import threading
                def restart_voice_loop():
                    try:
                        stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                        subprocess.run([str(stop_script)], cwd=str(self.project_dir),
                                       capture_output=True, timeout=15)
                        start_script = self.project_dir / "scripts" / "start_voice_loop.sh"
                        subprocess.run([str(start_script)], cwd=str(self.project_dir),
                                       capture_output=True, timeout=15)
                        logger.info(f"Voice loop restarted with voice: {voice_name}")

                        # Test the new voice by writing a test message
                        time.sleep(0.5)  # Brief delay to let voice loop restart
                        speech_file = self.speech_output_dir / "speech_output.txt"
                        try:
                            speech_file.write_text("I've changed voices. How is this?")
                            logger.info("Voice test message written to speech output")
                        except Exception as e:
                            logger.error(f"Failed to write voice test message: {e}")
                    except Exception as e:
                        logger.error(f"Failed to restart voice loop: {e}")
                threading.Thread(target=restart_voice_loop, daemon=True).start()

        except Exception as e:
            logger.error(f"Error changing voice: {e}")
            rumps.alert("Error", f"Failed to change voice: {e}")

    def on_test_voice(self, sender):
        """Test the current voice."""
        voice = self.get_current_voice()
        try:
            subprocess.run(
                ["say", "-v", voice, f"Hello, this is the {voice} voice."],
                check=True
            )
        except Exception as e:
            rumps.alert("Voice Test Failed", f"Could not test voice {voice}: {e}")

    def on_list_voices(self, sender):
        """List all available system voices."""
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse and format voice list
            voices = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    # Format: "VoiceName    locale    # description"
                    parts = line.split("#")
                    name_locale = parts[0].strip() if parts else line
                    voices.append(name_locale.split()[0] if name_locale else "")

            voice_list = ", ".join(v for v in voices if v)
            # Copy to clipboard
            subprocess.run(['pbcopy'], input=voice_list.encode(), check=True)
            rumps.alert(
                "Available Voices",
                f"Found {len(voices)} voices.\n\nVoice names copied to clipboard.\n\nTo download more voices:\nSystem Settings → Accessibility → Spoken Content → System Voice → Manage Voices"
            )
        except Exception as e:
            rumps.alert("Error", f"Failed to list voices: {e}")

    def on_view_instructions(self, sender):
        """View agent instructions and copy to clipboard."""
        instructions_file = self.runtime_dir / "agent_instructions.active"

        if instructions_file.exists():
            # Read instructions
            instructions = instructions_file.read_text()

            # Copy to clipboard
            subprocess.run(["pbcopy"], input=instructions.encode())

            # Show instructions in TextEdit
            subprocess.run(["open", "-a", "TextEdit", str(instructions_file)])

            # Notify user
            rumps.alert(
                "Instructions Copied!",
                "Agent instructions have been:\n• Opened in TextEdit\n• Copied to clipboard\n\nPaste into your OpenClaw TUI with Cmd+V"
            )
        else:
            rumps.alert(
                "Instructions Not Available",
                "Agent instructions are created when the voice loop starts.\n\nStart the voice loop to see the instructions."
            )

    def on_inject_instructions(self, sender):
        """Manually inject agent instructions into TUI."""
        if not (self.integration_running and self.mouth_running):
            rumps.alert(
                "Voice Loop Not Running",
                "Start the voice loop first before injecting instructions."
            )
            return

        self.inject_agent_instructions()
        speech_file = str(self.speech_output_dir / "speech_output.txt")
        rumps.alert(
            "Instructions Injected",
            f"Voice loop instructions have been sent to the agent TUI.\n\n"
            f"The agent should now know to write responses to:\n"
            f"{speech_file}"
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

            # Notification removed

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
        self.on_stop_all(None)
        force_cleanup()
        rumps.quit_application()


def force_cleanup():
    """Force kill all voice loop processes on exit."""
    project_dir = Path(__file__).parent
    runtime_dir = project_dir / "runtime"

    # Stop processes using PID files (safer than pattern matching)
    pid_files = [
        (runtime_dir / "audio.pid", "Unified Audio"),
        (runtime_dir / "mouth.pid", "Mouth"),
        (runtime_dir / "ears.pid", "Ears"),
        (runtime_dir / "integration.pid", "Integration"),
    ]

    for pid_file, name in pid_files:
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to {name} (PID: {pid})")
                # Wait briefly for graceful shutdown
                time.sleep(0.5)
                # Force kill if still running
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Already stopped
                pid_file.unlink()
            except (ValueError, ProcessLookupError, PermissionError) as e:
                logger.debug(f"Could not stop {name}: {e}")
                if pid_file.exists():
                    pid_file.unlink()

    # Also try the stop script as backup (but it won't kill Claude Code anymore)
    stop_script = project_dir / "scripts" / "stop_voice_loop.sh"
    if stop_script.exists():
        subprocess.run([str(stop_script)], capture_output=True, cwd=str(project_dir))


def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signum}, cleaning up...")
    force_cleanup()
    import sys
    sys.exit(0)


def main():
    """Main entry point."""
    # Register cleanup handlers
    atexit.register(force_cleanup)
    # Only handle SIGTERM, not SIGINT (to avoid interfering with parent process)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        app = VoiceLoopMenuBar()
        app.run()
    finally:
        # Ensure cleanup even if app.run() throws
        force_cleanup()


if __name__ == "__main__":
    main()
