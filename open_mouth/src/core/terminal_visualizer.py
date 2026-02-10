"""Terminal visualization for the speech system."""

import logging
import os
import sys
from datetime import datetime

from ..core.state_manager import SpeechState

logger = logging.getLogger(__name__)


class TerminalVisualizer:
    """Terminal-based visualizer for speech system status."""

    def __init__(self, enable_colors: bool = True):
        """
        Initialize the terminal visualizer.

        Args:
            enable_colors: Whether to use ANSI colors
        """
        self.enable_colors = enable_colors and self._supports_color()
        self.last_render = ""
        logger.debug("Terminal visualizer initialized")

    @staticmethod
    def _supports_color() -> bool:
        """
        Check if terminal supports ANSI colors.

        Returns:
            True if colors are supported
        """
        # Check if running in a TTY
        if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
            return False

        # Check TERM environment variable
        term = os.environ.get("TERM", "")
        if "color" in term or term in ("xterm", "screen", "linux"):
            return True

        return False

    def _colorize(self, text: str, color_code: str) -> str:
        """
        Apply ANSI color to text.

        Args:
            text: Text to colorize
            color_code: ANSI color code

        Returns:
            Colorized text if colors are enabled, otherwise plain text
        """
        if not self.enable_colors:
            return text

        reset = "\033[0m"
        return f"{color_code}{text}{reset}"

    def _get_status_color(self, status: str) -> str:
        """
        Get color code for status.

        Args:
            status: Status string

        Returns:
            ANSI color code
        """
        colors = {
            "IDLE": "\033[90m",      # Gray
            "QUEUED": "\033[93m",    # Yellow
            "SPEAKING": "\033[92m",  # Green
            "ERROR": "\033[91m",     # Red
        }
        return colors.get(status, "\033[0m")

    def _get_status_icon(self, status: str) -> str:
        """
        Get icon for status.

        Args:
            status: Status string

        Returns:
            Status icon
        """
        icons = {
            "IDLE": "🔇",
            "QUEUED": "⏳",
            "SPEAKING": "📢",
            "ERROR": "❌",
        }
        return icons.get(status, "❓")

    def _render_progress_bar(self, progress: float, width: int = 20) -> str:
        """
        Render a progress bar.

        Args:
            progress: Progress (0.0 to 1.0)
            width: Width of the progress bar

        Returns:
            Progress bar string
        """
        filled = int(progress * width)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        percentage = int(progress * 100)
        return f"[{bar}] {percentage}%"

    def _truncate_text(self, text: str, max_length: int = 60) -> str:
        """
        Truncate text to maximum length.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def _wrap_text(self, text: str, width: int = 70) -> list:
        """
        Wrap text to multiple lines at word boundaries.

        Args:
            text: Text to wrap
            width: Maximum width per line

        Returns:
            List of wrapped lines
        """
        if len(text) <= width:
            return [text]

        lines = []
        words = text.split()
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word)
            # +1 for the space between words
            if current_length + word_length + len(current_line) <= width:
                current_line.append(word)
                current_length += word_length
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [text[:width]]

    def render_full(self, state: SpeechState) -> str:
        """
        Render full visualization of current state.

        Args:
            state: Current speech state

        Returns:
            Rendered visualization string
        """
        lines = []

        # Calculate dynamic width based on content
        content_width = 40  # Minimum width
        if state.current_text:
            content_width = max(content_width, min(len(state.current_text), 100))
        if state.queued_items:
            for item in state.queued_items[:1]:
                content_width = max(content_width, min(len(item), 100))

        # Cap at reasonable maximum
        width = min(content_width + 10, 100)

        # Use different border style when speaking
        if state.status == "SPEAKING":
            border_style = "═"
            corner_tl = "╔"
            corner_tr = "╗"
            corner_bl = "╚"
            corner_br = "╝"
            border_v = "║"
            border_color = "\033[92m"  # Bright green
        else:
            border_style = "─"
            corner_tl = "┌"
            corner_tr = "┐"
            corner_bl = "└"
            corner_br = "┘"
            border_v = "│"
            border_color = "\033[0m"  # Default

        # Header with dynamic border
        header = f"{corner_tl}{border_style * (width - 2)}{corner_tr}"
        if self.enable_colors and state.status == "SPEAKING":
            header = self._colorize(header, border_color)
        lines.append(header)

        # Add prominent "AGENT SPEAKING" banner when speaking
        if state.status == "SPEAKING":
            banner = "🔊 AGENT SPEAKING - EARS SHOULD PAUSE 🔊"
            banner_padding = (width - 2 - len(banner)) // 2
            banner_line = f"{border_v}{' ' * banner_padding}{banner}{' ' * (width - 2 - banner_padding - len(banner))}{border_v}"
            if self.enable_colors:
                banner_line = self._colorize(banner_line, "\033[1;92m")  # Bold bright green
            lines.append(banner_line)

            # Separator
            separator = f"{border_v}{border_style * (width - 2)}{border_v}"
            if self.enable_colors:
                separator = self._colorize(separator, border_color)
            lines.append(separator)

        # Helper to format line with padding
        def format_line(content: str) -> str:
            # Strip ANSI codes to get actual visible length
            import re
            ansi_pattern = re.compile(r'\033\[[0-9;]+m')
            visible_content = ansi_pattern.sub('', content)
            visible_len = len(visible_content)
            padding = " " * max(0, width - 4 - visible_len)
            return f"{border_v} {content}{padding}{border_v}"

        # Status line
        status_icon = self._get_status_icon(state.status)
        status_text = self._colorize(
            f"{status_icon} {state.status}",
            self._get_status_color(state.status)
        )
        lines.append(format_line(f"Status: {status_text}"))

        # Current text (if speaking) - show full text with wrapping
        if state.status == "SPEAKING" and state.current_text:
            wrapped_lines = self._wrap_text(state.current_text, width - 10)
            for i, wrapped_line in enumerate(wrapped_lines):
                label = "Text: " if i == 0 else "      "
                lines.append(format_line(f"{label}{wrapped_line}"))

            # Progress bar
            progress_bar = self._render_progress_bar(state.progress, min(50, width - 20))
            lines.append(format_line(f"Progress: {progress_bar}"))

        # Queue status
        if state.queue_size > 0:
            queue_text = f"Queue: {state.queue_size} item(s)"
            lines.append(format_line(queue_text))

            # Show queued items preview - full text with wrapping
            if state.queued_items:
                for i, item in enumerate(state.queued_items[:3], 1):
                    wrapped_lines = self._wrap_text(item, width - 15)
                    for j, wrapped_line in enumerate(wrapped_lines):
                        if j == 0:
                            item_text = f"  {i}. {wrapped_line}"
                        else:
                            item_text = f"     {wrapped_line}"
                        # Use yellow color for queued items
                        if self.enable_colors:
                            item_text = self._colorize(item_text, "\033[93m")
                        lines.append(format_line(item_text))

        # Voice
        voice_display = state.voice.split("-")[-1] if state.voice else "Unknown"
        voice_text = f"Voice: {voice_display}"
        lines.append(format_line(voice_text))

        # Statistics
        stats_text = f"Total spoken: {state.total_spoken}"
        lines.append(format_line(stats_text))

        # Error message (if any)
        if state.error_message:
            error_text = self._colorize(
                f"⚠️  {state.error_message[:width-10]}",
                "\033[91m"  # Red
            )
            lines.append(format_line(error_text))

        # Timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        time_text = f"Last update: {timestamp}"
        lines.append(format_line(time_text))

        # Footer with dynamic border
        footer = f"{corner_bl}{border_style * (width - 2)}{corner_br}"
        if self.enable_colors and state.status == "SPEAKING":
            footer = self._colorize(footer, border_color)
        lines.append(footer)

        return "\n".join(lines)

    def render_compact(self, state: SpeechState) -> str:
        """
        Render compact visualization (single line).

        Args:
            state: Current speech state

        Returns:
            Compact visualization string
        """
        icon = self._get_status_icon(state.status)
        status = self._colorize(state.status, self._get_status_color(state.status))

        parts = []

        # Add prominent indicator when speaking
        if state.status == "SPEAKING":
            speaking_indicator = self._colorize("🔊 AGENT SPEAKING", "\033[1;92m")  # Bold bright green
            parts.append(speaking_indicator)
            parts.append("|")

        parts.append(f"{icon} {status}")

        if state.status == "SPEAKING" and state.current_text:
            # Show more text in compact mode (100 chars instead of 40)
            text = self._truncate_text(state.current_text, 100)
            parts.append(f"| {text}")

        if state.queue_size > 0:
            parts.append(f"| Queue: {state.queue_size}")
            # Show first queued item in compact mode with more text
            if state.queued_items:
                first_item = self._truncate_text(state.queued_items[0], 80)
                queued_preview = self._colorize(f"Next: {first_item}", "\033[93m")
                parts.append(f"| {queued_preview}")

        parts.append(f"| Total: {state.total_spoken}")

        return " ".join(parts)

    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        os.system("clear" if os.name != "nt" else "cls")

    def display(self, state: SpeechState, compact: bool = False) -> None:
        """
        Display the current state in the terminal.

        Args:
            state: Current speech state
            compact: Use compact mode (single line)
        """
        try:
            if compact:
                rendered = self.render_compact(state)
                # Use carriage return to overwrite the same line
                print(f"\r{rendered}", end="", flush=True)
            else:
                rendered = self.render_full(state)

                # Only re-render if state changed
                if rendered != self.last_render:
                    self.clear_screen()
                    print(rendered, flush=True)
                    self.last_render = rendered

        except Exception as e:
            logger.error(f"Error displaying visualization: {e}")

    def display_startup_banner(self) -> None:
        """Display startup banner."""
        banner = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║                        🎙️  OpenClaw Mouth TTS System                         ║
║                                                                               ║
║                    Text-to-Speech Output for AI Agents                        ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""
        print(self._colorize(banner, "\033[96m"))  # Cyan

    def display_shutdown_message(self) -> None:
        """Display shutdown message."""
        message = "\n\n✅ Speech system shutdown complete.\n"
        print(self._colorize(message, "\033[92m"))  # Green
