#!/usr/bin/env python3
"""
Real-time Audio Level Visualizer
Shows live audio input levels with visual feedback
"""

import sys
import os
import time
import numpy as np
import sounddevice as sd
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openclaw-ears'))

class AudioVisualizer:
    """Real-time audio level visualization"""
    
    def __init__(self, 
                 device=None,
                 sample_rate=16000,
                 block_duration=0.05,
                 speech_threshold=500,
                 history_size=50):
        """
        Initialize audio visualizer
        
        :param device: Input device index
        :param sample_rate: Audio sample rate
        :param block_duration: Duration of each analysis block (seconds)
        :param speech_threshold: Amplitude threshold for speech detection
        :param history_size: Number of historical samples to display
        """
        self.device = device
        self.sample_rate = sample_rate
        self.block_size = int(sample_rate * block_duration)
        self.speech_threshold = speech_threshold
        
        # Amplitude history for waveform
        self.amplitude_history = deque(maxlen=history_size)
        
        # Peak hold
        self.peak_amplitude = 0
        self.peak_hold_time = 0
        
        # Speech detection state
        self.is_speaking = False
        self.speech_start_time = None
        
    def _audio_callback(self, indata, frames, time_info, status):
        """Process incoming audio"""
        if status:
            print(f"⚠️  {status}", file=sys.stderr)
        
        # Calculate RMS amplitude
        amplitude = np.sqrt(np.mean(indata**2)) * 10000
        
        # Update history
        self.amplitude_history.append(amplitude)
        
        # Update peak hold
        current_time = time.time()
        if amplitude > self.peak_amplitude:
            self.peak_amplitude = amplitude
            self.peak_hold_time = current_time
        elif current_time - self.peak_hold_time > 2.0:
            # Reset peak after 2 seconds
            self.peak_amplitude = amplitude
        
        # Speech detection
        was_speaking = self.is_speaking
        self.is_speaking = amplitude > self.speech_threshold
        
        if self.is_speaking and not was_speaking:
            self.speech_start_time = current_time
        elif not self.is_speaking and was_speaking:
            duration = current_time - self.speech_start_time if self.speech_start_time else 0
            if duration > 0.5:  # Only report if > 0.5 seconds
                print(f"\n🗣️  Speech detected ({duration:.1f}s)", file=sys.stderr)
    
    def _render_bar(self, value, max_value, width=50):
        """Render a horizontal bar graph"""
        filled = int((value / max_value) * width) if max_value > 0 else 0
        filled = min(filled, width)
        
        # Color coding
        if value < self.speech_threshold * 0.5:
            color = '\033[90m'  # Dark gray - too quiet
        elif value < self.speech_threshold:
            color = '\033[33m'  # Yellow - getting there
        else:
            color = '\033[92m'  # Green - speech level
        
        reset = '\033[0m'
        
        bar = '█' * filled + '░' * (width - filled)
        return f"{color}{bar}{reset}"
    
    def _render_waveform(self, width=50):
        """Render a mini waveform from history"""
        if len(self.amplitude_history) == 0:
            return ' ' * width
        
        # Sample the history to fit width
        history_list = list(self.amplitude_history)
        step = len(history_list) / width
        sampled = [history_list[int(i * step)] for i in range(width)]
        
        max_amp = max(sampled) if sampled else 1
        
        # Create sparkline
        chars = ' ▁▂▃▄▅▆▇█'
        waveform = ''
        for amp in sampled:
            idx = int((amp / max_amp) * (len(chars) - 1)) if max_amp > 0 else 0
            idx = min(idx, len(chars) - 1)
            
            # Color based on speech threshold
            if amp > self.speech_threshold:
                waveform += f'\033[92m{chars[idx]}\033[0m'  # Green
            elif amp > self.speech_threshold * 0.7:
                waveform += f'\033[33m{chars[idx]}\033[0m'  # Yellow
            else:
                waveform += f'\033[90m{chars[idx]}\033[0m'  # Gray
        
        return waveform
    
    def start(self):
        """Start the visualizer"""
        print("🎙️  Audio Level Visualizer")
        print("=" * 70)
        print(f"📡 Device: {self.device if self.device else 'Default'}")
        print(f"🎯 Speech Threshold: {self.speech_threshold}")
        print(f"📊 Sample Rate: {self.sample_rate} Hz")
        print()
        print("Press Ctrl+C to stop")
        print("=" * 70)
        print()
        
        try:
            with sd.InputStream(
                device=self.device,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self._audio_callback
            ):
                while True:
                    time.sleep(0.05)
                    
                    # Get current amplitude
                    current_amp = self.amplitude_history[-1] if self.amplitude_history else 0
                    
                    # Clear line and render
                    sys.stdout.write('\033[2K\r')  # Clear line
                    
                    # Current level bar
                    bar = self._render_bar(current_amp, 5000, width=40)
                    
                    # Status indicator
                    if self.is_speaking:
                        status = '\033[92m🗣️  SPEAKING\033[0m'
                    elif current_amp > self.speech_threshold * 0.5:
                        status = '\033[33m📢 Detected\033[0m'
                    else:
                        status = '\033[90m🔇 Quiet   \033[0m'
                    
                    # Display
                    sys.stdout.write(
                        f"{status}  [{bar}] {current_amp:6.0f} "
                        f"(peak: {self.peak_amplitude:6.0f})"
                    )
                    sys.stdout.flush()
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopped")
    
    def start_with_waveform(self):
        """Start visualizer with waveform display"""
        print("🎙️  Audio Level Visualizer (Waveform Mode)")
        print("=" * 70)
        print(f"📡 Device: {self.device if self.device else 'Default'}")
        print(f"🎯 Speech Threshold: {self.speech_threshold}")
        print(f"📊 Sample Rate: {self.sample_rate} Hz")
        print()
        print("Press Ctrl+C to stop")
        print("=" * 70)
        print("\n" * 5)  # Space for display
        
        try:
            with sd.InputStream(
                device=self.device,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self._audio_callback
            ):
                while True:
                    time.sleep(0.05)
                    
                    current_amp = self.amplitude_history[-1] if self.amplitude_history else 0
                    
                    # Move cursor up 5 lines
                    sys.stdout.write('\033[5A')
                    
                    # Status line
                    if self.is_speaking:
                        status = '\033[92m🗣️  SPEAKING\033[0m'
                        status_bar = '█' * 10
                    elif current_amp > self.speech_threshold * 0.5:
                        status = '\033[33m📢 DETECTED\033[0m'
                        status_bar = '▓' * 10
                    else:
                        status = '\033[90m🔇 QUIET   \033[0m'
                        status_bar = '░' * 10
                    
                    # Render display
                    bar = self._render_bar(current_amp, 5000, width=50)
                    waveform = self._render_waveform(width=60)
                    
                    sys.stdout.write(f'\033[2K{status}  {status_bar}\n')
                    sys.stdout.write(f'\033[2KCurrent: [{bar}] {current_amp:6.0f}\n')
                    sys.stdout.write(f'\033[2KPeak:    {self.peak_amplitude:6.0f} │ Threshold: {self.speech_threshold}\n')
                    sys.stdout.write(f'\033[2K{"─" * 70}\n')
                    sys.stdout.write(f'\033[2K{waveform}\n')
                    
                    sys.stdout.flush()
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopped")

def main():
    """Run the visualizer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time audio level visualizer')
    parser.add_argument('--device', type=int, help='Input device index')
    parser.add_argument('--threshold', type=int, default=500, help='Speech threshold')
    parser.add_argument('--waveform', action='store_true', help='Show waveform display')
    
    args = parser.parse_args()
    
    visualizer = AudioVisualizer(
        device=args.device,
        speech_threshold=args.threshold
    )
    
    if args.waveform:
        visualizer.start_with_waveform()
    else:
        visualizer.start()

if __name__ == '__main__':
    main()
