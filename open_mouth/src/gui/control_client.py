"""Control client for communicating with OpenClaw Mouth control server."""

import logging
import socket
from pathlib import Path
from typing import Optional, Tuple

from ..config import settings

logger = logging.getLogger(__name__)


class ControlClient:
    """Client for sending commands to the control server."""

    def __init__(self, socket_path: str = None):
        """
        Initialize control client.

        Args:
            socket_path: Path to Unix domain socket (defaults to project runtime)
        """
        if socket_path is None:
            socket_path = str(settings.RUNTIME_DIR / "mouth_control.sock")
        self.socket_path = Path(socket_path).expanduser()

    def send_command(self, command: str, timeout: float = 5.0) -> Optional[str]:
        """
        Send a command to the control server.

        Args:
            command: Command to send
            timeout: Socket timeout in seconds

        Returns:
            Response string or None if failed
        """
        try:
            # Create socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            # Connect
            sock.connect(str(self.socket_path))

            # Send command
            sock.sendall(command.encode('utf-8'))

            # Receive response
            response = sock.recv(1024).decode('utf-8')

            sock.close()

            return response.strip()

        except FileNotFoundError:
            logger.error(f"Socket not found: {self.socket_path}")
            logger.error("Is OpenClaw Mouth running with --enable-control?")
            return None

        except socket.timeout:
            logger.error("Socket timeout - server not responding")
            return None

        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return None

    def ping(self) -> bool:
        """
        Ping the server to check if it's alive.

        Returns:
            True if server responded, False otherwise
        """
        response = self.send_command("PING")
        return response == "OK:PONG" if response else False

    def get_status(self) -> Optional[Tuple[str, str, str, str]]:
        """
        Get current server status.

        Returns:
            Tuple of (status, voice, mode, current_text) or None if failed
        """
        response = self.send_command("GET_STATUS")
        if not response or not response.startswith("OK:"):
            return None

        try:
            # Parse response: "OK:STATUS|voice|mode|text"
            parts = response[3:].split("|")
            if len(parts) >= 4:
                return (parts[0], parts[1], parts[2], parts[3])
            return None

        except Exception as e:
            logger.error(f"Error parsing status: {e}")
            return None

    def change_voice(self, voice: str, mode: Optional[str] = None) -> bool:
        """
        Change the TTS voice.

        Args:
            voice: Voice identifier
            mode: TTS mode ("local" or "cloud"), None to keep current

        Returns:
            True if successful, False otherwise
        """
        if mode:
            command = f"CHANGE_VOICE:{voice},{mode}"
        else:
            command = f"CHANGE_VOICE:{voice}"

        response = self.send_command(command)

        if response and response.startswith("OK:"):
            logger.info(f"Voice changed to: {voice}")
            return True
        else:
            logger.error(f"Failed to change voice: {response}")
            return False

    def change_rate(self, rate: float) -> bool:
        """
        Change speech rate.

        Args:
            rate: Speech rate multiplier

        Returns:
            True if successful, False otherwise
        """
        response = self.send_command(f"CHANGE_RATE:{rate}")
        return bool(response and response.startswith("OK:"))

    def change_volume(self, volume: float) -> bool:
        """
        Change volume.

        Args:
            volume: Volume level (0.0 to 1.0)

        Returns:
            True if successful, False otherwise
        """
        response = self.send_command(f"CHANGE_VOLUME:{volume}")
        return bool(response and response.startswith("OK:"))

    def is_connected(self) -> bool:
        """
        Check if connection to server is possible.

        Returns:
            True if socket exists and server responds, False otherwise
        """
        if not self.socket_path.exists():
            return False

        return self.ping()
