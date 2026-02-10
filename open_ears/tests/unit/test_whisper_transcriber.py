import unittest
import os
import sys

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from openclaw_ears.transcription.whisper_transcriber import WhisperTranscriber

class TestWhisperTranscriber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use smallest model for faster testing
        cls.transcriber = WhisperTranscriber(model_size='tiny')
    
    def _create_test_audio(self, duration=3):
        """Create a test audio file"""
        import numpy as np
        from scipy.io import wavfile
        
        # Generate a test signal
        sample_rate = 16000
        t = np.linspace(0, duration, num=sample_rate*duration, endpoint=False)
        
        # Create a simple signal
        signal = np.sin(2 * np.pi * 440 * t) * (np.random.rand(len(t)) > 0.5)
        
        # Convert to 16-bit PCM
        signal = (signal * 32767).astype(np.int16)
        
        # Write to WAV
        test_wav = '/tmp/test_transcription.wav'
        wavfile.write(test_wav, sample_rate, signal)
        
        return test_wav
    
    def test_transcribe(self):
        """Test basic transcription"""
        # Create a test audio file
        test_wav = self._create_test_audio()
        
        # Transcribe
        result = self.transcriber.transcribe(test_wav)
        
        # Validate result structure
        self.assertIn('text', result)
        self.assertIn('language', result)
    
    def test_language_detection(self):
        """Test language detection"""
        # Create a test audio file
        test_wav = self._create_test_audio()
        
        # Detect language
        language_info = self.transcriber.detect_language(test_wav)
        
        # Validate language detection
        self.assertIsNotNone(language_info)
        self.assertIn('language', language_info)
        self.assertIn('probability', language_info)

if __name__ == '__main__':
    unittest.main()