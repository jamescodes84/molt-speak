import unittest
import os
import sys
import wave

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from openclaw_ears.vad.voice_detector import VoiceActivityDetector

class TestVoiceDetector(unittest.TestCase):
    def setUp(self):
        # Create a test WAV file with some audio
        self.test_wav = '/tmp/test_voice_detection.wav'
        self._create_test_wav()
        
    def _create_test_wav(self):
        """Create a simple WAV file for testing"""
        import numpy as np
        
        # Generate a test signal
        sample_rate = 16000
        duration = 3  # 3 seconds
        t = np.linspace(0, duration, num=sample_rate*duration, endpoint=False)
        
        # Create a signal with some speech-like characteristics
        signal = np.sin(2 * np.pi * 440 * t) * (np.random.rand(len(t)) > 0.5)
        
        # Convert to 16-bit PCM
        signal = (signal * 32767).astype(np.int16)
        
        # Write to WAV
        from scipy.io import wavfile
        wavfile.write(self.test_wav, sample_rate, signal)
    
    def test_is_speech(self):
        """Test basic speech detection"""
        vad = VoiceActivityDetector(sample_rate=16000)
        
        # Read the WAV file
        with wave.open(self.test_wav, 'rb') as wf:
            # Read frames
            audio_data = wf.readframes(wf.getnframes())
            frame_size = 16000 * 2 // 1000 * 30  # 30ms frame
            
            # Check first few frames
            for i in range(0, len(audio_data), frame_size):
                frame = audio_data[i:i+frame_size]
                if len(frame) < frame_size:
                    break
                
                speech_detected = vad.is_speech(frame)
                # At least some frames should be detected as speech
                self.assertIsInstance(speech_detected, bool)
    
    def test_detect_voice_segments(self):
        """Test detecting voice segments"""
        vad = VoiceActivityDetector(sample_rate=16000)
        
        # Read the WAV file
        with wave.open(self.test_wav, 'rb') as wf:
            # Read frames
            audio_data = wf.readframes(wf.getnframes())
            
            # Detect voice segments
            voice_segments = vad.detect_voice_segments(audio_data)
            
            # We expect some voice segments
            self.assertIsInstance(voice_segments, list)
            self.assertGreater(len(voice_segments), 0)
            
            # Check segment format
            for start, end in voice_segments:
                self.assertIsInstance(start, int)
                self.assertIsInstance(end, int)
                self.assertGreater(end, start)

if __name__ == '__main__':
    unittest.main()