import json
import os
from datetime import datetime, timedelta

class AudioState:
    def __init__(self, state_dir=None):
        """
        Manage audio interaction state
        
        :param state_dir: Directory to store state files (default: ~/.openclaw/voice)
        """
        if state_dir is None:
            state_dir = os.path.expanduser('~/.openclaw/voice')
        
        # Ensure state directory exists
        os.makedirs(state_dir, exist_ok=True)
        
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, 'state.json')
        self.history_file = os.path.join(state_dir, 'history.jsonl')
    
    def _read_state(self):
        """
        Read current state from JSON file
        
        :return: State dictionary
        """
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                'last_interaction': None,
                'is_listening': False,
                'recent_transcriptions': []
            }
    
    def _write_state(self, state):
        """
        Write state to JSON file
        
        :param state: State dictionary
        """
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def log_transcription(self, transcription, confidence=None):
        """
        Log a transcription to history
        
        :param transcription: Transcribed text
        :param confidence: Transcription confidence (optional)
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'text': transcription,
            'confidence': confidence
        }
        
        # Append to history file
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def is_active_conversation(self, max_idle_time_minutes=10):
        """
        Check if there's an ongoing conversation
        
        :param max_idle_time_minutes: Maximum time between interactions
        :return: Boolean indicating active conversation
        """
        state = self._read_state()
        
        if not state['last_interaction']:
            return False
        
        last_interaction = datetime.fromisoformat(state['last_interaction'])
        idle_time = datetime.now() - last_interaction
        
        return idle_time < timedelta(minutes=max_idle_time_minutes)
    
    def update_interaction(self, is_listening=False):
        """
        Update interaction state
        
        :param is_listening: Whether the system is currently listening
        """
        state = self._read_state()
        state['last_interaction'] = datetime.now().isoformat()
        state['is_listening'] = is_listening
        
        self._write_state(state)
    
    def get_conversation_context(self, num_entries=5):
        """
        Retrieve recent conversation context
        
        :param num_entries: Number of recent entries to return
        :return: List of recent transcriptions
        """
        try:
            with open(self.history_file, 'r') as f:
                # Read last n lines
                lines = f.readlines()[-num_entries:]
                return [json.loads(line) for line in lines]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

# Usage example
def main():
    audio_state = AudioState()
    
    # Log a transcription
    audio_state.log_transcription("Hello, this is a test transcription", 0.95)
    
    # Check conversation state
    print("Active conversation:", audio_state.is_active_conversation())
    
    # Update interaction
    audio_state.update_interaction(is_listening=True)
    
    # Get recent conversation context
    context = audio_state.get_conversation_context()
    print("Recent context:", context)

if __name__ == '__main__':
    main()