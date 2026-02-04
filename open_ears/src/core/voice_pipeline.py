#!/usr/bin/env python3
"""
OpenClaw Ears - Maximum Performance Voice Pipeline
Optimized for fastest possible STT → Agent → TTS at zero cost

Key optimizations:
- faster-whisper (4x faster than openai-whisper)
- In-memory transcription (no file I/O)
- INT8 quantization (2x speedup)
- Shorter segments (1.5s)
- Parallel processing
- Optional TTS response
"""

import sys
import os
import time
import threading
import queue
import numpy as np
import sounddevice as sd
from pathlib import Path
from collections import deque
from datetime import datetime

from src.services.transcription_service import WhisperTranscriberOptimized
from src.services.mouth_status_monitor import MouthStatusMonitor
from src.services.ears_status_notifier import EarsStatusNotifier
from src.core.state_manager import AudioState
from src.utils.openclaw_notifier import OpenClawNotifier
from src.core.terminal_visualizer import TerminalVisualizer
from src.config import settings


class UltraFastVoicePipeline:
    """
    Maximum performance voice transcription system
    Optimized for speed with zero extra cost
    """

    def __init__(self,
                 output_dir=None,  # Defaults to settings.VOICE_DIR
                 model_size='tiny',
                 silence_duration=1.1,  # Seconds of silence before submitting
                 speech_threshold=500,
                 sample_rate=16000,
                 enable_tts=False):
        """
        Initialize ultra-fast voice pipeline

        :param silence_duration: Seconds of silence before submitting (1.1s = fast response)
        :param enable_tts: Enable text-to-speech responses
        """
        if output_dir is None:
            self.output_dir = settings.VOICE_DIR
        else:
            self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.sample_rate = sample_rate
        self.silence_duration = silence_duration
        self.speech_threshold = speech_threshold
        self.barge_multiplier = self._get_barge_multiplier()
        self.speaking_threshold = speech_threshold * self.barge_multiplier
        self.enable_tts = enable_tts
        self.check_interval = 0.1  # Check audio every 100ms for responsiveness

        # Terminal Visualizer
        self.visualizer = TerminalVisualizer(width=60)
        self.visualizer.threshold = speech_threshold
        self.current_amplitude = 0
        self.is_speaking = False

        # Streaming state
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        self.transcription_queue = queue.Queue()

        # Silence detection state
        self.last_speech_time = None
        self.accumulated_audio = []
        self.is_recording = False

        # Transcription - OPTIMIZED with faster-whisper + INT8
        print(f"🚀 Loading optimized Whisper {model_size} model...")
        self.transcriber = WhisperTranscriberOptimized(
            model_size=model_size,
            compute_type='int8'  # 2x faster with minimal accuracy loss
        )
        self.state = AudioState(state_dir=str(self.output_dir))
        print("✅ Model loaded with INT8 optimization")
        
        # OpenClaw integration
        self.openclaw = OpenClawNotifier(queue_dir=str(self.output_dir))
        if self.openclaw.is_available():
            print("✅ OpenClaw integration enabled (queue-based notifications)")

        # OpenClaw Mouth integration - monitor speaking status for echo prevention
        self.mouth_monitor = MouthStatusMonitor()
        if self.mouth_monitor.is_available():
            print("✅ OpenClaw Mouth integration enabled (echo prevention)")

        # Ears status notifier - tell mouth when we detect speech (barge-in)
        self.ears_notifier = EarsStatusNotifier()
        print("✅ Ears status notifier enabled (barge-in support)")

        # TTS (if enabled)
        self.tts_queue = queue.Queue()
        if enable_tts:
            try:
                import edge_tts
                self.edge_tts = edge_tts
                print("✅ TTS enabled (edge-tts)")
            except ImportError:
                print("⚠️  edge-tts not installed. Install with: pip install edge-tts")
                self.enable_tts = False

        # Display
        self.current_transcription = ""
        self.transcription_count = 0
        self.last_transcription_time = 0

        # Performance metrics
        self.avg_transcription_time = 0
        self.transcription_times = deque(maxlen=10)

        # Speaking flag to prevent listening while TTS is active
        self.is_speaking_tts = False

        self.running = False
        self.segment_count = 0

    def _get_barge_multiplier(self) -> int:
        """Get barge-in threshold multiplier from ConfigManager."""
        try:
            import sys
            config_manager_path = settings.PROJECT_DIR / "src" / "config"
            if str(config_manager_path) not in sys.path:
                sys.path.insert(0, str(config_manager_path))
            from config_manager import ConfigManager
            config = ConfigManager()
            return config.get_barge_multiplier()
        except Exception:
            return 5  # Default fallback

    def _audio_callback(self, indata, frames, time_info, status):
        """Capture and analyze audio"""
        if status:
            print(f"\n⚠️  {status}", file=sys.stderr)

        amplitude = np.sqrt(np.mean(indata**2)) * 10000
        self.current_amplitude = amplitude
        self.is_speaking = amplitude > self.speech_threshold

        # Update visualizer
        self.visualizer.update(amplitude, self.is_speaking)

        # Add to buffer
        with self.buffer_lock:
            self.audio_buffer.append(indata.copy())

    def _display_loop(self):
        """Update display using terminal visualizer"""
        while self.running:
            time.sleep(0.05)

            # Move cursor up and display the visualizer
            self.visualizer.clear_lines(4)
            print(self.visualizer.render_full())
            sys.stdout.flush()

    def _capture_loop(self):
        """Capture audio with silence-based voice activity detection"""
        while self.running:
            time.sleep(self.check_interval)  # Check every 100ms for responsiveness

            # Use much higher threshold when agent is speaking to prevent TTS bleed
            agent_speaking = self.is_speaking_tts or self.mouth_monitor.is_agent_speaking()
            current_threshold = self.speaking_threshold if agent_speaking else self.speech_threshold

            # Get buffered audio
            with self.buffer_lock:
                if len(self.audio_buffer) == 0:
                    if agent_speaking:
                        self.ears_notifier.notify_paused()
                    continue

                audio_data = np.concatenate(self.audio_buffer)
                self.audio_buffer = []

            # Check amplitude against current threshold
            max_amp = np.max(np.abs(audio_data)) * 10000
            has_speech = max_amp >= current_threshold

            if has_speech:
                # Speech detected - update last speech time and accumulate audio
                self.last_speech_time = time.time()
                self.accumulated_audio.append(audio_data)
                # Notify mouth that user is speaking (triggers barge-in)
                self.ears_notifier.notify_speech_detected(max_amp)
                if not self.is_recording:
                    self.is_recording = True
            else:
                # Silence detected - notify we're just listening
                self.ears_notifier.notify_listening()
                if self.is_recording and self.last_speech_time is not None:
                    # Check if we've had enough silence
                    silence_time = time.time() - self.last_speech_time
                    if silence_time >= self.silence_duration:
                        # Submit accumulated audio for transcription
                        if len(self.accumulated_audio) > 0:
                            full_audio = np.concatenate(self.accumulated_audio)
                            self.segment_count += 1
                            self.transcription_queue.put((self.segment_count, full_audio, time.time()))

                        # Reset state
                        self.accumulated_audio = []
                        self.is_recording = False
                        self.last_speech_time = None

    def _transcription_worker(self):
        """
        Process transcription queue
        OPTIMIZED: No file I/O, transcribe directly from memory
        """
        while self.running:
            try:
                segment_num, audio_data, capture_time = self.transcription_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # Normalize audio
            if np.max(np.abs(audio_data)) > 0:
                audio_normalized = audio_data / np.max(np.abs(audio_data))
            else:
                audio_normalized = audio_data

            audio_16bit = (audio_normalized * 32767).astype(np.int16)

            # OPTIMIZATION: Transcribe directly from memory (no file I/O!)
            start_time = time.time()

            try:
                # This is the key optimization - pass numpy array directly
                result = self.transcriber.transcribe(
                    audio_16bit,
                    language='en'  # Pre-specify language for speed
                )
                text = result['text'].strip()

                transcription_time = time.time() - start_time
                total_latency = time.time() - capture_time

                self.transcription_times.append(transcription_time)
                self.avg_transcription_time = sum(self.transcription_times) / len(self.transcription_times)

                if text:
                    self.current_transcription = text
                    self.transcription_count += 1
                    self.last_transcription_time = time.time()

                    # Update visualizer with transcription
                    self.visualizer.set_transcription(text)

                    # Save to state
                    self.state.log_transcription(text)
                    self.state.update_interaction()

                    # Type directly into OpenClaw TUI and press Enter
                    self._send_to_openclaw_tui(text)

                    # Optional: Queue for TTS response
                    if self.enable_tts:
                        response = self._generate_agent_response(text)
                        if response:
                            self.tts_queue.put(response)

                    # Log performance
                    print(f"\n⚡ Transcribed in {transcription_time:.2f}s (total latency: {total_latency:.2f}s)")

            except Exception as e:
                print(f"\n⚠️  Transcription error: {e}", file=sys.stderr)

    def _send_to_openclaw_tui(self, text):
        """
        Send transcribed text directly to OpenClaw TUI
        Intelligently finds the correct Terminal window/tab and types text + Enter

        On macOS: Uses AppleScript to find and activate specific Terminal window
        Fallback: Uses pyautogui (types into focused window)
        """
        from ..config import settings

        # Escape quotes and backslashes for AppleScript string
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')

        # Get window targeting configuration
        window_pattern = settings.TARGET_WINDOW_PATTERN
        activate_window = settings.ACTIVATE_TARGET_WINDOW

        # Sophisticated AppleScript - finds specific Terminal window by title and types into it
        applescript = f'''
tell application "Terminal"
    set foundWindow to missing value
    set searchPattern to "{window_pattern}"

    -- Search all windows for matching pattern (case-insensitive)
    if searchPattern is not "" then
        repeat with w in windows
            set windowName to name of w
            -- Check if window name contains the pattern
            if windowName contains searchPattern then
                set foundWindow to w
                exit repeat
            end if
        end repeat
    end if

    -- If no match, use frontmost window
    if foundWindow is missing value and (count of windows) > 0 then
        set foundWindow to front window
    end if

    -- If we have a target window, send text to it in background
    if foundWindow is not missing value then
        -- Get the selected tab of the target window
        set targetTab to selected tab of foundWindow

        -- Send the text to that tab (do script works for interactive programs)
        -- This sends input to the running program without activating Terminal
        do script "{escaped_text}" in targetTab

        return "Typed into Terminal window (background)"
    else
        error "No Terminal windows available"
    end if
end tell
'''

        try:
            import subprocess

            # Run AppleScript
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                success_msg = result.stdout.strip()
                print(f"\n✅ {success_msg}: {text}")
                return
            else:
                error_msg = result.stderr.strip()
                if error_msg:
                    print(f"\n⚠️  AppleScript failed: {error_msg}")
                # Fall through to pyautogui fallback

        except subprocess.TimeoutExpired:
            print(f"\n⚠️  AppleScript timed out")
        except Exception as e:
            print(f"\n⚠️  AppleScript error: {e}")

        # Fallback: Use pyautogui (types into focused window)
        try:
            import pyautogui

            time.sleep(0.05)
            pyautogui.write(text, interval=0)
            time.sleep(0.05)
            pyautogui.press('enter')

            print(f"\n✅ Typed into focused window (fallback): {text}")

        except ImportError:
            print(f"\n⚠️  Neither AppleScript nor pyautogui worked. Install pyautogui: pip install pyautogui")
        except Exception as e:
            print(f"\n⚠️  Error typing to TUI: {e}")

    def _generate_agent_response(self, transcription):
        """
        Generate agent response to transcription
        Placeholder - integrate with your OpenClaw agent here
        """
        # TODO: Integrate with OpenClaw agent
        # For now, just echo back with confirmation
        return f"Received: {transcription}"

    def _tts_worker(self):
        """Process TTS queue (if enabled)"""
        if not self.enable_tts:
            return

        import asyncio

        async def speak(text):
            """Speak text using edge-tts"""
            try:
                # Set speaking flag to prevent echo
                self.is_speaking_tts = True

                output_file = self.output_dir / f"tts_{int(time.time())}.mp3"
                communicate = self.edge_tts.Communicate(text, "en-US-ChristopherNeural")
                await communicate.save(str(output_file))

                # Play audio (requires pygame or similar)
                # For now, just save the file
                print(f"\n🔊 TTS saved to: {output_file}")

                # TODO: Add actual playback here
                # When playback completes, clear the flag
                # For now, wait estimated duration
                await asyncio.sleep(len(text) * 0.1)  # Rough estimate

            except Exception as e:
                print(f"\n⚠️  TTS error: {e}")
            finally:
                # Always clear speaking flag when done
                self.is_speaking_tts = False

        while self.running:
            try:
                text = self.tts_queue.get(timeout=0.5)
                asyncio.run(speak(text))
            except queue.Empty:
                continue

    def start(self):
        """Start ultra-fast voice pipeline"""
        print("\033[2J\033[H")  # Clear screen
        print("🚀 OpenClaw Ears - Maximum Performance Pipeline")
        print("=" * 70)
        print("⚡ Optimizations:")
        print("   • faster-whisper (4x faster)")
        print("   • INT8 quantization (2x faster)")
        print("   • In-memory transcription (no file I/O)")
        print(f"   • Silence detection ({self.silence_duration}s of silence)")
        if self.enable_tts:
            print("   • TTS enabled (edge-tts)")
        print()
        print(f"📡 Sample Rate: {self.sample_rate} Hz")
        print(f"🎯 Speech Threshold: {self.speech_threshold}")
        print(f"💾 Output: {self.output_dir}")
        print()
        print("Press Ctrl+C to stop")
        print("=" * 70)
        print("\n" * 4)  # 4 lines for terminal visualizer

        self.running = True

        # Start OpenClaw Mouth monitor (if available)
        if self.mouth_monitor.is_available():
            self.mouth_monitor.start()

        # Start display thread
        display_thread = threading.Thread(target=self._display_loop, daemon=True)
        display_thread.start()

        # Start capture thread
        capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        capture_thread.start()

        # Start transcription worker (parallel processing)
        transcription_thread = threading.Thread(target=self._transcription_worker, daemon=True)
        transcription_thread.start()

        # Start TTS worker (if enabled)
        if self.enable_tts:
            tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
            tts_thread.start()

        try:
            with sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=int(self.sample_rate * 0.05),
                callback=self._audio_callback
            ):
                while self.running:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\n⏹️  Shutting down OpenClaw Ears...")
            self.running = False
            # Stop Mouth monitor
            if self.mouth_monitor:
                self.mouth_monitor.stop()
            time.sleep(0.5)
            print("✅ Shutdown complete")


def main():
    """Run ultra-fast voice pipeline"""
    import argparse

    parser = argparse.ArgumentParser(description='OpenClaw Ears Ultra Fast Voice Pipeline')
    parser.add_argument('--model', default='tiny', help='Whisper model size (tiny recommended)')
    parser.add_argument('--threshold', type=int, default=500, help='Speech threshold')
    parser.add_argument('--silence', type=float, default=1.1, help='Silence duration before submitting (1.1s = fast response)')
    parser.add_argument('--tts', action='store_true', help='Enable TTS responses')

    args = parser.parse_args()

    pipeline = UltraFastVoicePipeline(
        model_size=args.model,
        speech_threshold=args.threshold,
        silence_duration=args.silence,
        enable_tts=args.tts
    )

    pipeline.start()


if __name__ == '__main__':
    main()