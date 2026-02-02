#!/usr/bin/env python3
"""
Terminal-based audio visualizer for embedding in TUI
Shows audio levels and transcription status in terminal
"""

import sys
import time
from collections import deque


class TerminalVisualizer:
    """Compact audio visualizer for terminal embedding"""

    def __init__(self, width=60):
        self.width = width
        self.amplitude_history = deque(maxlen=width)
        self.current_amplitude = 0
        self.peak_amplitude = 0
        self.is_speaking = False
        self.last_transcription = ""
        self.threshold = 500

    def update(self, amplitude, is_speaking=False):
        """Update visualizer with new amplitude"""
        self.current_amplitude = amplitude
        self.amplitude_history.append(amplitude)
        self.is_speaking = is_speaking

        if amplitude > self.peak_amplitude:
            self.peak_amplitude = amplitude

    def set_transcription(self, text):
        """Update the latest transcription"""
        self.last_transcription = text

    def render_compact(self):
        """Render a compact single-line status"""
        # Status indicator
        if self.is_speaking:
            status = "🗣️ "
        elif self.current_amplitude > self.threshold * 0.5:
            status = "📢"
        else:
            status = "🔇"

        # Audio level bar
        bar_width = 30
        filled = int((self.current_amplitude / 5000) * bar_width)
        filled = min(filled, bar_width)

        if self.current_amplitude > self.threshold:
            color = '\033[92m'  # Green
        elif self.current_amplitude > self.threshold * 0.5:
            color = '\033[33m'  # Yellow
        else:
            color = '\033[90m'  # Gray

        bar = color + '█' * filled + '\033[90m' + '░' * (bar_width - filled) + '\033[0m'

        # Last transcription (truncated)
        trans = self.last_transcription[:40] if self.last_transcription else "Listening..."

        return f"{status} {bar} │ {trans}"

    def render_waveform(self):
        """Render ASCII waveform"""
        if len(self.amplitude_history) == 0:
            return ' ' * self.width

        history_list = list(self.amplitude_history)
        max_amp = max(history_list) if history_list else 1
        chars = ' ▁▂▃▄▅▆▇█'

        waveform = ''
        for amp in history_list:
            idx = int((amp / max_amp) * (len(chars) - 1)) if max_amp > 0 else 0
            idx = min(idx, len(chars) - 1)

            if amp > self.threshold:
                waveform += f'\033[92m{chars[idx]}\033[0m'  # Green
            elif amp > self.threshold * 0.7:
                waveform += f'\033[33m{chars[idx]}\033[0m'  # Yellow
            else:
                waveform += f'\033[90m{chars[idx]}\033[0m'  # Gray

        return waveform

    def render_full(self):
        """Render full multi-line visualizer"""
        lines = []

        # Status line
        if self.is_speaking:
            status = '\033[92m🗣️  SPEAKING\033[0m'
        elif self.current_amplitude > self.threshold * 0.5:
            status = '\033[33m📢 DETECTED\033[0m'
        else:
            status = '\033[90m🔇 QUIET   \033[0m'

        lines.append(status)

        # Level bar
        bar_width = 50
        filled = int((self.current_amplitude / 5000) * bar_width)
        filled = min(filled, bar_width)

        if self.current_amplitude > self.threshold:
            color = '\033[92m'
        elif self.current_amplitude > self.threshold * 0.5:
            color = '\033[33m'
        else:
            color = '\033[90m'

        bar = color + '█' * filled + '\033[90m' + '░' * (bar_width - filled) + '\033[0m'
        lines.append(f"Level: [{bar}] {self.current_amplitude:6.0f}")

        # Waveform
        lines.append(f"Wave:  {self.render_waveform()}")

        # Last transcription
        if self.last_transcription:
            trans = self.last_transcription[:70]
            lines.append(f'💬 "{trans}"')
        else:
            lines.append('💬 Listening...')

        return '\n'.join(lines)

    def clear_lines(self, num_lines):
        """Clear N lines above cursor"""
        for _ in range(num_lines):
            sys.stdout.write('\033[F')  # Move up
            sys.stdout.write('\033[K')  # Clear line

    def display(self, mode='compact'):
        """Display the visualizer"""
        if mode == 'compact':
            output = self.render_compact()
            num_lines = 1
        else:
            output = self.render_full()
            num_lines = 4

        # Clear previous lines
        self.clear_lines(num_lines)

        # Print new output
        print(output)
        sys.stdout.flush()


def test_visualizer():
    """Test the terminal visualizer"""
    import random

    viz = TerminalVisualizer(width=60)

    # Print initial blank lines
    print("\n" * 4)

    try:
        for i in range(100):
            # Simulate audio levels
            if i % 20 < 10:
                amp = random.randint(100, 400)  # Quiet
                speaking = False
            else:
                amp = random.randint(500, 2000)  # Speaking
                speaking = True
                if i % 20 == 10:
                    viz.set_transcription("Hello, this is a test transcription")

            viz.update(amp, speaking)
            viz.display(mode='full')
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nTest stopped")


if __name__ == '__main__':
    test_visualizer()
