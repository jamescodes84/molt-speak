"""
Agent Messenger

Sends messages to the agent when the voice loop starts and stops.
Creates a special instructions file that the agent should read on startup.
"""

import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentMessenger:
    """
    Sends messages to the agent about voice loop status.

    Creates an agent_instructions.active file when the voice loop starts,
    and removes it when the loop stops.
    """

    def __init__(self, openclaw_dir: Path, instructions_file: Path):
        """
        Initialize the agent messenger.

        Args:
            openclaw_dir: Path to ~/.openclaw directory
            instructions_file: Path to AGENT_INSTRUCTIONS.txt
        """
        self.openclaw_dir = openclaw_dir
        self.instructions_file = instructions_file
        self.active_instructions_file = openclaw_dir / "agent_instructions.active"
        self.shutdown_message_file = openclaw_dir / "agent_shutdown.signal"

    def send_startup_instructions(self) -> bool:
        """
        Send agent instructions on voice loop startup.

        Creates ~/.openclaw/agent_instructions.active with the full
        AGENT_INSTRUCTIONS.txt content plus activation metadata.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read the instructions file
            if not self.instructions_file.exists():
                logger.error(f"Instructions file not found: {self.instructions_file}")
                return False

            instructions = self.instructions_file.read_text()

            # Create active instructions with metadata
            timestamp = datetime.now().isoformat()
            active_content = f"""{'=' * 77}
VOICE LOOP ACTIVATED - {timestamp}
{'=' * 77}

The OpenClaw voice loop is now ACTIVE. You can have voice conversations!

SYSTEMS RUNNING:
  ✅ Integration Coordinator (echo prevention)
  ✅ Ready for OpenClaw Mouth (voice output)
  ✅ Ready for OpenClaw Ears (voice input)

READ THE INSTRUCTIONS BELOW CAREFULLY:

{'=' * 77}

{instructions}

{'=' * 77}
END OF VOICE LOOP INSTRUCTIONS
{'=' * 77}

This file will be removed when the voice loop shuts down.
"""

            # Write to active instructions file
            self.active_instructions_file.write_text(active_content)
            logger.info(f"Sent startup instructions to agent: {self.active_instructions_file}")

            # Also log a summary
            logger.info("=" * 60)
            logger.info("📢 AGENT INSTRUCTIONS ACTIVATED")
            logger.info("=" * 60)
            logger.info(f"Instructions file: {self.active_instructions_file}")
            logger.info("Agent should read this file to learn about voice loop usage")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"Failed to send startup instructions: {e}", exc_info=True)
            return False

    def send_shutdown_message(self) -> bool:
        """
        Send shutdown message to agent.

        Creates ~/.openclaw/agent_shutdown.signal to notify the agent
        that the voice loop is shutting down.

        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = datetime.now().isoformat()
            shutdown_content = f"""{'=' * 77}
VOICE LOOP DEACTIVATED - {timestamp}
{'=' * 77}

The OpenClaw voice loop has been SHUT DOWN.

SYSTEMS STOPPED:
  ❌ Integration Coordinator (stopped)
  ❌ Voice output may not be available
  ❌ Voice input may not be available

PREVIOUS INSTRUCTIONS ARE NOW VOID:
  - You can no longer send voice output via ~/.openclaw/speech_output.txt
  - You may no longer receive voice input automatically
  - Echo prevention is no longer active

If the voice loop is restarted, you will receive new instructions.

{'=' * 77}
"""

            # Write shutdown message
            self.shutdown_message_file.write_text(shutdown_content)
            logger.info(f"Sent shutdown message to agent: {self.shutdown_message_file}")

            # Remove active instructions file
            if self.active_instructions_file.exists():
                self.active_instructions_file.unlink()
                logger.info(f"Removed active instructions: {self.active_instructions_file}")

            # Log summary
            logger.info("=" * 60)
            logger.info("📢 VOICE LOOP DEACTIVATED")
            logger.info("=" * 60)
            logger.info("Agent has been notified of shutdown")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"Failed to send shutdown message: {e}", exc_info=True)
            return False

    def cleanup(self) -> None:
        """
        Clean up all messenger files.

        Removes active instructions and shutdown message files.
        """
        try:
            if self.active_instructions_file.exists():
                self.active_instructions_file.unlink()
                logger.debug(f"Cleaned up: {self.active_instructions_file}")

            if self.shutdown_message_file.exists():
                self.shutdown_message_file.unlink()
                logger.debug(f"Cleaned up: {self.shutdown_message_file}")

        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
