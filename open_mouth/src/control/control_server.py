"""Unix socket control server for runtime configuration."""

import json
import logging
import socket
import threading
from pathlib import Path
from typing import Optional, Callable

from .command_protocol import CommandProtocol, CommandResponse
from ..config import settings

logger = logging.getLogger(__name__)


class ControlServer:
    """Unix domain socket server for control commands."""

    def __init__(
        self,
        socket_path: str = None,
        command_handler: Optional[Callable] = None
    ):
        # Default to project runtime directory
        if socket_path is None:
            socket_path = str(settings.RUNTIME_DIR / "mouth_control.sock")
        """
        Initialize control server.

        Args:
            socket_path: Path to Unix domain socket
            command_handler: Callback function for handling commands
                            Signature: handler(command: str, args: str) -> str
        """
        self.socket_path = Path(socket_path).expanduser()
        self.command_handler = command_handler
        self.running = False
        self.sock = None
        self.server_thread = None

    def start(self) -> bool:
        """
        Start the control server.

        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Remove existing socket file if present
            if self.socket_path.exists():
                self.socket_path.unlink()

            # Create socket
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.bind(str(self.socket_path))
            self.sock.listen(5)
            self.sock.settimeout(1.0)  # Allow checking running flag

            self.running = True

            # Start accept loop in separate thread
            self.server_thread = threading.Thread(
                target=self._accept_loop,
                name="ControlServer",
                daemon=True
            )
            self.server_thread.start()

            logger.info(f"Control server started on {self.socket_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to start control server: {e}")
            return False

    def stop(self) -> None:
        """Stop the control server."""
        try:
            self.running = False

            if self.sock:
                self.sock.close()

            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=2.0)

            # Clean up socket file
            if self.socket_path.exists():
                self.socket_path.unlink()

            logger.info("Control server stopped")

        except Exception as e:
            logger.error(f"Error stopping control server: {e}")

    def _accept_loop(self) -> None:
        """Accept incoming connections."""
        logger.info("Control server accept loop started")

        while self.running:
            try:
                # Accept connection (with timeout)
                try:
                    client_sock, _ = self.sock.accept()
                except socket.timeout:
                    continue

                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock,),
                    daemon=True
                )
                client_thread.start()

            except Exception as e:
                if self.running:
                    logger.error(f"Error in accept loop: {e}")

        logger.info("Control server accept loop stopped")

    def _handle_client(self, client_sock: socket.socket) -> None:
        """
        Handle client connection.

        Args:
            client_sock: Client socket
        """
        try:
            # Receive command
            data = client_sock.recv(1024).decode('utf-8')
            if not data:
                return

            # Parse command
            command, args = CommandProtocol.parse_command(data)

            logger.debug(f"Received command: {command} with args: {args}")

            # Handle command
            response = self._handle_command(command, args)

            # Send response
            client_sock.sendall(response.encode('utf-8'))

        except Exception as e:
            logger.error(f"Error handling client: {e}")
            try:
                error_response = CommandResponse.error(str(e))
                client_sock.sendall(error_response.encode('utf-8'))
            except:
                pass

        finally:
            client_sock.close()

    def _handle_command(self, command: str, args: Optional[str]) -> str:
        """
        Handle a command.

        Args:
            command: Command name
            args: Command arguments

        Returns:
            Response string
        """
        # Built-in commands
        if command == "PING":
            return CommandResponse.ok("PONG")

        # Delegate to handler if provided
        if self.command_handler:
            try:
                return self.command_handler(command, args)
            except Exception as e:
                logger.error(f"Command handler error: {e}")
                return CommandResponse.error(f"Command handler error: {e}")

        # Unknown command
        return CommandResponse.error(f"Unknown command: {command}")
