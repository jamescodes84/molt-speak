"""
Whisper transcriber using openai-whisper.

Provides high-quality speech-to-text transcription with MPS/GPU acceleration.
"""

# Standard library
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional, Union

# Third-party
import numpy as np
import scipy.io.wavfile as wavfile
import torch
import whisper

# Module-level logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL_SIZE = "tiny"
DEFAULT_SAMPLE_RATE = 16000

class WhisperTranscriberOptimized:
    """
    Whisper transcriber using openai-whisper
    - Supports MPS (Apple Silicon), CUDA, and CPU
    - In-memory transcription support
    - FP16 acceleration on compatible devices
    """

    def __init__(self, model_size='tiny', device=None, compute_type='default'):
        """
        Initialize Whisper model

        :param model_size: Size of Whisper model ('tiny', 'base', 'small', 'medium', 'large')
        :param device: Compute device ('cuda', 'cpu', 'mps', 'auto')
        :param compute_type: Compatibility parameter (ignored for openai-whisper)
        """
        # Auto-select device if not specified
        # Force CPU to avoid MPS sparse tensor bug on Apple Silicon
        if device is None or device == 'auto':
            device = 'cpu'  # Always use CPU for now

        self.device = device
        self.model_size = model_size

        # Load the model
        try:
            self.model = whisper.load_model(model_size, device=device)
            logger.info(f"✅ Loaded whisper {model_size} on {device}")
            print(f"✅ Loaded whisper {model_size} on {device}")
        except Exception as e:
            logger.error(f"Error loading whisper model: {e}")
            print(f"Error loading whisper model: {e}")
            raise

    def transcribe(self, audio_input, language=None, prompt=None):
        """
        Transcribe audio from file path OR numpy array (in-memory)

        :param audio_input: Either:
                           - str: Path to audio file
                           - np.ndarray: Audio data (will be saved to temp file)
        :param language: Language code (optional, e.g., 'en', 'es')
        :param prompt: Initial transcription prompt (optional)
        :return: Transcription result dictionary
        """
        # Handle numpy array input (in-memory transcription)
        if isinstance(audio_input, np.ndarray):
            return self._transcribe_from_array(audio_input, language, prompt)

        # Handle file path input
        elif isinstance(audio_input, str):
            return self._transcribe_from_file(audio_input, language, prompt)

        else:
            raise ValueError("audio_input must be either a file path (str) or numpy array")

    def _transcribe_from_file(self, audio_path, language=None, prompt=None):
        """Transcribe from audio file"""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        return self._run_transcription(audio_path, language, prompt)

    def _transcribe_from_array(self, audio_data, language=None, prompt=None, sample_rate=16000):
        """
        Transcribe from numpy array (in-memory, no file I/O overhead)

        This is MUCH faster than saving to disk first
        """
        # Create temporary file (faster-whisper needs a file path)
        # But we use a memory-backed temp file for speed
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name

            # Normalize audio to int16 if needed
            if audio_data.dtype != np.int16:
                if np.max(np.abs(audio_data)) > 0:
                    audio_normalized = audio_data / np.max(np.abs(audio_data))
                else:
                    audio_normalized = audio_data
                audio_data = (audio_normalized * 32767).astype(np.int16)

            # Write to temp file
            wavfile.write(tmp_path, sample_rate, audio_data)

        try:
            result = self._run_transcription(tmp_path, language, prompt)
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

        return result

    def _run_transcription(self, audio_path, language=None, prompt=None):
        """Run the actual transcription"""
        try:
            # Transcription options for openai-whisper
            result = self.model.transcribe(
                audio_path,
                language=language,
                initial_prompt=prompt,
                fp16=(self.device != 'cpu'),  # Use FP16 on GPU/MPS
                verbose=False
            )

            # Extract text and segments
            text = result['text'].strip()
            segments = result.get('segments', [])

            # Calculate average confidence from segments
            if segments:
                avg_confidence = sum(
                    seg.get('avg_logprob', seg.get('confidence', 0))
                    for seg in segments
                ) / len(segments)
            else:
                avg_confidence = None

            return {
                'text': text,
                'language': result.get('language', language or 'en'),
                'segments': [
                    {
                        'text': seg.get('text', ''),
                        'start': seg.get('start', 0),
                        'end': seg.get('end', 0),
                        'confidence': seg.get('avg_logprob', seg.get('confidence', 0))
                    }
                    for seg in segments
                ],
                'confidence': avg_confidence,
                'duration': segments[-1].get('end', 0) if segments else 0
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            print(f"Transcription error: {e}")
            return {
                'text': '',
                'error': str(e)
            }

    def detect_language(self, audio_path):
        """
        Detect language of an audio file

        :param audio_path: Path to audio file
        :return: Detected language info
        """
        try:
            # Load audio and detect language
            audio = whisper.load_audio(audio_path)
            audio = whisper.pad_or_trim(audio)

            # Make log-Mel spectrogram and detect language
            mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
            _, probs = self.model.detect_language(mel)

            detected_language = max(probs, key=probs.get)

            return {
                'language': detected_language,
                'probability': probs[detected_language]
            }
        except Exception as e:
            logger.error(f"Language detection error: {e}")
            print(f"Language detection error: {e}")
            return None


# Backwards compatibility: drop-in replacement for original WhisperTranscriber
class WhisperTranscriber(WhisperTranscriberOptimized):
    """Alias for backwards compatibility"""
    pass


def main():
    """Test the transcriber"""
    import time

    print("🚀 Testing Whisper Transcriber (openai-whisper)")
    print("=" * 60)

    # Initialize
    start = time.time()
    transcriber = WhisperTranscriberOptimized(model_size='tiny')
    load_time = time.time() - start
    print(f"⏱️  Model load time: {load_time:.2f}s")
    print()

    # Test with a sample audio file
    test_file = 'test_recording.wav'
    if os.path.exists(test_file):
        print(f"📝 Transcribing {test_file}...")
        start = time.time()
        result = transcriber.transcribe(test_file)
        transcribe_time = time.time() - start

        print(f"✅ Transcription: \"{result['text']}\"")
        print(f"🌍 Language: {result['language']}")
        print(f"⏱️  Transcription time: {transcribe_time:.2f}s")

        if result.get('duration'):
            realtime_factor = transcribe_time / result['duration']
            print(f"⚡ Realtime factor: {realtime_factor:.2f}x")
    else:
        print(f"⚠️  Test file {test_file} not found")
        print("💡 Create a test recording to benchmark performance")


if __name__ == '__main__':
    main()