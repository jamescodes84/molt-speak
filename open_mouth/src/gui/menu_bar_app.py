"""macOS menu bar application for OpenClaw Mouth voice control."""

import logging
import rumps
from typing import Optional, List, Dict
from .control_client import ControlClient
from .voice_manager import VoiceManager
from ..config.voice_config import VoiceConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenClawMenuBar(rumps.App):
    """Menu bar application for controlling OpenClaw Mouth."""

    def __init__(self):
        """Initialize menu bar app."""
        super().__init__("🎙️", quit_button=None)  # type: ignore[arg-type]

        # Initialize components
        self.control = ControlClient()
        self.voice_mgr = VoiceManager()
        self.config = VoiceConfig()

        # State
        self.current_voice = "Unknown"
        self.current_mode = "unknown"
        self.current_status = "IDLE"
        self.is_connected = False

        # Build initial menu
        self.build_menu()

        # Start status update timer
        self.timer = rumps.Timer(self.update_status, 2.0)
        self.timer.start()

        logger.info("OpenClaw Menu Bar initialized")

    def build_menu(self):
        """Build the menu structure."""
        # Clear existing menu
        self.menu.clear()

        # Header section
        self.menu.add(rumps.MenuItem(f"Current: {self.current_voice}", callback=None))
        self.menu.add(rumps.MenuItem(f"Status: {self.current_status}", callback=None))

        if not self.is_connected:
            self.menu.add(rumps.MenuItem("⚠️  Not Connected", callback=None))

        self.menu.add(rumps.separator)

        # Local voices submenu
        local_menu = rumps.MenuItem("⚡ Local Voices")
        local_voices = self.voice_mgr.get_local_voices()

        # Group by common English voices first
        common_voices = ["Alex", "Samantha", "Daniel", "Victoria", "Allison", "Karen", "Moira"]
        other_voices = []

        for voice_data in local_voices:
            voice_name = voice_data["name"]
            if voice_data["locale"].startswith("en_"):
                if voice_name in common_voices:
                    item = rumps.MenuItem(
                        voice_name,
                        callback=lambda sender, v=voice_name: self.on_voice_select(v, "local")
                    )
                    if voice_name == self.current_voice and self.current_mode == "local":
                        item.state = True
                    local_menu.add(item)
                else:
                    other_voices.append(voice_name)

        # Add separator and other voices
        if other_voices:
            local_menu.add(rumps.separator)
            local_menu.add(rumps.MenuItem(f"--- Other English Voices ({len(other_voices)}) ---", callback=None))

            for voice_name in sorted(other_voices)[:15]:  # Limit to 15
                item = rumps.MenuItem(
                    voice_name,
                    callback=lambda sender, v=voice_name: self.on_voice_select(v, "local")
                )
                if voice_name == self.current_voice and self.current_mode == "local":
                    item.state = True
                local_menu.add(item)

        self.menu.add(local_menu)

        # Cloud voices submenu
        cloud_menu = rumps.MenuItem("☁️  Cloud Voices")
        cloud_voices = self.voice_mgr.get_cloud_voices()

        # Group by US voices first
        us_voices = [v for v in cloud_voices if v["locale"].startswith("en-US")][:12]  # Limit to 12

        for voice_data in us_voices:
            voice_id = voice_data["name"]
            # Shorten display name
            display_name = voice_id.replace("en-US-", "").replace("Neural", "")

            item = rumps.MenuItem(
                display_name,
                callback=lambda sender, v=voice_id: self.on_voice_select(v, "cloud")
            )
            if voice_id == self.current_voice and self.current_mode == "cloud":
                item.state = True
            cloud_menu.add(item)

        self.menu.add(cloud_menu)

        self.menu.add(rumps.separator)

        # Favorites section
        favorites = self.config.get_favorites()
        if favorites:
            fav_menu = rumps.MenuItem("★ Favorites")
            for fav in favorites[:5]:  # Limit to 5
                voice_name = fav["name"]
                voice_type = fav["type"]
                display_name = f"{voice_name} ({'⚡' if voice_type == 'local' else '☁️'})"

                item = rumps.MenuItem(
                    display_name,
                    callback=lambda sender, v=voice_name, t=voice_type: self.on_voice_select(v, t)
                )
                fav_menu.add(item)

            self.menu.add(fav_menu)

        # Add/remove favorite for current voice
        if self.current_voice != "Unknown":
            is_fav = self.config.is_favorite(self.current_voice, self.current_mode)
            if is_fav:
                self.menu.add(rumps.MenuItem("Remove from Favorites", callback=self.on_remove_favorite))
            else:
                self.menu.add(rumps.MenuItem("Add to Favorites", callback=self.on_add_favorite))

        self.menu.add(rumps.separator)

        # Refresh voices
        self.menu.add(rumps.MenuItem("🔄 Refresh Voices", callback=self.on_refresh_voices))

        self.menu.add(rumps.separator)

        # Visualizer
        self.menu.add(rumps.MenuItem("📊 Show Visualizer", callback=self.on_show_visualizer))

        self.menu.add(rumps.separator)

        # System controls
        self.menu.add(rumps.MenuItem("Reconnect", callback=self.on_reconnect))
        self.menu.add(rumps.MenuItem("Quit", callback=self.on_quit))

    def update_status(self, sender):
        """Update status from server."""
        try:
            # Check connection
            if not self.control.is_connected():
                if self.is_connected:
                    # Connection lost
                    self.is_connected = False
                    self.title = "🎙️ ⚠️"
                    self.build_menu()
                return

            # Get status
            status = self.control.get_status()
            if status:
                new_status, new_voice, new_mode, _ = status

                # Check if anything changed
                if (new_voice != self.current_voice or
                    new_mode != self.current_mode or
                    new_status != self.current_status or
                    not self.is_connected):

                    self.current_voice = new_voice
                    self.current_mode = new_mode
                    self.current_status = new_status
                    self.is_connected = True

                    # Update title based on status
                    if new_status == "SPEAKING":
                        self.title = "🎙️ 🔊"
                    else:
                        self.title = "🎙️"

                    # Rebuild menu to show current voice
                    self.build_menu()

        except Exception as e:
            logger.error(f"Error updating status: {e}")

    def on_voice_select(self, voice: str, mode: str):
        """
        Handle voice selection.

        Args:
            voice: Voice identifier
            mode: "local" or "cloud"
        """
        try:
            logger.info(f"Changing voice to: {voice} ({mode})")

            # Change voice via control client
            success = self.control.change_voice(voice, mode)

            if success:
                rumps.notification(
                    "Voice Changed",
                    "",
                    f"Now using {voice}"
                )
                self.current_voice = voice
                self.current_mode = mode
                self.build_menu()
            else:
                rumps.alert(
                    "Voice Change Failed",
                    "Could not change voice. Check that OpenClaw Mouth is running with --enable-control flag."
                )

        except Exception as e:
            logger.error(f"Error changing voice: {e}")
            rumps.alert("Error", f"Failed to change voice: {e}")

    def on_add_favorite(self, sender):
        """Add current voice to favorites."""
        if self.current_voice != "Unknown":
            self.config.add_favorite(self.current_voice, self.current_mode)
            self.build_menu()
            rumps.notification("Favorite Added", "", f"{self.current_voice} added to favorites")

    def on_remove_favorite(self, sender):
        """Remove current voice from favorites."""
        if self.current_voice != "Unknown":
            self.config.remove_favorite(self.current_voice, self.current_mode)
            self.build_menu()
            rumps.notification("Favorite Removed", "", f"{self.current_voice} removed from favorites")

    def on_refresh_voices(self, sender):
        """Refresh voice list from system/cloud."""
        try:
            logger.info("Refreshing voice list...")
            self.voice_mgr.get_local_voices(force_refresh=True)
            self.voice_mgr.get_cloud_voices(force_refresh=True)
            self.build_menu()
            rumps.notification("Voices Refreshed", "", "Voice list updated")
        except Exception as e:
            logger.error(f"Error refreshing voices: {e}")
            rumps.alert("Error", f"Failed to refresh voices: {e}")

    def on_reconnect(self, sender):
        """Attempt to reconnect to control server."""
        if self.control.ping():
            rumps.notification("Connected", "", "Successfully connected to OpenClaw Mouth")
            self.is_connected = True
            self.build_menu()
        else:
            rumps.alert(
                "Connection Failed",
                "Could not connect to OpenClaw Mouth.\n\n" +
                "Make sure it's running with:\n" +
                "./start_speech_system.sh --enable-control --local"
            )

    def on_show_visualizer(self, sender):
        """Open a new terminal window showing the visualizer."""
        import subprocess
        import os

        # Get the project directory
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # AppleScript to open new Terminal window with visualizer
        script = f'''
        tell application "Terminal"
            activate
            do script "cd '{project_dir}' && tail -f /tmp/openclaw_mouth.log"
        end tell
        '''

        try:
            subprocess.run(["osascript", "-e", script], check=True)
        except Exception as e:
            logger.error(f"Error opening visualizer: {e}")
            rumps.alert("Error", f"Failed to open visualizer: {e}")

    def on_quit(self, sender):
        """Quit the application."""
        rumps.quit_application()


def main():
    """Main entry point."""
    app = OpenClawMenuBar()
    app.run()


if __name__ == "__main__":
    main()
