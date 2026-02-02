import whisper
import numpy as np
import torch
import os

class WhisperTranscriber:
    def __init__(self, model_size='base', device=None):
        """
        Initialize Whisper transcription model
        
        :param model_size: Size of Whisper model ('tiny', 'base', 'small', 'medium', 'large')
        :param device: Compute device (None = auto-select)
        """
        # Auto-select device if not specified
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
        
        self.device = device
        
        # Load the model
        try:
            self.model = whisper.load_model(model_size, device=self.device)
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            raise
    
    def transcribe(self, audio_path, language=None, prompt=None):
        """
        Transcribe an audio file
        
        :param audio_path: Path to audio file
        :param language: Language code (optional)
        :param prompt: Initial transcription prompt (optional)
        :return: Transcription result dictionary
        """
        # Verify file exists
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Transcription options
        options = {
            'task': 'transcribe',
            'fp16': self.device != 'cpu'  # Use fp16 only on GPU/MPS
        }
        
        # Add optional parameters
        if language:
            options['language'] = language
        if prompt:
            options['initial_prompt'] = prompt
        
        try:
            result = self.model.transcribe(audio_path, **options)
            return {
                'text': result['text'].strip(),
                'language': result['language'],
                'segments': result.get('segments', []),
                'confidence': result.get('confidence', None)
            }
        except Exception as e:
            print(f"Transcription error: {e}")
            return {
                'text': '',
                'error': str(e)
            }
    
    def detect_language(self, audio_path):
        """
        Detect language of an audio file
        
        :param audio_path: Path to audio file
        :return: Detected language code and probability
        """
        try:
            result = self.model.detect_language(whisper.load_audio(audio_path))
            return {
                'language': result[0],
                'probability': result[1]
            }
        except Exception as e:
            print(f"Language detection error: {e}")
            return None

# Usage example
def main():
    transcriber = WhisperTranscriber(model_size='base')
    
    # Example transcription
    result = transcriber.transcribe('test_recording.wav')
    print("Transcription:", result['text'])
    
    # Language detection
    language_info = transcriber.detect_language('test_recording.wav')
    if language_info:
        print(f"Detected Language: {language_info['language']} "
              f"(Probability: {language_info['probability']})")

if __name__ == '__main__':
    main()