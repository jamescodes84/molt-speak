#!/usr/bin/env python3
"""
Unified macOS menu bar application for OpenClaw Voice Loop.

Controls:
- Integration Coordinator (echo prevention)
- OpenClaw Mouth (voice output)
- OpenClaw Ears (voice input)
"""

import logging
import re
import shlex
import subprocess
import os
import signal
import time
import atexit
import objc
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Force PyObjC to initialize properly BEFORE importing rumps
# This fixes menu bar not appearing on some Macs
try:
    from Foundation import NSObject, NSLog
    from AppKit import NSApplication, NSStatusBar, NSVariableStatusItemLength
    # Initialize NSApplication shared instance early
    _app = NSApplication.sharedApplication()
    # Force status bar to initialize
    _status_bar = NSStatusBar.systemStatusBar()
    NSLog("Menu bar initialization: NSApplication and NSStatusBar ready")
except ImportError as e:
    print(f"Warning: Could not pre-initialize AppKit: {e}")

import rumps

from src.config.config_manager import ConfigManager

# Analytics
try:
    from src.services.analytics import get_analytics, initialize_analytics
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Analytics not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximum characters for alert messages to prevent dialogs running off screen
_ALERT_MAX_CHARS = 500


def _truncated_alert(title, message, **kwargs):
    """Show a rumps alert with message truncated to fit on screen."""
    if message and len(message) > _ALERT_MAX_CHARS:
        message = message[:_ALERT_MAX_CHARS] + "\n\n…(truncated — see logs for full details)"
    return rumps.alert(title, message, **kwargs)


class _MenuOpenDelegate(NSObject):
    """NSMenuDelegate that swaps lobster/robot icon on menu open/close."""

    def initWithApp_(self, app):
        self = objc.super(_MenuOpenDelegate, self).init()
        if self is not None:
            self.app = app
        return self

    def menuWillOpen_(self, menu):
        self.app._menu_is_open = True
        self.app._refresh_icon()

    def menuDidClose_(self, menu):
        self.app._menu_is_open = False
        self.app._refresh_icon()


class VoiceLoopMenuBar(rumps.App):
    """Unified menu bar application for OpenClaw Voice Loop."""

    def __init__(self):
        """Initialize menu bar app."""
        # Paths - use project-local directories (resolve to absolute paths)
        # MUST be set BEFORE calling super().__init__ for menu building
        self.project_dir = Path(__file__).parent.resolve()
        self.runtime_dir = self.project_dir / "runtime"
        self.logs_dir = self.project_dir / "logs"

        # Speech output directory - use project runtime directory
        self.speech_output_dir = self.runtime_dir

        # Ensure directories exist with proper permissions
        self.runtime_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.speech_output_dir.mkdir(parents=True, exist_ok=True, mode=0o755)

        # Create /tmp/speak.txt symlink (space-free path for agent's bash commands)
        # The agent echoes to /tmp/speak.txt which symlinks to the real speech file.
        # This avoids shell issues with spaces in the project path.
        try:
            speak_symlink = Path("/tmp/speak.txt")
            speak_symlink.unlink(missing_ok=True)
            speak_symlink.symlink_to(self.speech_output_dir / "speech_output.txt")
        except OSError:
            pass  # Best-effort; start_voice_loop.sh also creates this

        # PID files (in runtime dir)
        self.integration_pid_file = self.runtime_dir / "integration.pid"
        self.mouth_pid_file = self.runtime_dir / "mouth.pid"
        self.ears_pid_file = self.runtime_dir / "ears.pid"

        # Status files for real-time indicators
        self.ears_status_file = self.runtime_dir / "ears_status.txt"

        # State
        self.integration_running = False
        self.mouth_running = False
        self.ears_running = False
        self.initializing = True  # Flag to prevent crashes during startup
        self._current_voice = None  # Cache for current voice selection
        self._menu_is_open = False  # Tracks menu open/close for icon swap
        self._recovery_needed = False  # True when background recovery polling is active
        self._recovery_timer = None   # rumps.Timer for recovery polling

        # Configuration manager
        self.config = ConfigManager()

        # Analytics (respect POSTHOG_DISABLED env var)
        self.analytics = None
        if ANALYTICS_AVAILABLE:
            try:
                disabled = os.getenv("POSTHOG_DISABLED", "false").lower() == "true"
                self.analytics = initialize_analytics(disabled=disabled)
                self.analytics.track_event("menu_bar_started")
            except Exception as e:
                logger.warning(f"Analytics initialization failed: {e}")

        # Detect display configuration for adaptive menu bar setup
        self._display_info = self._detect_display_config()
        logger.info("Display config: %s", self._display_info)

        # Initialize rumps app with a simple title first
        super().__init__("MoltSpeak", quit_button=None)  # type: ignore
        self.title = "🦞"

        # Build initial menu
        self.build_menu()

        # Start status update timer (0.1s for responsive speech indicator)
        self.timer = rumps.Timer(self.update_status, 0.1)
        self.timer.start()

        # Schedule status item fix after app starts (rumps creates status item during run())
        self._status_fix_timer = rumps.Timer(self._delayed_status_fix, 0.5)
        self._status_fix_timer.start()

        # Auto-start voice loop after a short delay using threading
        import threading
        def delayed_start():
            # Must set initializing to False BEFORE calling auto_start
            # otherwise on_start_all will return early due to the guard
            self.initializing = False
            self.auto_start_voice_loop()
        threading.Timer(1.0, delayed_start).start()

        # Check for updates after startup (non-blocking)
        # HTTP check runs on background thread, UI shown via timer on main thread
        self._pending_update = None  # Store update info from background thread
        self._pending_alert = None   # Store alert for main-thread display
        def check_updates():
            time.sleep(2.0)  # Wait for app to fully initialize
            self._fetch_update_info()
        threading.Thread(target=check_updates, daemon=True).start()

        # Timer polls for update result and shows dialog on main thread
        self._update_ui_timer = rumps.Timer(self._show_pending_update, 1.0)
        self._update_ui_timer.start()

        # Timer polls for queued alerts and shows them on main thread
        self._alert_ui_timer = rumps.Timer(self._show_pending_alert, 0.5)
        self._alert_ui_timer.start()

        logger.info("Menu bar app initialized with title: %s", self.title)
        logger.info("Unified Voice Loop Menu Bar initialized")

    def _delayed_status_fix(self, timer):
        """Fix status item visibility after app has fully started."""
        timer.stop()  # Only run once
        logger.info("Running delayed status fix...")

        # Now the status item should exist
        self._setup_menu_bar_item(self._display_info)
        self._force_status_item_visible()

        # Install menu delegate for lobster/robot icon swap
        try:
            if hasattr(self, '_nsapp') and hasattr(self._nsapp, 'nsstatusitem'):
                ns_menu = self._nsapp.nsstatusitem.menu()
                if ns_menu:
                    self._menu_delegate = _MenuOpenDelegate.alloc().initWithApp_(self)
                    ns_menu.setDelegate_(self._menu_delegate)
                    logger.info("Menu delegate installed for icon swap")
        except Exception as e:
            logger.debug(f"Could not install menu delegate: {e}")

        logger.info("Delayed status fix complete")

    def _detect_display_config(self) -> dict:
        """Detect display configuration to adapt menu bar behavior."""
        info = {
            "has_internal": False,
            "has_external": False,
            "is_laptop": False,
            "main_display_internal": False,
        }
        try:
            from AppKit import NSScreen
            import subprocess

            # Check if this is a laptop by looking for battery
            result = subprocess.run(
                ["system_profiler", "SPPowerDataType"],
                capture_output=True, text=True, timeout=5
            )
            is_laptop = "Battery" in result.stdout
            info["is_laptop"] = is_laptop

            screens = NSScreen.screens()
            logger.info(f"Detected {len(screens)} screen(s), is_laptop={is_laptop}")

            for i, screen in enumerate(screens):
                desc = screen.deviceDescription()
                # Try to get display name/info
                screen_num = desc.get("NSScreenNumber", i)
                frame = screen.frame()
                logger.info(f"Screen {i}: {frame.size.width}x{frame.size.height}, screenNum={screen_num}")

            # If it's a laptop with only one screen, assume internal display
            if is_laptop and len(screens) == 1:
                info["has_internal"] = True
                info["main_display_internal"] = True
            elif is_laptop and len(screens) > 1:
                # Multiple screens on laptop = has external
                info["has_internal"] = True
                info["has_external"] = True
                # Main screen is likely external if using clamshell mode
            else:
                # Desktop Mac
                info["has_external"] = True

        except Exception as e:
            logger.warning("Could not detect display config: %s", e)

        return info

    def _setup_menu_bar_item(self, display_info: dict):
        """Set up menu bar item adaptively based on display configuration."""
        # Try multiple approaches in order of reliability
        success = False

        # Method 1: Direct NSStatusItem manipulation (most reliable on problematic displays)
        if display_info.get("main_display_internal") and not success:
            success = self._try_direct_status_item()

        # Method 2: Simple title (fallback)
        if not success:
            self.title = "🦞"
            success = True
            logger.info("Using simple title: 🦞")

        # Force visibility regardless of method
        self._force_status_item_visible()

    def _try_direct_status_item(self) -> bool:
        """Try creating status item directly via AppKit."""
        try:
            from AppKit import NSStatusBar, NSFont

            # Wait for rumps to create its status item, then configure it
            if hasattr(self, '_nsapp') and hasattr(self._nsapp, 'nsstatusitem'):
                status_item = self._nsapp.nsstatusitem
                if status_item:
                    # Get the button and set title directly
                    button = status_item.button()
                    if button:
                        button.setTitle_("🦞")
                        logger.info("Button title set to: 🦞")

                    # Configure status item
                    status_item.setVisible_(True)
                    status_item.setLength_(-1)  # Variable length

                    logger.info("Direct status item setup successful")
                    return True
        except Exception as e:
            logger.warning("Direct status item setup failed: %s", e)
        return False

    def _force_status_item_visible(self):
        """Force the status item to be visible."""
        try:
            from AppKit import NSStatusBar
            if hasattr(self, '_nsapp') and hasattr(self._nsapp, 'nsstatusitem'):
                status_item = self._nsapp.nsstatusitem
                if status_item:
                    status_item.setVisible_(True)
                    # Also ensure length is set
                    status_item.setLength_(-1)  # Variable length
                    logger.info("Status item forced visible, length=-1")
        except Exception as e:
            logger.warning("Could not force status item visible: %s", e)

    def _set_title(self, new_title: str):
        """Set title via both rumps and AppKit to ensure it sticks."""
        self.title = new_title
        try:
            if hasattr(self, '_nsapp') and hasattr(self._nsapp, 'nsstatusitem'):
                status_item = self._nsapp.nsstatusitem
                if status_item:
                    button = status_item.button()
                    if button:
                        button.setTitle_(new_title)
        except Exception:
            pass

    def _is_user_speaking(self) -> bool:
        """Check if user is currently speaking by reading ears_status.txt.

        The file format is ``timestamp|status|amplitude``.  If the timestamp
        is older than 2 seconds we treat the data as stale (the ears process
        may have crashed or the file may be left over from a previous session).
        """
        try:
            if self.ears_status_file.exists():
                content = self.ears_status_file.read_text().strip()
                parts = content.split("|")
                if len(parts) >= 2:
                    # Staleness guard — ignore data older than 2 s
                    try:
                        ts = float(parts[0])
                        if time.time() - ts > 2.0:
                            return False
                    except (ValueError, IndexError):
                        return False
                    status = parts[1]
                    return status == "SPEECH_DETECTED"
        except Exception as e:
            logger.debug(f"Error reading ears status: {e}")
        return False

    @property
    def _mascot(self):
        """Return robot when menu is open, lobster when closed."""
        return "🤖" if self._menu_is_open else "🦞"

    def _refresh_icon(self):
        """Immediately refresh the icon based on current state."""
        all_running = self.integration_running and self.mouth_running and self.ears_running
        if all_running:
            if self._is_user_speaking():
                self._set_title(f"🔵{self._mascot}")
            else:
                self._set_title(f"🟢{self._mascot}")
        else:
            self._set_title(f"🔴{self._mascot}")

    def build_menu(self):
        """Build the menu structure."""
        try:
            # Clear all existing items by key to ensure full rebuild
            keys = list(self.menu.keys())
            for key in keys:
                try:
                    del self.menu[key]
                except Exception:
                    pass
            self.menu.clear()
        except Exception:
            return  # Menu not ready yet

        all_running = self.integration_running and self.mouth_running and self.ears_running

        # Start/Stop Molt Speak
        if all_running:
            self.menu.add(rumps.MenuItem("Stop Molt Speak", callback=self.on_stop_all))
        else:
            self.menu.add(rumps.MenuItem("Start Molt Speak", callback=self.on_start_all))

        self.menu.add(rumps.separator)

        # TTS Provider selection
        provider_menu = rumps.MenuItem("TTS Provider")
        current_provider = self.config.tts_provider

        edge_check = "✓ " if current_provider == "edge-tts" else "   "
        elo_check = "✓ " if current_provider == "elevenlabs" else "   "

        provider_menu.add(rumps.MenuItem(
            f"{edge_check}Edge-TTS (Free)",
            callback=lambda _: self.on_select_provider("edge-tts")
        ))
        provider_menu.add(rumps.MenuItem(
            f"{elo_check}ElevenLabs ($ API Key)",
            callback=lambda _: self.on_select_provider("elevenlabs")
        ))
        provider_menu.add(rumps.separator)
        provider_menu.add(rumps.MenuItem(
            "⚙️  Configure ElevenLabs...",
            callback=self.on_configure_elevenlabs
        ))

        self.menu.add(provider_menu)
        self.menu.add(rumps.separator)

        # Voice selection submenu - varies based on TTS provider
        voice_menu = rumps.MenuItem("Voice")

        if current_provider == "elevenlabs":
            # ElevenLabs: show available voices from API
            current_voice_id = self.config.elevenlabs_voice_id
            voices = self.get_elevenlabs_voices()

            if voices:
                for voice in voices:
                    voice_id = voice.get('voice_id', '')
                    voice_name = voice.get('name', 'Unknown')
                    check = "✓ " if voice_id == current_voice_id else "   "
                    item = rumps.MenuItem(
                        f"{check}{voice_name}",
                        callback=lambda s, vid=voice_id, vname=voice_name: self.on_select_elevenlabs_voice(vid, vname)
                    )
                    voice_menu.add(item)
                voice_menu.add(rumps.separator)
            else:
                voice_menu.add(rumps.MenuItem("(No voices found)", callback=None))
                voice_menu.add(rumps.separator)

            voice_menu.add(rumps.MenuItem("Test Voice", callback=self.on_test_elevenlabs_voice))
            voice_menu.add(rumps.MenuItem("Refresh Voices", callback=self.on_refresh_elevenlabs_voices))
        else:
            # Edge-TTS: show Edge-TTS voices
            current_voice = self.config.preferred_voice

            # Edge-TTS voice categories
            voice_categories = [
                ("🇺🇸 American", [
                    ("en-US-ChristopherNeural", "Male (default)"),
                    ("en-US-AriaNeural", "Female"),
                    ("en-US-JennyNeural", "Female"),
                    ("en-US-GuyNeural", "Male"),
                    ("en-US-DavisNeural", "Male"),
                    ("en-US-AmberNeural", "Female"),
                    ("en-US-AnaNeural", "Female child"),
                    ("en-US-BrandonNeural", "Male"),
                    ("en-US-CoraNeural", "Female"),
                    ("en-US-EricNeural", "Male"),
                ]),
                ("🇬🇧 British", [
                    ("en-GB-RyanNeural", "Male"),
                    ("en-GB-SoniaNeural", "Female"),
                    ("en-GB-LibbyNeural", "Female"),
                    ("en-GB-ThomasNeural", "Male"),
                    ("en-GB-MaisieNeural", "Female child"),
                ]),
                ("🇦🇺 Australian", [
                    ("en-AU-NatashaNeural", "Female"),
                    ("en-AU-WilliamNeural", "Male"),
                ]),
                ("🇮🇪 Irish", [
                    ("en-IE-EmilyNeural", "Female"),
                    ("en-IE-ConnorNeural", "Male"),
                ]),
                ("🇿🇦 South African", [
                    ("en-ZA-LeahNeural", "Female"),
                    ("en-ZA-LukeNeural", "Male"),
                ]),
                ("🇮🇳 Indian", [
                    ("en-IN-NeerjaNeural", "Female"),
                    ("en-IN-PrabhatNeural", "Male"),
                ]),
            ]

            for category_name, voices in voice_categories:
                category_menu = rumps.MenuItem(category_name)
                for voice_name, description in voices:
                    check = "✓ " if voice_name == current_voice else "   "
                    item = rumps.MenuItem(
                        f"{check}{voice_name.split('-')[-1]} - {description}",
                        callback=lambda s, v=voice_name: self.on_select_edge_voice(v)
                    )
                    category_menu.add(item)
                voice_menu.add(category_menu)

            voice_menu.add(rumps.separator)
            voice_menu.add(rumps.MenuItem("🔊 Test Current Voice", callback=self.on_test_edge_voice))

        self.menu.add(voice_menu)

        # Mic Sensitivity submenu
        mic_menu = rumps.MenuItem("🎙️ Mic Sensitivity")
        current_threshold = self.config.mic_threshold

        sensitivity_options = [
            ("low", 1, "Low [1] (loud speech only)"),
            ("medium", 40, "Medium [40]"),
            ("high", 70, "High [70] (Recommended)"),
            ("max", 80, "Max [80] (quiet speech to barge in)")
        ]

        for level, threshold, description in sensitivity_options:
            check = "✓ " if current_threshold == threshold else "   "
            item = rumps.MenuItem(
                f"{check}{description}",
                callback=lambda s, lv=level: self.on_select_mic_sensitivity(lv)
            )
            mic_menu.add(item)

        mic_menu.add(rumps.separator)
        mic_menu.add(rumps.MenuItem(
            f"Custom... (current: {current_threshold})",
            callback=self.on_custom_mic_threshold
        ))

        self.menu.add(mic_menu)

        # Barge-in Sensitivity submenu (how easy to interrupt agent)
        barge_menu = rumps.MenuItem("🗣️ Barge-in Sensitivity")
        current_barge_threshold = self.config.barge_threshold

        barge_options = [
            ("off", 1, "Off [1] (can't interrupt)"),
            ("low", 25, "Low [25] (speak loudly)"),
            ("medium", 50, "Medium [50] (Recommended)"),
            ("high", 75, "High [75] (easy interrupt)")
        ]

        for level, threshold, description in barge_options:
            check = "✓ " if current_barge_threshold == threshold else "   "
            item = rumps.MenuItem(
                f"{check}{description}",
                callback=lambda s, lv=level: self.on_select_barge_sensitivity(lv)
            )
            barge_menu.add(item)

        barge_menu.add(rumps.separator)
        barge_menu.add(rumps.MenuItem(
            f"Custom... (current: {current_barge_threshold})",
            callback=self.on_custom_barge_threshold
        ))

        self.menu.add(barge_menu)

        # Agent Boldness submenu (how eager to engage in conversations)
        boldness_menu = rumps.MenuItem("🧠 Agent Boldness")
        current_boldness = self.config.agent_boldness

        boldness_options = [
            ("very_timid", 10, "Very Timid [10] (clear directives only)"),
            ("timid", 25, "Timid [25] (conservative)"),
            ("somewhat_timid", 40, "Somewhat Timid [40] (Default)"),
            ("balanced", 60, "Balanced [60]"),
            ("bold", 80, "Bold [80] (eager to engage)")
        ]

        for level, threshold, description in boldness_options:
            check = "✓ " if current_boldness == threshold else "   "
            item = rumps.MenuItem(
                f"{check}{description}",
                callback=lambda s, lv=threshold: self.on_select_agent_boldness(lv)
            )
            boldness_menu.add(item)

        boldness_menu.add(rumps.separator)
        boldness_menu.add(rumps.MenuItem(
            f"Custom... (current: {current_boldness})",
            callback=self.on_custom_agent_boldness
        ))

        self.menu.add(boldness_menu)

        # Honorific selection (sir/madam/custom)
        current_honorific = self.get_current_honorific()
        honorific_menu = rumps.MenuItem(f"Called: {current_honorific.title()}")

        presets = ["Sir", "Madam"]
        for preset in presets:
            check = "✓ " if current_honorific.lower() == preset.lower() else "   "
            honorific_menu.add(rumps.MenuItem(
                f"{check}{preset}",
                callback=lambda s, h=preset.lower(): self.on_select_honorific(h)
            ))

        honorific_menu.add(rumps.separator)

        # Custom option
        is_custom = current_honorific.lower() not in ("sir", "madam")
        custom_label = f"✓  Custom: {current_honorific.title()}" if is_custom else "   Custom..."
        honorific_menu.add(rumps.MenuItem(custom_label, callback=self.on_custom_honorific))

        self.menu.add(honorific_menu)

        self.menu.add(rumps.separator)

        # Debug Mode toggle
        debug_check = "✓ " if self.config.debug_mode else "   "
        self.menu.add(rumps.MenuItem(
            f"{debug_check} Debug Mode",
            callback=self.on_toggle_debug_mode
        ))

        # Check for Updates
        self.menu.add(rumps.MenuItem("Check for Updates", callback=self.on_check_for_updates))

        # Quit
        self.menu.add(rumps.MenuItem("Quit", callback=self.on_quit))

    def on_select_edge_voice(self, voice_name):
        """Select an Edge-TTS voice from the menu."""
        try:
            # Save voice setting to config file
            self.config.preferred_voice = voice_name
            self._current_voice = voice_name
            logger.info(f"Edge-TTS voice selected: {voice_name}")
        except Exception as e:
            logger.error(f"Failed to save voice setting: {e}")
            _truncated_alert("Setting Not Saved", f"Could not save your voice setting. Please try again.\n\nDetail: {type(e).__name__}: {e}")
            return

        if self.analytics:
            self.analytics.track_event("voice_changed", {
                "voice_name": voice_name,
                "tts_provider": "edge-tts"
            })

        # Update menu immediately to show the change
        self.build_menu()

        # Restart voice loop if running
        if self.mouth_running:
            import threading
            def restart_voice_loop():
                try:
                    # Delay to ensure config is flushed to disk
                    time.sleep(0.3)
                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    logger.info(f"Voice loop restarted with Edge-TTS voice: {voice_name}")

                    # Announce voice change
                    time.sleep(0.5)
                    speech_file = self.speech_output_dir / "speech_output.txt"
                    try:
                        with open(speech_file, 'a') as f:
                            f.write("Voice Changed\n")
                        logger.info("Voice change message written to speech output")
                    except Exception as e:
                        logger.error(f"Failed to write voice change message: {e}")
                except Exception as e:
                    logger.error(f"Failed to restart voice loop: {e}")
            threading.Thread(target=restart_voice_loop, daemon=True).start()

    def on_test_edge_voice(self, sender):
        """Test the current Edge-TTS voice."""
        if not self.mouth_running:
            rumps.alert("Not Running", "Start Molt Speak first to test the voice.")
            return

        try:
            speech_file = self.speech_output_dir / "speech_output.txt"
            with open(speech_file, 'a') as f:
                f.write("This is a test of the current Edge TTS voice.\n")
            logger.info("Voice test message written")
        except Exception as e:
            logger.error(f"Failed to test voice: {e}")
            _truncated_alert("Voice Test Failed", f"Could not test the selected voice. Please try again.\n\nDetail: {type(e).__name__}: {e}")

    def on_test_elevenlabs_voice(self, sender):
        """Test the current ElevenLabs voice."""
        if not self.mouth_running:
            rumps.alert("Not Running", "Start Molt Speak first to test the voice.")
            return

        try:
            speech_file = self.speech_output_dir / "speech_output.txt"
            with open(speech_file, 'a') as f:
                f.write("This is a test of the ElevenLabs voice.\n")
            logger.info("ElevenLabs voice test message written")
        except Exception as e:
            logger.error(f"Failed to test voice: {e}")
            _truncated_alert("Voice Test Failed", f"Could not test the selected voice. Please try again.\n\nDetail: {type(e).__name__}: {e}")

    def get_elevenlabs_voices(self):
        """Fetch available ElevenLabs voices from API."""
        # Use cached voices if available
        if hasattr(self, '_elevenlabs_voices_cache') and self._elevenlabs_voices_cache:
            return self._elevenlabs_voices_cache

        api_key = self.config.elevenlabs_api_key
        if not api_key:
            return []

        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=api_key)
            voices_response = client.voices.get_all()
            voices = [{'voice_id': v.voice_id, 'name': v.name} for v in voices_response.voices]
            self._elevenlabs_voices_cache = voices
            logger.info(f"Fetched {len(voices)} ElevenLabs voices")
            return voices
        except Exception as e:
            logger.error(f"Failed to fetch ElevenLabs voices: {e}")
            return []

    def on_select_elevenlabs_voice(self, voice_id, voice_name):
        """Select an ElevenLabs voice."""
        try:
            self.config.elevenlabs_voice_id = voice_id
            logger.info(f"ElevenLabs voice selected: {voice_name} ({voice_id})")
        except Exception as e:
            logger.error(f"Failed to save voice setting: {e}")
            _truncated_alert("Setting Not Saved", f"Could not save your voice setting. Please try again.\n\nDetail: {type(e).__name__}: {e}")
            return

        if self.analytics:
            self.analytics.track_event("voice_changed", {
                "voice_name": voice_name,
                "tts_provider": "elevenlabs"
            })

        # Update menu
        self.build_menu()

        # Restart voice loop if running
        if self.mouth_running:
            import threading
            def restart_voice_loop():
                try:
                    # Delay to ensure config is flushed to disk
                    time.sleep(0.3)
                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    logger.info(f"Voice loop restarted with ElevenLabs voice: {voice_name} ({voice_id})")

                    # Announce voice change
                    time.sleep(0.5)
                    speech_file = self.speech_output_dir / "speech_output.txt"
                    try:
                        with open(speech_file, 'a') as f:
                            f.write("Voice Changed\n")
                    except Exception as e:
                        logger.error(f"Failed to write voice change message: {e}")
                except Exception as e:
                    logger.error(f"Failed to restart voice loop: {e}")
            threading.Thread(target=restart_voice_loop, daemon=True).start()

    def on_refresh_elevenlabs_voices(self, sender):
        """Refresh the ElevenLabs voices list."""
        # Clear cache
        self._elevenlabs_voices_cache = None
        # Rebuild menu (will fetch fresh voices)
        self.build_menu()
        logger.info("ElevenLabs voices refreshed")

    def on_select_mic_sensitivity(self, level: str):
        """Set microphone sensitivity level."""
        try:
            self.config.mic_sensitivity = level
            threshold = self.config.get_speech_threshold()
            logger.info(f"Mic sensitivity set to: {level} (threshold: {threshold})")
        except Exception as e:
            logger.error(f"Failed to save mic sensitivity: {e}")
            _truncated_alert("Setting Not Saved", f"Could not save your setting. Please try again.\n\nDetail: {type(e).__name__}: {e}")
            return

        if self.analytics:
            self.analytics.track_event("setting_changed", {
                "setting": "mic_sensitivity",
                "value": level
            })

        # Update menu
        self.build_menu()

        # Restart voice loop if running to apply new sensitivity
        if self.mouth_running:
            import threading
            def restart_voice_loop():
                try:
                    time.sleep(0.2)
                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    logger.info(f"Voice loop restarted with mic sensitivity: {level}")
                except Exception as e:
                    logger.error(f"Failed to restart voice loop: {e}")
            threading.Thread(target=restart_voice_loop, daemon=True).start()

    def on_custom_mic_threshold(self, sender):
        """Open dialog for custom mic sensitivity value."""
        try:
            response = rumps.Window(
                title="Custom Mic Sensitivity",
                message="Enter sensitivity (1-100):\n\nHigher = more sensitive\n\nPresets: Low=1, Medium=40, High=70, Max=80",
                default_text=str(self.config.mic_threshold),
                ok="Set",
                cancel="Cancel",
                dimensions=(100, 24)
            ).run()

            if response.clicked:
                try:
                    sensitivity = int(response.text.strip())
                    if 1 <= sensitivity <= 100:
                        self.config.mic_threshold = sensitivity
                        logger.info(f"Custom mic sensitivity set to: {sensitivity}")
                        self.build_menu()

                        if self.analytics:
                            self.analytics.track_event("setting_changed", {
                                "setting": "mic_threshold",
                                "value": sensitivity
                            })

                        # Restart voice loop if running
                        if self.mouth_running:
                            import threading
                            def restart_voice_loop():
                                try:
                                    time.sleep(0.2)
                                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                                   capture_output=True, timeout=15)
                                    subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                                   capture_output=True, timeout=15)
                                    logger.info(f"Voice loop restarted with sensitivity: {sensitivity}")
                                except Exception as e:
                                    logger.error(f"Failed to restart voice loop: {e}")
                            threading.Thread(target=restart_voice_loop, daemon=True).start()
                    else:
                        _truncated_alert("Invalid Value", "Sensitivity must be between 1 and 100")
                except ValueError:
                    _truncated_alert("Invalid Value", "Please enter a number between 1 and 100")
        except Exception as e:
            logger.error(f"Error in custom sensitivity dialog: {e}")

    def on_select_barge_sensitivity(self, level: str):
        """Set barge-in sensitivity level (how easy to interrupt agent)."""
        try:
            self.config.barge_sensitivity = level
            multiplier = self.config.get_barge_multiplier()
            logger.info(f"Barge-in sensitivity set to: {level} (multiplier: {multiplier}x)")
        except Exception as e:
            logger.error(f"Failed to save barge sensitivity: {e}")
            _truncated_alert("Setting Not Saved", f"Could not save your setting. Please try again.\n\nDetail: {type(e).__name__}: {e}")
            return

        if self.analytics:
            self.analytics.track_event("setting_changed", {
                "setting": "barge_sensitivity",
                "value": level
            })

        # Update menu
        self.build_menu()

        # Restart voice loop if running to apply new sensitivity
        if self.mouth_running:
            import threading
            def restart_voice_loop():
                try:
                    time.sleep(0.2)
                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    logger.info(f"Voice loop restarted with barge sensitivity: {level}")
                except Exception as e:
                    logger.error(f"Failed to restart voice loop: {e}")
            threading.Thread(target=restart_voice_loop, daemon=True).start()

    def on_custom_barge_threshold(self, sender):
        """Open dialog for custom barge-in sensitivity value."""
        try:
            response = rumps.Window(
                title="Custom Barge-in Sensitivity",
                message="Enter sensitivity (1-100):\n\nHigher = easier to interrupt\n\nPresets: Off=1, Low=25, Medium=50, High=75",
                default_text=str(self.config.barge_threshold),
                ok="Set",
                cancel="Cancel",
                dimensions=(100, 24)
            ).run()

            if response.clicked:
                try:
                    sensitivity = int(response.text.strip())
                    if 1 <= sensitivity <= 100:
                        self.config.barge_threshold = sensitivity
                        logger.info(f"Custom barge sensitivity set to: {sensitivity}")
                        self.build_menu()

                        if self.analytics:
                            self.analytics.track_event("setting_changed", {
                                "setting": "barge_threshold",
                                "value": sensitivity
                            })

                        # Restart voice loop if running
                        if self.mouth_running:
                            import threading
                            def restart_voice_loop():
                                try:
                                    time.sleep(0.2)
                                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                                   capture_output=True, timeout=15)
                                    subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                                   capture_output=True, timeout=15)
                                    logger.info(f"Voice loop restarted with barge sensitivity: {sensitivity}")
                                except Exception as e:
                                    logger.error(f"Failed to restart voice loop: {e}")
                            threading.Thread(target=restart_voice_loop, daemon=True).start()
                    else:
                        _truncated_alert("Invalid Value", "Sensitivity must be between 1 and 100")
                except ValueError:
                    _truncated_alert("Invalid Value", "Please enter a number between 1 and 100")
        except Exception as e:
            logger.error(f"Error in custom barge sensitivity dialog: {e}")

    def on_select_agent_boldness(self, value: int):
        """Set agent boldness level (how eager to engage in conversations)."""
        try:
            self.config.agent_boldness = value
            logger.info(f"Agent boldness set to: {value} ({self.config.get_boldness_label()})")
        except Exception as e:
            logger.error(f"Failed to save agent boldness: {e}")
            _truncated_alert("Setting Not Saved", f"Could not save your setting. Please try again.\n\nDetail: {type(e).__name__}: {e}")
            return

        if self.analytics:
            self.analytics.track_event("setting_changed", {
                "setting": "agent_boldness",
                "value": value
            })

        # Update menu
        self.build_menu()

        # Notify agent about new disposition (no restart needed)
        if self.mouth_running:
            self.inject_boldness_change_message(value, self.config.get_boldness_label())

    @staticmethod
    def _boldness_stats(v):
        """Compute boldness perturbation values for display."""
        bias = (v - 40) / 250
        momentum = 0.6 + v / 100
        halflife = 1.0 + (v - 40) / 100
        if v <= 15: label = "Very Timid"
        elif v <= 35: label = "Timid"
        elif v <= 50: label = "Somewhat Timid"
        elif v <= 70: label = "Balanced"
        else: label = "Bold"
        return label, bias, momentum, halflife

    def on_custom_agent_boldness(self, sender):
        """Open dialog for custom agent boldness value."""
        try:
            cur = self.config.agent_boldness
            label, bias, momentum, halflife = self._boldness_stats(cur)
            msg = (
                f"Enter boldness (1-100):\n\n"
                f"Higher = bolder (more responsive)\n\n"
                f"Current: {cur} ({label})\n"
                f"  Score bias:      {bias:+.3f}\n"
                f"  Momentum mult:   {momentum:.2f}x\n"
                f"  Half-life mult:  {halflife:.2f}x\n\n"
                f"Presets: V.Timid=10, Timid=25,\n"
                f"Default=40, Balanced=60, Bold=80"
            )
            response = rumps.Window(
                title="Custom Agent Boldness",
                message=msg,
                default_text=str(cur),
                ok="Set",
                cancel="Cancel",
                dimensions=(100, 24)
            ).run()

            if response.clicked:
                try:
                    boldness = int(response.text.strip())
                    if 1 <= boldness <= 100:
                        self.config.agent_boldness = boldness
                        logger.info(f"Custom agent boldness set to: {boldness}")
                        self.build_menu()

                        if self.analytics:
                            self.analytics.track_event("setting_changed", {
                                "setting": "agent_boldness",
                                "value": boldness
                            })

                        # Restart voice loop if running
                        if self.mouth_running:
                            self.inject_boldness_change_message(boldness, self.config.get_boldness_label())
                    else:
                        _truncated_alert("Invalid Value", "Boldness must be between 1 and 100")
                except ValueError:
                    _truncated_alert("Invalid Value", "Please enter a number between 1 and 100")
        except Exception as e:
            logger.error(f"Error in custom boldness dialog: {e}")

    def on_toggle_debug_mode(self, sender):
        """Toggle debug mode (inline temperature/barge-in tags in agent messages)."""
        new_value = not self.config.debug_mode
        self.config.debug_mode = new_value
        logger.info(f"Debug mode {'enabled' if new_value else 'disabled'}")

        self.build_menu()

        # Restart voice loop if running to apply new mode
        if self.mouth_running:
            import threading
            def restart_voice_loop():
                try:
                    time.sleep(0.2)
                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    logger.info(f"Voice loop restarted with debug mode: {new_value}")
                except Exception as e:
                    logger.error(f"Failed to restart voice loop: {e}")
            threading.Thread(target=restart_voice_loop, daemon=True).start()

    def on_select_provider(self, provider: str):
        """Select TTS provider (edge-tts or elevenlabs)."""
        try:
            # Warn if ElevenLabs is not configured but still allow the switch
            if provider == "elevenlabs" and not self.config.elevenlabs_api_key:
                rumps.alert(
                    "ElevenLabs Not Configured",
                    "No API key found. Voices won't load until you configure ElevenLabs:\n"
                    "TTS Provider → Configure ElevenLabs"
                )

            # Save provider setting
            self.config.tts_provider = provider
            logger.info(f"TTS provider changed to: {provider}")

            if self.analytics:
                self.analytics.track_event("setting_changed", {
                    "setting": "tts_provider",
                    "value": provider
                })

            # Update menu
            self.build_menu()

            # Restart or start voice loop with new provider
            import threading
            provider_name = "ElevenLabs" if provider == "elevenlabs" else "Edge-TTS"

            if self.mouth_running:
                def restart_voice_loop():
                    try:
                        stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                        subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                       capture_output=True, timeout=15)
                        subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                       capture_output=True, timeout=15)
                        logger.info(f"Voice loop restarted with provider: {provider}")

                        # Test the new provider
                        time.sleep(0.5)
                        speech_file = self.speech_output_dir / "speech_output.txt"
                        try:
                            with open(speech_file, 'a') as f:
                                f.write(f"Switched to {provider_name}. Testing voice.\n")
                            logger.info("Provider test message written to speech output")
                        except Exception as e:
                            logger.error(f"Failed to write provider test message: {e}")
                    except Exception as e:
                        logger.error(f"Failed to restart voice loop: {e}")

                threading.Thread(target=restart_voice_loop, daemon=True).start()
            else:
                # Voice loop is not running (e.g. crashed due to expired API key)
                # Auto-start it with the new provider instead of just showing an alert
                def start_with_new_provider():
                    try:
                        # Stop any lingering processes first
                        stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                        subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                       capture_output=True, timeout=15)
                        result = subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                       capture_output=True, text=True, timeout=15)
                        if result.returncode != 0:
                            logger.error(f"Voice loop failed to start with new provider: {result.stdout + result.stderr}")
                            return
                        logger.info(f"Voice loop started with new provider: {provider}")

                        time.sleep(1.0)
                        self.inject_agent_instructions()

                        time.sleep(0.5)
                        speech_file = self.speech_output_dir / "speech_output.txt"
                        try:
                            with open(speech_file, 'a') as f:
                                f.write(f"Switched to {provider_name}.\n")
                        except Exception as e:
                            logger.error(f"Failed to write provider switch message: {e}")
                    except Exception as e:
                        logger.error(f"Failed to start voice loop with new provider: {e}")

                threading.Thread(target=start_with_new_provider, daemon=True).start()

        except Exception as e:
            logger.error(f"Error selecting provider: {e}")
            _truncated_alert("Provider Change Failed", f"Could not switch TTS provider. Please try again.\n\nDetail: {type(e).__name__}: {e}")

    def on_configure_elevenlabs(self, sender):
        """Launch ElevenLabs configuration wizard."""
        try:
            logger.info("Launching ElevenLabs configuration...")

            # Run the configuration script in a new Terminal window
            config_script = self.project_dir / "scripts" / "molt-speak-elo.sh"

            if not config_script.exists():
                rumps.alert(
                    "Script Not Found",
                    f"Configuration script not found at:\n{config_script}"
                )
                return

            # Open Terminal and run the script
            applescript = f'''
                tell application "Terminal"
                    activate
                    do script "cd {shlex.quote(str(self.project_dir))} && ./scripts/molt-speak-elo.sh"
                end tell
            '''

            subprocess.run(['osascript', '-e', applescript], check=True)

            logger.info("ElevenLabs configuration launched in Terminal")

        except Exception as e:
            logger.error(f"Error launching ElevenLabs configuration: {e}")
            _truncated_alert("Configuration Failed", f"Could not open the configuration tool.\n\nDetail: {type(e).__name__}: {e}")

    def check_process(self, pid_file: Path) -> bool:
        """Check if a process is running by PID file."""
        try:
            if not pid_file.exists():
                return False
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError, PermissionError):
            return False
        except Exception as e:
            logger.debug(f"Error checking process {pid_file}: {e}")
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
            some_running = self.integration_running or self.mouth_running or self.ears_running

            if all_running:
                # Everything healthy — clear recovery state
                if getattr(self, '_recovery_needed', False):
                    self._recovery_needed = False
                    logger.info("All systems recovered — clearing recovery state")
                if self._is_user_speaking():
                    self._set_title(f"🔵{self._mascot}")
                else:
                    self._set_title(f"🟢{self._mascot}")
            elif some_running:
                # Degraded mode — some components still alive
                self._set_title(f"🟡{self._mascot}")
            else:
                self._set_title(f"🔴{self._mascot}")

            # Check for crash report from unified_audio supervisor
            self._check_crash_report()

            # Rebuild menu if anything changed
            if (integration_was_running != self.integration_running or
                mouth_was_running != self.mouth_running or
                ears_was_running != self.ears_running):
                self.build_menu()
        except Exception as e:
            logger.warning(f"Error updating status: {e}")

    def _check_crash_report(self):
        """Check for runtime/last_crash.json and handle based on action type."""
        crash_file = self.runtime_dir / "last_crash.json"
        if not crash_file.exists():
            return
        try:
            import json
            data = json.loads(crash_file.read_text())
            crash_file.unlink(missing_ok=True)

            component = data.get("component", "Unknown")
            action = data.get("action", "needs_user_action")
            retry_count = data.get("retry_count", 0)

            # Use error registry for user-friendly messages (fall back to raw fields)
            error_code = data.get("error_code")
            try:
                from src.errors import lookup_error
                err = lookup_error(error_code) if error_code else None
                message = err.user_message if err else data.get("message", "Crashed unexpectedly")
                fix = err.fix if err else data.get("fix", "")
                alert_title = err.alert_title if err else component
            except ImportError:
                message = data.get("message", "Crashed unexpectedly")
                fix = data.get("fix", "")
                alert_title = component

            if action == "auto_restarted":
                # Silent recovery — supervisor handled it.
                # Only alert if this is the 3rd+ auto-restart (repeated issue).
                if retry_count >= 3:
                    _truncated_alert(
                        f"{alert_title} — Unstable",
                        f"{component} has crashed {retry_count} times and keeps restarting.\n\n"
                        f"{message}\n"
                        f"{fix}",
                    )
                else:
                    logger.info(
                        f"{component} auto-restarted (attempt {retry_count}) — no alert"
                    )
                return

            if action == "retries_exhausted":
                # Supervisor gave up — offer to try again
                response = rumps.alert(
                    f"{alert_title} — Keeps Crashing",
                    f"{component} crashed {retry_count} times.\n\n"
                    f"{message}\n"
                    f"{fix}",
                    ok="Try Again",
                    cancel="OK",
                )
                if response == 1:  # "Try Again" clicked
                    self._attempt_recovery()
                else:
                    self._start_recovery_polling()
                return

            # action == "needs_user_action" (non-restartable failure)
            response = rumps.alert(
                f"{alert_title} — Stopped",
                f"{message}\n\n"
                f"{fix}",
                ok="Try Again",
                cancel="OK",
            )
            if response == 1:  # "Try Again" clicked
                self._attempt_recovery()
            else:
                # User dismissed — start background polling for when they fix it
                self._start_recovery_polling()

        except Exception as e:
            logger.warning(f"Could not read crash report: {e}")
            try:
                crash_file.unlink(missing_ok=True)
            except Exception:
                pass

    def _attempt_recovery(self):
        """Run preflight (if available), then restart the voice loop."""
        import threading
        def _do_recovery():
            try:
                from src.diagnostics.preflight import PreflightChecker
                checker = PreflightChecker(project_root=self.project_dir)
                results = checker.run_critical_only()
                if not checker.has_critical_failure(results):
                    logger.info("Preflight passed — restarting voice loop")
                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    time.sleep(0.5)
                    self.on_start_all(None)
                else:
                    msg = PreflightChecker.format_results(results)
                    logger.warning(f"Recovery preflight failed:\n{msg}")
                    self._start_recovery_polling()
            except ImportError:
                # Preflight module not available — attempt direct restart
                logger.info("Preflight not available — attempting direct restart")
                try:
                    stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                    subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                   capture_output=True, timeout=15)
                    time.sleep(0.5)
                    self.on_start_all(None)
                except Exception as e2:
                    logger.error(f"Direct restart failed: {e2}")
                    self._start_recovery_polling()
            except Exception as e:
                logger.error(f"Recovery attempt failed: {e}")
                self._start_recovery_polling()
        threading.Thread(target=_do_recovery, daemon=True).start()

    def _start_recovery_polling(self):
        """Start background polling for when the issue is fixed (e.g. mic plugged in)."""
        if getattr(self, '_recovery_needed', False):
            return  # Already polling
        self._recovery_needed = True
        if not hasattr(self, '_recovery_timer') or self._recovery_timer is None:
            self._recovery_timer = rumps.Timer(self._recovery_poll, 10)
            self._recovery_timer.start()
            logger.info("Started recovery polling (every 10s)")

    def _recovery_poll(self, sender):
        """Background poll: check if crashed component's issue is fixed."""
        if not getattr(self, '_recovery_needed', False):
            # Recovery no longer needed — stop polling
            if hasattr(self, '_recovery_timer') and self._recovery_timer:
                self._recovery_timer.stop()
                self._recovery_timer = None
            return
        try:
            from src.diagnostics.preflight import PreflightChecker
            checker = PreflightChecker(project_root=self.project_dir)
            results = checker.run_critical_only()
            if not checker.has_critical_failure(results):
                # Issue fixed! Auto-restart.
                logger.info("Recovery poll: preflight passed — auto-restarting")
                self._recovery_needed = False
                if hasattr(self, '_recovery_timer') and self._recovery_timer:
                    self._recovery_timer.stop()
                    self._recovery_timer = None
                stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                               capture_output=True, timeout=15)
                time.sleep(0.5)
                self.on_start_all(None)
        except ImportError:
            # Preflight not available — attempt direct restart
            logger.info("Recovery poll: preflight not available — attempting direct restart")
            self._recovery_needed = False
            if hasattr(self, '_recovery_timer') and self._recovery_timer:
                self._recovery_timer.stop()
                self._recovery_timer = None
            try:
                stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                               capture_output=True, timeout=15)
                time.sleep(0.5)
                self.on_start_all(None)
            except Exception as e2:
                logger.error(f"Direct restart failed: {e2}")
        except Exception as e:
            logger.debug(f"Recovery poll check failed: {e}")

    def _start_script_cmd(self) -> list:
        """Build the start_voice_loop.sh command, including --debug if enabled."""
        script_path = self.project_dir / "scripts" / "start_voice_loop.sh"
        cmd = ["bash", str(script_path)]
        if self.config.debug_mode:
            cmd.append('--debug')
        return cmd

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

            # Run start script (timeout covers preflight checks + venv setup)
            result = subprocess.run(
                self._start_script_cmd(),
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                # Don't show notification to avoid macOS notification spam
                logger.info("Voice loop started successfully")
                self.update_status(None)

                # Track voice loop start
                if self.analytics:
                    self.analytics.start_session()
                    self.analytics.track_event("voice_loop_started", {
                        "triggered_by": "user" if sender is not None else "auto_start",
                        "tts_provider": self.config.tts_provider,
                        "voice": self.config.preferred_voice,
                        "mic_sensitivity": self.config.mic_sensitivity,
                        "barge_sensitivity": self.config.barge_sensitivity
                    })

                # Inject short instruction to read the instructions file
                import threading
                def delayed_injection():
                    time.sleep(3.0)
                    self.inject_agent_instructions()
                threading.Thread(target=delayed_injection, daemon=True).start()

            else:
                # Extract a clean error message from script output
                raw = (result.stdout + "\n" + result.stderr).strip()
                logger.error(f"Failed to start voice loop:\n{raw}")
                # Strip ANSI codes and extract only the useful error lines
                clean = re.sub(r'\x1b\[[0-9;]*m', '', raw)
                # Pull out just the error — skip banners and progress
                error_lines = []
                for line in clean.splitlines():
                    line = line.strip()
                    # Keep failure/error/blocked lines and their fixes
                    if any(kw in line.upper() for kw in ['FAIL', 'ERROR', 'BLOCKED', 'FIX:', 'CANNOT START']):
                        error_lines.append(line)
                if error_lines:
                    msg = "\n".join(error_lines)
                else:
                    msg = clean[-300:] if len(clean) > 300 else clean
                self._pending_alert = (
                    "Voice Loop Failed",
                    msg or "Unknown error — check logs/audio.log"
                )
        except subprocess.TimeoutExpired:
            logger.error("Voice loop start script timed out")
            self._pending_alert = ("Voice Loop Failed", "Startup timed out. Try: moltspeak stop && moltspeak start")
        except Exception as e:
            logger.error(f"Error starting voice loop: {e}")
            self._pending_alert = ("Error", f"Failed to start: {e}")

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
                ["bash", str(script_path)],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Clear speech output queue to prevent old messages on restart
                speech_output = self.speech_output_dir / "speech_output.txt"
                try:
                    speech_output.write_text("")
                    logger.info("Cleared speech output queue")
                except Exception as e:
                    logger.warning(f"Failed to clear speech queue: {e}")

                # Track voice loop stop with session context
                if self.analytics:
                    session_duration = None
                    if self.analytics.session_start:
                        session_duration = round(time.time() - self.analytics.session_start, 2)
                    self.analytics.track_event("voice_loop_stopped", {
                        "triggered_by": "user",
                        "session_duration_seconds": session_duration,
                        "voice_interactions": self.analytics.voice_interaction_count,
                        "tts_provider": self.config.tts_provider,
                        "voice": self.config.preferred_voice
                    })
                    self.analytics.end_session()

                # Notification removed
                self.update_status(None)
            else:
                _truncated_alert(
                    "Stop Failed",
                    f"Failed to stop voice loop:\n\n{result.stderr}"
                )
        except Exception as e:
            logger.error(f"Error stopping voice loop: {e}")
            _truncated_alert("Stop Failed", f"Could not stop the voice loop cleanly. Try: moltspeak kill\n\nDetail: {type(e).__name__}: {e}")

    def on_start_integration(self, sender):
        """Start Integration Coordinator."""
        self._start_component("integration", "Integration Coordinator",
                             ["python", "main.py"])

    def on_start_mouth(self, sender):
        """Start OpenClaw Mouth standalone."""
        self._start_component("mouth", "OpenClaw Mouth",
                             ["python", "main.py"],
                             self.project_dir / "open_mouth")

    def on_start_ears(self, sender):
        """Start OpenClaw Ears standalone."""
        self._start_component("ears", "OpenClaw Ears",
                             ["python", "main.py"],
                             self.project_dir / "open_ears")

    def on_start_mouth_only(self, sender):
        """Start Mouth only mode (TTS output, no voice input)."""
        # Stop ears if running
        if self.ears_running:
            self._stop_component(self.ears_pid_file, "OpenClaw Ears")

        # Start integration if not running
        if not self.integration_running:
            self._start_component("integration", "Integration Coordinator",
                                 ["python", "main.py"])

        # Start mouth
        self._start_component("mouth", "OpenClaw Mouth",
                             ["python", "main.py"],
                             self.project_dir / "open_mouth")
        logger.info("Started Mouth-only mode (TTS output)")

    def on_start_ears_only(self, sender):
        """Start Ears only mode (voice input, no TTS output)."""
        # Stop mouth if running
        if self.mouth_running:
            self._stop_component(self.mouth_pid_file, "OpenClaw Mouth")

        # Start ears
        self._start_component("ears", "OpenClaw Ears",
                             ["python", "main.py"],
                             self.project_dir / "open_ears")
        logger.info("Started Ears-only mode (voice input)")

    def _start_component(self, name: str, display_name: str, cmd_args: list, working_dir: Path = None):
        """Start a component."""
        try:
            cwd = str(working_dir) if working_dir else str(self.project_dir)
            subprocess.Popen(
                cmd_args,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Notification removed
            self.update_status(None)
        except Exception as e:
            logger.error(f"Error starting {name}: {e}")
            _truncated_alert(f"{display_name} Start Failed", f"Could not start {display_name}. Check logs: moltspeak logs audio\n\nDetail: {type(e).__name__}: {e}")

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
            _truncated_alert(f"{display_name} Stop Failed", f"Could not stop {display_name}. Try: moltspeak kill\n\nDetail: {type(e).__name__}: {e}")

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
        cmd = f"tail -f {shlex.quote(str(ears_log))}"
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
        cmd = f"tail -f {shlex.quote(str(mouth_log))}"
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
            do script "tail -f {shlex.quote(str(log_path))}"
        end tell
        '''

        try:
            subprocess.run(["osascript", "-e", script], check=True)
        except Exception as e:
            logger.error(f"Error opening log: {e}")
            _truncated_alert("Log Viewer Failed", f"Could not open the log file.\n\nDetail: {type(e).__name__}: {e}")

    def inject_agent_instructions(self):
        """Write instructions to file and tell agent to read it."""
        # Use /tmp/speak.txt symlink (space-free path for agent's bash commands)
        speech_file = "/tmp/speak.txt"

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
        speech_file = "/tmp/speak.txt"
        honorific = self.get_current_honorific()

        # Path where closing instructions will be saved
        closing_instructions_file = self.speech_output_dir / "agent_closing_instructions.txt"

        # Read the closing instructions template and apply substitutions
        close_template_file = self.project_dir / "docs" / "AGENT_INSTRUCTIONS_CLOSE.txt"
        try:
            closing_instructions = close_template_file.read_text()
            closing_instructions = closing_instructions.replace("{{SPEECH_FILE}}", speech_file)
            closing_instructions = closing_instructions.replace("{{HONORIFIC}}", honorific)
            # Write rendered instructions to the molt-speak directory
            closing_instructions_file.write_text(closing_instructions)
            logger.info(f"Wrote closing instructions to: {closing_instructions_file}")
        except Exception as e:
            logger.error(f"Failed to write closing instructions: {e}")
            # Fallback to minimal instruction
            closing_instructions_file.write_text(
                f"Voice mode disabled. Say goodbye: echo \"Goodbye, {honorific}.\" >> {speech_file} && echo \"(spoken)\" "
                f"then display the same text. Resume normal text-only responses."
            )

        # Self-contained message: agent knows what to do without reading the file
        message = (
            f"[MOLT SPEAK: OFFLINE] - Voice mode ending. "
            f"Say goodbye: echo \"Goodbye, {honorific}.\" >> {speech_file} && echo \"(spoken)\" "
            f"then display the same text. Full instructions at {closing_instructions_file}"
        )

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

    def inject_boldness_change_message(self, value: int, label: str):
        """Inject message to tell agent about boldness/disposition change."""
        message = f"[MOLT SPEAK: DISPOSITION CHANGED] Your boldness is now {value} ({label}). Adjust your conversational style per your disposition profile."

        # Paste into terminal — agent acknowledges verbally via normal pipeline
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
            escaped_message = message.replace('\\', '\\\\').replace('"', '\\"')
            logger.info(f"Injecting boldness change message into terminal: {message}")

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
                logger.info("Injected boldness change message into terminal successfully")
            else:
                logger.warning(f"Could not inject boldness change message: {result.stderr}")
        except Exception as e:
            logger.warning(f"Error injecting boldness change message: {e}")

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

    def on_select_honorific(self, honorific: str):
        """Select a preset honorific (sir/madam)."""
        self._save_honorific(honorific)

    def on_custom_honorific(self, sender):
        """Prompt user to enter a custom honorific."""
        current = self.get_current_honorific()
        window = rumps.Window(
            message="What would you like to be called?",
            title="Custom Honorific",
            default_text=current,
            ok="Save",
            cancel="Cancel"
        )
        response = window.run()
        if response.clicked and response.text.strip():
            self._save_honorific(response.text.strip())

    def _save_honorific(self, new_honorific: str):
        """Save honorific setting and update menu."""
        try:
            self.config.user_title = new_honorific
            honorific_file = self.runtime_dir / "honorific.conf"
            honorific_file.write_text(new_honorific)
            logger.info(f"Honorific changed to: {new_honorific}")
            if self.analytics:
                self.analytics.track_event("setting_changed", {
                    "setting": "honorific",
                    "value": new_honorific.lower() if new_honorific.lower() in ("sir", "madam") else "custom"
                })
            self.build_menu()
            # Notify agent about new honorific (no restart needed)
            if self.mouth_running:
                self.inject_honorific_change_message(new_honorific)
        except Exception as e:
            logger.error(f"Error changing honorific: {e}")
            _truncated_alert("Honorific Not Saved", f"Could not save your honorific preference. Please try again.\n\nDetail: {type(e).__name__}: {e}")

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

            # Track voice change
            if self.analytics:
                self.analytics.track_event("voice_changed", {
                    "voice_name": voice_name,
                    "mouth_was_running": self.mouth_running
                })

            # Update menu immediately
            self.build_menu()

            # Restart voice loop in background if running
            if self.mouth_running:
                import threading
                def restart_voice_loop():
                    try:
                        stop_script = self.project_dir / "scripts" / "stop_voice_loop.sh"
                        subprocess.run(["bash", str(stop_script)], cwd=str(self.project_dir),
                                       capture_output=True, timeout=15)
                        subprocess.run(self._start_script_cmd(), cwd=str(self.project_dir),
                                       capture_output=True, timeout=15)
                        logger.info(f"Voice loop restarted with voice: {voice_name}")

                        # Announce voice change
                        time.sleep(0.5)  # Brief delay to let voice loop restart
                        speech_file = self.speech_output_dir / "speech_output.txt"
                        try:
                            with open(speech_file, 'a') as f:
                                f.write("Voice Changed\n")
                            logger.info("Voice change message written to speech output")
                        except Exception as e:
                            logger.error(f"Failed to write voice test message: {e}")
                    except Exception as e:
                        logger.error(f"Failed to restart voice loop: {e}")
                threading.Thread(target=restart_voice_loop, daemon=True).start()

        except Exception as e:
            logger.error(f"Error changing voice: {e}")
            _truncated_alert("Voice Change Failed", f"Could not switch to the selected voice. The previous voice is still active.\n\nDetail: {type(e).__name__}: {e}")

    def on_test_voice(self, sender):
        """Test the current voice."""
        voice = self.get_current_voice()
        try:
            subprocess.run(
                ["say", "-v", voice, f"Hello, this is the {voice} voice."],
                check=True
            )
        except Exception as e:
            _truncated_alert("Voice Test Failed", f"Could not test voice {voice}: {e}")

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
            _truncated_alert("Voice List Failed", f"Could not load available voices. Check your internet connection.\n\nDetail: {type(e).__name__}: {e}")

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
        rumps.alert(
            "Instructions Injected",
            f"Voice loop instructions have been sent to the agent TUI.\n\n"
            f"The agent should now know to write responses to:\n"
            f"/tmp/speak.txt"
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

    def _fetch_update_info(self):
        """Fetch update info on background thread (no UI calls)."""
        try:
            from src.services.update_checker import check_for_updates

            logger.info("Checking for updates...")

            # Track update check
            if self.analytics:
                self.analytics.track_event("update_check_started", {
                    "trigger": "app_startup"
                })

            update_available, latest_version, _, install_command = check_for_updates()

            if update_available:
                logger.info(f"Update available: {latest_version}")

                # Track update available
                if self.analytics:
                    self.analytics.track_event("update_available", {
                        "current_version": self._get_current_version(),
                        "latest_version": latest_version,
                        "trigger": "app_startup"
                    })

                # Store result for main thread to display
                self._pending_update = (latest_version, install_command)
            else:
                logger.info("No updates available")

                # Track no update
                if self.analytics:
                    self.analytics.track_event("update_check_completed", {
                        "update_available": False,
                        "trigger": "app_startup"
                    })

        except ImportError:
            logger.warning("Update checker not available (missing packaging library)")
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")

    def _show_pending_update(self, timer):
        """Show update dialog on main thread (called by rumps.Timer)."""
        if self._pending_update is None:
            return

        # Stop the timer and consume the pending update
        timer.stop()
        latest_version, install_command = self._pending_update
        self._pending_update = None

        try:
            rumps.notification(
                title="🦞 Molt-Speak Update Available",
                subtitle=f"Version {latest_version} is now available",
                message="Use the menu bar to update",
                sound=True
            )

            response = rumps.alert(
                title="Update Available",
                message=f"Molt-Speak {latest_version} is available!\n\nYou're currently on version {self._get_current_version()}.\n\nWould you like to update now?",
                ok="Update Now",
                cancel="Later"
            )

            if response == 1:  # User clicked "Update Now"
                self._perform_update(install_command, latest_version)
            else:
                # Track dismissed update
                if self.analytics:
                    self.analytics.track_event("update_dismissed", {
                        "latest_version": latest_version
                    })
        except Exception as e:
            logger.error(f"Error showing update dialog: {e}")

    def _show_pending_alert(self, timer):
        """Show queued alert on main thread (called by rumps.Timer)."""
        if self._pending_alert is None:
            return
        title, message = self._pending_alert
        self._pending_alert = None
        try:
            _truncated_alert(title, message)
        except Exception as e:
            logger.error(f"Error showing alert: {e}")

    def on_check_for_updates(self, sender):
        """Manual update check from menu."""
        try:
            from src.services.update_checker import check_for_updates

            # Track manual update check
            if self.analytics:
                self.analytics.track_event("update_check_started", {
                    "trigger": "manual"
                })

            update_available, latest_version, _, install_command = check_for_updates()

            if update_available:
                # Track update available
                if self.analytics:
                    self.analytics.track_event("update_available", {
                        "current_version": self._get_current_version(),
                        "latest_version": latest_version,
                        "trigger": "manual"
                    })

                response = rumps.alert(
                    title="Update Available",
                    message=f"Molt-Speak {latest_version} is available!\n\nYou're currently on version {self._get_current_version()}.\n\nWould you like to update now?",
                    ok="Update Now",
                    cancel="Later"
                )

                if response == 1:
                    self._perform_update(install_command, latest_version)
            else:
                # Track no update
                if self.analytics:
                    self.analytics.track_event("update_check_completed", {
                        "update_available": False,
                        "trigger": "manual"
                    })

                rumps.alert(
                    title="No Updates Available",
                    message=f"You're already running the latest version ({self._get_current_version()})."
                )

        except ImportError:
            rumps.alert(
                title="Update Check Failed",
                message="Update checker not available. Please install: pip install packaging"
            )
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            _truncated_alert(
                title="Update Check Failed",
                message=f"Could not check for updates:\n\n{str(e)}"
            )

    def _perform_update(self, install_command, latest_version):
        """Perform the update."""
        # Track update started
        if self.analytics:
            self.analytics.track_event("update_started", {
                "latest_version": latest_version,
                "install_method": "curl_script"
            })

        # Show update instructions
        rumps.alert(
            title="Updating Molt-Speak",
            message=f"To update to version {latest_version}:\n\n1. Open Terminal\n2. Run this command:\n\n{install_command}\n\n3. Restart Molt-Speak",
            ok="Copy Command"
        )

        # Copy command to clipboard
        try:
            import subprocess
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                close_fds=True
            )
            process.communicate(install_command.encode('utf-8'))

            rumps.notification(
                title="Command Copied",
                subtitle="",
                message="Update command copied to clipboard. Paste in Terminal.",
                sound=False
            )
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")

    def _get_current_version(self):
        """Get the current app version."""
        try:
            version_file = self.project_dir / "VERSION"
            if version_file.exists():
                return version_file.read_text().strip()
            return "1.0.0"
        except Exception:
            return "1.0.0"

    def on_quit(self, sender):
        """Quit the menu bar app and stop all voice loop processes."""
        self.on_stop_all(None)

        # Flush analytics before exit — os._exit bypasses atexit handlers
        if self.analytics:
            try:
                self.analytics.shutdown()
            except Exception:
                pass

        force_cleanup()
        # Force kill by pattern as backup (SIGKILL)
        subprocess.run(["pkill", "-9", "-f", "unified_audio"], capture_output=True)
        subprocess.run(["pkill", "-9", "-f", "voice_pipeline"], capture_output=True)
        subprocess.run(["pkill", "-9", "-f", "mouth_pipeline"], capture_output=True)
        rumps.quit_application()
        # os._exit bypasses all cleanup and forces immediate termination
        # This ensures we actually quit even if something is blocking
        os._exit(0)


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
        subprocess.run(["bash", str(stop_script)], capture_output=True, cwd=str(project_dir))

    # Force kill by pattern as final backup
    subprocess.run(["pkill", "-9", "-f", "unified_audio"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "voice_pipeline"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "mouth_pipeline"], capture_output=True)


def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signum}, cleaning up...")
    # Flush analytics before cleanup (SIGTERM from moltspeak quit)
    try:
        from src.services.analytics import get_analytics
        get_analytics().shutdown()
    except Exception:
        pass
    force_cleanup()
    import sys
    sys.exit(0)


def main():
    """Main entry point."""
    # Register cleanup handlers
    atexit.register(force_cleanup)
    # Only handle SIGTERM, not SIGINT (to avoid interfering with parent process)
    signal.signal(signal.SIGTERM, signal_handler)

    # Ensure NSApplication is properly activated (fixes menu bar not showing on some Macs)
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        from Foundation import NSAutoreleasePool

        # Create autorelease pool for proper memory management
        # Keep reference to prevent garbage collection
        _pool = NSAutoreleasePool.alloc().init()  # noqa: F841

        app_instance = NSApplication.sharedApplication()
        # Use accessory policy for menu bar apps - shows in menu bar but not Dock
        app_instance.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        app_instance.activateIgnoringOtherApps_(True)

        logger.info("NSApplication initialized with accessory policy")
    except ImportError:
        logger.warning("PyObjC not available, using rumps defaults")
    except Exception as e:
        logger.warning("NSApplication setup warning: %s", e)

    try:
        app = VoiceLoopMenuBar()
        logger.info("VoiceLoopMenuBar created, starting run loop...")
        app.run()
    finally:
        # Ensure cleanup even if app.run() throws
        force_cleanup()


if __name__ == "__main__":
    main()
