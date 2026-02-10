import unittest
import os
import sys
import time
import json
from datetime import datetime, timedelta

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from openclaw_ears.state.audio_state import AudioState

class TestAudioState(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory for state files
        self.test_state_dir = '/tmp/openclaw_ears_test_state'
        os.makedirs(self.test_state_dir, exist_ok=True)
        
        # Create AudioState with test directory
        self.audio_state = AudioState(state_dir=self.test_state_dir)
    
    def tearDown(self):
        # Clean up test state files
        import shutil
        shutil.rmtree(self.test_state_dir, ignore_errors=True)
    
    def test_log_transcription(self):
        """Test logging a transcription"""
        test_transcription = "This is a test transcription"
        
        # Log transcription
        self.audio_state.log_transcription(test_transcription, 0.95)
        
        # Check history file
        history_path = os.path.join(self.test_state_dir, 'history.jsonl')
        self.assertTrue(os.path.exists(history_path))
        
        # Read last log entry
        with open(history_path, 'r') as f:
            last_line = f.readlines()[-1].strip()
            log_entry = json.loads(last_line)
        
        self.assertEqual(log_entry['text'], test_transcription)
        self.assertEqual(log_entry['confidence'], 0.95)
    
    def test_is_active_conversation(self):
        """Test conversation activity detection"""
        # Initially, no conversation
        self.assertFalse(self.audio_state.is_active_conversation())
        
        # Update interaction
        self.audio_state.update_interaction(is_listening=True)
        
        # Should now be an active conversation
        self.assertTrue(self.audio_state.is_active_conversation())
    
    def test_get_conversation_context(self):
        """Test retrieving conversation context"""
        # Log multiple transcriptions
        transcriptions = [
            "First message",
            "Second message",
            "Third message"
        ]
        
        for transcription in transcriptions:
            self.audio_state.log_transcription(transcription)
        
        # Retrieve context
        context = self.audio_state.get_conversation_context(num_entries=2)
        
        # Check context
        self.assertEqual(len(context), 2)
        self.assertEqual(context[-1]['text'], "Third message")
        self.assertEqual(context[-2]['text'], "Second message")

if __name__ == '__main__':
    unittest.main()