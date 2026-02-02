#!/usr/bin/env python3
"""
OpenClaw Ears Plugin
Continuous voice input for OpenClaw agents
"""

import sys
import os
import time
import threading
from pathlib import Path

# Add openclaw-ears to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openclaw-ears'))

from openclaw_ears.core.audio_capture import AudioCapture
from openclaw_ears.transcription.whisper_transcriber import WhisperTranscriber
from openclaw_ears.state.audio_state import AudioState

class OpenClawEarsPlugin:
    """Continuous voice input plugin for OpenClaw"""
    
    def __init__(self, 
                 output_dir='~/.openclaw/voice',
                 model_size='tiny',
                 recording_duration=5,
                 silence_threshold=500):
        """
        Initialize the OpenClaw Ears plugin
        
        :param output_dir: Directory to store voice recordings
        :param model_size: Whisper model size (tiny, base, small, medium, large)
        :param recording_duration: Duration of each recording chunk (seconds)
        :param silence_threshold: Amplitude threshold for silence detection
        """
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.recording_duration = recording_duration
        self.silence_threshold = silence_threshold
        
        # Initialize components
        print("🎙️  Initializing OpenClaw Ears...")
        self.capture = AudioCapture()
        self.transcriber = WhisperTranscriber(model_size=model_size)
        self.state = AudioState()
        
        # Thread control
        self.is_listening = False
        self.listener_thread = None
        
        print("✅ OpenClaw Ears initialized")
    
    def start_listening(self):
        """Start continuous listening in a background thread"""
        if self.is_listening:
            print("⚠️  Already listening")
            return
        
        self.is_listening = True
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()
        print("🎧 Started continuous listening")
    
    def stop_listening(self):
        """Stop continuous listening"""
        self.is_listening = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2)
        print("🛑 Stopped listening")
    
    def _listen_loop(self):
        """Main listening loop (runs in background thread)"""
        segment_count = 0
        
        while self.is_listening:
            segment_count += 1
            audio_file = self.output_dir / f"segment_{segment_count:04d}.wav"
            
            # Record audio segment
            self.capture.save_to_wav(str(audio_file), duration_seconds=self.recording_duration)
            
            # Analyze for silence
            analysis = self.capture.analyze_audio(str(audio_file))
            
            if analysis['max_amplitude'] < self.silence_threshold:
                # Silent segment - delete and continue
                audio_file.unlink()
                continue
            
            # Transcribe
            result = self.transcriber.transcribe(str(audio_file))
            transcribed_text = result['text'].strip()
            
            if transcribed_text:
                # Log transcription
                self.state.log_transcription(transcribed_text)
                self.state.update_interaction()
                
                # Output the transcription (this would be sent to OpenClaw)
                self._handle_transcription(transcribed_text, result['language'])
            
            # Clean up old recordings (keep only last 10)
            self._cleanup_old_recordings(keep_count=10)
    
    def _handle_transcription(self, text, language):
        """
        Handle a transcription - this is where you'd integrate with OpenClaw
        
        :param text: Transcribed text
        :param language: Detected language
        """
        print(f"\n🗣️  [{language}] {text}")
        
        # TODO: Send to OpenClaw via:
        # - Write to state file that OpenClaw monitors
        # - Call OpenClaw API/webhook
        # - Use IPC mechanism
        # - Publish to message queue
        
        # For now, write to a file that can be monitored
        transcription_file = self.output_dir / 'latest_transcription.txt'
        with open(transcription_file, 'w') as f:
            f.write(f"[{language}] {text}\n")
    
    def _cleanup_old_recordings(self, keep_count=10):
        """
        Remove old audio recordings, keeping only the most recent ones
        
        :param keep_count: Number of recordings to keep
        """
        recordings = sorted(self.output_dir.glob('segment_*.wav'))
        if len(recordings) > keep_count:
            for old_recording in recordings[:-keep_count]:
                old_recording.unlink()

def main():
    """Demo/test of the OpenClaw Ears plugin"""
    print("OpenClaw Ears - Continuous Voice Input Plugin")
    print("=" * 60)
    
    # Initialize plugin
    plugin = OpenClawEarsPlugin(
        output_dir='~/.openclaw/voice',
        model_size='tiny',
        recording_duration=5,
        silence_threshold=500
    )
    
    # Start listening
    plugin.start_listening()
    
    # Run for demo period (or until interrupted)
    try:
        print("\n🎤 Listening for voice input...")
        print("   (Press Ctrl+C to stop)\n")
        
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping...")
        plugin.stop_listening()
        print("✅ Shutdown complete")

if __name__ == '__main__':
    main()
