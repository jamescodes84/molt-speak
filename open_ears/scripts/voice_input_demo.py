#!/usr/bin/env python3
"""
OpenClaw Ears - Voice Input Demo
Captures audio, transcribes with Whisper, and demonstrates the complete pipeline
"""

import sys
import os

# Add openclaw-ears to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openclaw-ears'))

from openclaw_ears.core.audio_capture import AudioCapture
from openclaw_ears.transcription.whisper_transcriber import WhisperTranscriber
from openclaw_ears.vad.voice_detector import VoiceActivityDetector
from openclaw_ears.state.audio_state import AudioState
import sounddevice as sd

def main():
    print("🎙️  OpenClaw Ears - Voice Input Demo")
    print("=" * 60)
    
    # Initialize components
    print("\n1️⃣  Initializing audio capture...")
    capture = AudioCapture()
    
    # List available devices
    print("\n📡 Available Input Devices:")
    devices = capture.list_devices()
    for device in devices:
        print(f"   Device {device['index']}: {device['name']}")
    
    # Initialize Whisper (using tiny model for speed)
    print("\n2️⃣  Loading Whisper transcription model...")
    transcriber = WhisperTranscriber(model_size='tiny')
    print("   ✅ Whisper model loaded")
    
    # Initialize state management
    print("\n3️⃣  Initializing state management...")
    state = AudioState()
    
    # Record audio
    print("\n🔴 Recording 5 seconds of audio...")
    print("   (Speak now!)")
    
    audio_file = '/tmp/openclaw_ears_demo.wav'
    capture.save_to_wav(audio_file, duration_seconds=5)
    
    print(f"   ✅ Audio saved to {audio_file}")
    
    # Analyze audio
    analysis = capture.analyze_audio(audio_file)
    print(f"\n📊 Audio Analysis:")
    print(f"   Sample Rate: {analysis['sample_rate']} Hz")
    print(f"   Duration: {analysis['duration']:.2f} seconds")
    print(f"   Max Amplitude: {analysis['max_amplitude']}")
    
    # Transcribe
    print("\n4️⃣  Transcribing audio with Whisper...")
    result = transcriber.transcribe(audio_file)
    
    print(f"\n📝 Transcription Result:")
    print(f"   Text: \"{result['text']}\"")
    print(f"   Language: {result['language']}")
    
    # Log to state
    state.log_transcription(result['text'])
    state.update_interaction()
    
    print("\n✅ Demo complete!")
    print(f"\n💡 Next Steps:")
    print(f"   - Integrate with OpenClaw message system")
    print(f"   - Add continuous listening mode")
    print(f"   - Implement VAD for speech detection")
    print(f"   - Create OpenClaw plugin/extension")

if __name__ == '__main__':
    main()
