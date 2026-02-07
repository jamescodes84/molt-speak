#!/usr/bin/env python3
"""
OpenClaw integration - sends voice transcriptions to active agent session
"""

import json
from pathlib import Path
from datetime import datetime

from ..config import settings


class OpenClawNotifier:
    """Send voice transcriptions to OpenClaw agent session via message queue"""

    def __init__(self, queue_dir=None):
        if queue_dir is None:
            self.queue_dir = settings.VOICE_DIR
        else:
            self.queue_dir = Path(queue_dir).expanduser()
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.queue_dir / 'agent_queue.jsonl'
    
    def notify(self, transcription):
        """
        Send transcription to OpenClaw agent via queue file
        
        The agent can monitor this file and process new entries
        
        :param transcription: Text transcription (with or without [lang] prefix)
        """
        # Parse language tag if present
        if ']' in transcription:
            lang, text = transcription.split(']', 1)
            lang = lang.strip('[')
            text = text.strip()
        else:
            lang = 'unknown'
            text = transcription.strip()
        
        if not text:
            return False
        
        # Create queue entry
        entry = {
            'timestamp': datetime.now().isoformat(),
            'language': lang,
            'text': text,
            'type': 'voice_command'
        }
        
        try:
            # Append to queue file
            with open(self.queue_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
            
            # Also write to a simple "latest" file for easy checking
            latest_file = self.queue_dir / 'latest_command.txt'
            with open(latest_file, 'w') as f:
                f.write(f"{text}\n")
            
            return True
            
        except Exception as e:
            # Fail silently - voice system shouldn't crash
            return False
    
    def is_available(self):
        """Check if queue directory is writable"""
        return self.queue_dir.exists() and self.queue_dir.is_dir()
