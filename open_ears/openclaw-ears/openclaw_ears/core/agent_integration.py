import os
from datetime import datetime

from ..core.audio_capture import AudioCapture
from ..vad.voice_detector import VoiceActivityDetector
from ..transcription.whisper_transcriber import WhisperTranscriber
from ..state.audio_state import AudioState

class OpenClawEars:
    def __init__(self, sample_rate=16000, device_index=None):
        """
        Initialize OpenClaw voice input system
        
        :param sample_rate: Audio sampling rate
        :param device_index: Specific input device (None = default)
        """
        self.audio_capture = AudioCapture(
            device_index=device_index, 
            sample_rate=sample_rate
        )
        self.vad = VoiceActivityDetector(sample_rate=sample_rate)
        self.transcriber = WhisperTranscriber()
        self.state = AudioState()
    
    def list_input_devices(self):
        """
        List available audio input devices
        
        :return: List of input devices
        """
        return self.audio_capture.list_devices()
    
    def detect_speech(self, audio_path, min_duration_ms=300):
        """
        Detect speech segments in an audio file
        
        :param audio_path: Path to audio file
        :param min_duration_ms: Minimum speech segment duration
        :return: List of speech segments
        """
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        return self.vad.detect_voice_segments(audio_data, min_duration_ms)
    
    def transcribe_audio(self, audio_path, language=None):
        """
        Transcribe audio file
        
        :param audio_path: Path to audio file
        :param language: Language code (optional)
        :return: Transcription result
        """
        result = self.transcriber.transcribe(audio_path, language)
        
        # Log transcription
        self.state.log_transcription(
            result['text'], 
            result.get('confidence')
        )
        
        return result
    
    def continuous_listening(self, 
                             output_dir='/tmp/openclaw_ears', 
                             max_silence_duration=2.0,
                             min_speech_duration=1.0):
        """
        Start continuous listening mode
        
        :param output_dir: Directory to save audio segments
        :param max_silence_duration: Max silence before stopping recording
        :param min_speech_duration: Minimum speech segment to transcribe
        """
        # Ensure output directory exists
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        def on_speech_detected(audio_segment):
            """
            Callback for when speech is detected
            
            :param audio_segment: Detected speech audio data
            """
            # Save audio segment
            segment_path = os.path.join(
                output_dir, 
                f'speech_segment_{datetime.now().isoformat()}.wav'
            )
            
            # Transcribe and process
            transcription = self.transcribe_audio(segment_path)
            
            # You would typically route this to your agent's input here
            print(f"Transcribed: {transcription['text']}")
        
        # TODO: Implement continuous listening logic
        # This is a placeholder and would require more complex 
        # audio streaming and real-time processing
        raise NotImplementedError("Continuous listening not yet implemented")

# Usage example
def main():
    ears = OpenClawEars()
    
    # List input devices
    print("Available Input Devices:")
    for device in ears.list_input_devices():
        print(f"Device {device['index']}: {device['name']}")
    
    # Example: Transcribe a test recording
    try:
        result = ears.transcribe_audio('test_recording.wav')
        print("Transcription:", result['text'])
    except FileNotFoundError:
        print("No test recording found. Please record an audio file first.")

if __name__ == '__main__':
    main()