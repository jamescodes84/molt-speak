import unittest
import os
import sys

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from openclaw_ears.core.audio_capture import AudioCapture

class TestAudioCapture(unittest.TestCase):
    def setUp(self):
        self.capture = AudioCapture()
    
    def test_list_devices(self):
        """Test that we can list audio input devices"""
        devices = self.capture.list_devices()
        self.assertIsNotNone(devices)
        self.assertTrue(len(devices) > 0)
    
    def test_save_to_wav(self):
        """Test saving audio to a WAV file"""
        output_file = '/tmp/test_audio_capture.wav'
        
        # Remove existing file if it exists
        if os.path.exists(output_file):
            os.remove(output_file)
        
        # Record for 2 seconds
        self.capture.save_to_wav(output_file, duration_seconds=2)
        
        # Check that file was created
        self.assertTrue(os.path.exists(output_file))
        
        # Check file size (should be non-zero)
        file_size = os.path.getsize(output_file)
        self.assertGreater(file_size, 0)

if __name__ == '__main__':
    unittest.main()