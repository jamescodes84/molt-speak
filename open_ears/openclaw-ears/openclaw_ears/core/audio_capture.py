import pyaudio
import numpy as np
import wave
import threading
import queue

class AudioCapture:
    def __init__(self, device_index=None, sample_rate=16000, channels=1, chunk_size=1024):
        """
        Initialize audio capture system
        
        :param device_index: Specific audio input device (None = default)
        :param sample_rate: Audio sampling rate (Hz)
        :param channels: Number of audio channels
        :param chunk_size: Number of frames per buffer
        """
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        
        self.pyaudio = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.audio_queue = queue.Queue()
        
    def list_devices(self):
        """List all available audio input devices"""
        devices = []
        for i in range(self.pyaudio.get_device_count()):
            dev = self.pyaudio.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': dev['name'],
                    'max_input_channels': dev['maxInputChannels']
                })
        return devices
    
    def start_recording(self):
        """Start continuous audio recording"""
        if self.is_recording:
            return
        
        self.is_recording = True
        self.stream = self.pyaudio.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )
        
    def stop_recording(self):
        """Stop audio recording"""
        if self.stream:
            self.is_recording = False
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        Callback for handling audio input stream
        
        :return: (data, continuation flag)
        """
        if self.is_recording:
            self.audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)
    
    def get_audio_chunk(self, timeout=None):
        """
        Retrieve an audio chunk from the queue
        
        :param timeout: Maximum time to wait for audio
        :return: Audio chunk or None
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def save_to_wav(self, filename, duration_seconds=5):
        """
        Save recorded audio to WAV file
        
        :param filename: Output file path
        :param duration_seconds: Recording duration
        """
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.pyaudio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(self.sample_rate)
        
        self.start_recording()
        
        for _ in range(int(self.sample_rate / self.chunk_size * duration_seconds)):
            data = self.get_audio_chunk()
            if data:
                wf.writeframes(data)
        
        self.stop_recording()
        wf.close()
    
    def analyze_audio(self, filename):
        """
        Basic audio file analysis
        
        :param filename: Input WAV file
        :return: Audio analysis dictionary
        """
        import scipy.io.wavfile as wavfile
        
        sample_rate, audio_data = wavfile.read(filename)
        
        return {
            'sample_rate': sample_rate,
            'duration': len(audio_data) / sample_rate,
            'channels': audio_data.ndim,
            'max_amplitude': np.max(np.abs(audio_data))
        }

def main():
    capture = AudioCapture()
    print("Available input devices:")
    for device in capture.list_devices():
        print(f"Device {device['index']}: {device['name']}")
    
    # Example: save 5 seconds of audio from default device
    output_file = '/tmp/openclaw_test_recording.wav'
    capture.save_to_wav(output_file)
    print(f"Recorded audio saved to {output_file}")

if __name__ == '__main__':
    main()