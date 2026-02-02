"""Command protocol definitions for control server."""

from enum import Enum
from typing import Optional, Tuple


class Command(Enum):
    """Available commands."""
    PING = "PING"
    GET_STATUS = "GET_STATUS"
    GET_VOICES = "GET_VOICES"
    CHANGE_VOICE = "CHANGE_VOICE"
    CHANGE_RATE = "CHANGE_RATE"
    CHANGE_VOLUME = "CHANGE_VOLUME"
    CHANGE_MODE = "CHANGE_MODE"
    CLEAR_QUEUE = "CLEAR_QUEUE"
    STOP_SPEAKING = "STOP_SPEAKING"
    RELOAD_CONFIG = "RELOAD_CONFIG"
    SHUTDOWN = "SHUTDOWN"


class CommandProtocol:
    """Protocol for parsing and formatting commands."""

    @staticmethod
    def parse_command(command_str: str) -> Tuple[str, Optional[str]]:
        """
        Parse command string into command and arguments.

        Args:
            command_str: Raw command string

        Returns:
            Tuple of (command, args)

        Example:
            "CHANGE_VOICE:Samantha,local" -> ("CHANGE_VOICE", "Samantha,local")
            "PING" -> ("PING", None)
        """
        command_str = command_str.strip()
        if ":" in command_str:
            parts = command_str.split(":", 1)
            return parts[0], parts[1]
        return command_str, None

    @staticmethod
    def format_response(status: str, message: str) -> str:
        """
        Format response string.

        Args:
            status: Response status ("OK" or "ERROR")
            message: Response message

        Returns:
            Formatted response string

        Example:
            format_response("OK", "PONG") -> "OK:PONG\n"
        """
        return f"{status}:{message}\n"


class CommandResponse:
    """Helper class for creating command responses."""

    @staticmethod
    def ok(message: str) -> str:
        """Create successful response."""
        return CommandProtocol.format_response("OK", message)

    @staticmethod
    def error(message: str) -> str:
        """Create error response."""
        return CommandProtocol.format_response("ERROR", message)
