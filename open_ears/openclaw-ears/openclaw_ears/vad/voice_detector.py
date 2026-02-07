import webrtcvad
import numpy as np

class VoiceActivityDetector:
    def __init__(self, sample_rate=16000, frame_duration_ms=30, aggressiveness=3):
        """
        Initialize Voice Activity Detector
        
        :param sample_rate: Audio sample rate (Hz)
        :param frame_duration_ms: Frame duration for VAD analysis
        :param aggressiveness: VAD sensitivity (0-3, 3 being most aggressive)
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        
        # Validate parameters
        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError("Sample rate must be 8000, 16000, 32000, or 48000 Hz")
        
        if frame_duration_ms not in (10, 20, 30):
            raise ValueError("Frame duration must be 10, 20, or 30 ms")
    
    def is_speech(self, audio_frame):
        """
        Detect if an audio frame contains speech
        
        :param audio_frame: Raw audio data (bytes)
        :return: Boolean indicating speech presence
        """
        try:
            return self.vad.is_speech(audio_frame, self.sample_rate)
        except Exception:
            return False
    
    def detect_voice_segments(self, audio_data, min_speech_duration_ms=300):
        """
        Detect continuous voice segments in audio
        
        :param audio_data: Entire audio data as bytes
        :param min_speech_duration_ms: Minimum continuous speech duration
        :return: List of (start_ms, end_ms) voice segments
        """
        # Calculate frame size in bytes
        bytes_per_ms = self.sample_rate * 2 // 1000  # 16-bit audio
        frame_size = self.frame_duration_ms * bytes_per_ms
        
        voice_segments = []
        current_segment_start = None
        
        for i in range(0, len(audio_data), frame_size):
            frame = audio_data[i:i+frame_size]
            
            # Ensure frame is correct size
            if len(frame) < frame_size:
                break
            
            is_speech = self.is_speech(frame)
            
            if is_speech and current_segment_start is None:
                # Start of a new speech segment
                current_segment_start = i * 1000 // (self.sample_rate * 2)
            
            elif not is_speech and current_segment_start is not None:
                # End of a speech segment
                segment_end = i * 1000 // (self.sample_rate * 2)
                
                # Check if segment meets minimum duration
                if segment_end - current_segment_start >= min_speech_duration_ms:
                    voice_segments.append((current_segment_start, segment_end))
                
                current_segment_start = None
        
        # Handle case where last segment doesn't end
        if current_segment_start is not None:
            segment_end = len(audio_data) * 1000 // (self.sample_rate * 2)
            if segment_end - current_segment_start >= min_speech_duration_ms:
                voice_segments.append((current_segment_start, segment_end))
        
        return voice_segments

# Usage example
def main():
    import wave
    
    # Load a wav file
    with wave.open('test_recording.wav', 'rb') as wf:
        # Read the wav file
        audio_data = wf.readframes(wf.getnframes())
        sample_rate = wf.getframerate()
    
    vad = VoiceActivityDetector(sample_rate=sample_rate)
    voice_segments = vad.detect_voice_segments(audio_data)
    
    print("Voice Segments (ms):")
    for start, end in voice_segments:
        print(f"Speech from {start}ms to {end}ms (duration: {end-start}ms)")

if __name__ == '__main__':
    main()