"""
Whisper transcriber using faster-whisper (CTranslate2 backend).

Provides high-quality speech-to-text with INT8 quantization and
direct numpy array transcription (no temp file I/O).
"""

# Standard library
import logging
import os
from typing import Any, Dict, Optional, Union

# Third-party
import numpy as np
from faster_whisper import WhisperModel

# Module-level logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL_SIZE = "small"
DEFAULT_SAMPLE_RATE = 16000


class WhisperTranscriberOptimized:
    """
    Whisper transcriber using faster-whisper (CTranslate2).
    - INT8 quantization for ~2x speedup on CPU
    - Direct numpy array transcription (no temp files)
    - Greedy decoding (beam_size=1) for fast short utterances
    - Built-in Silero VAD filter trims silence before transcription
    """

    def __init__(self, model_size='base', device=None, compute_type='int8'):
        """
        Initialize faster-whisper model.

        :param model_size: Model size ('tiny', 'base', 'small', 'medium', 'large-v3')
        :param device: Compute device ('cpu' only on macOS — no MPS/Metal support in CTranslate2)
        :param compute_type: Quantization type ('int8', 'float32')
        """
        if device is None or device == 'auto':
            device = 'cpu'

        self.device = device
        self.model_size = model_size

        # Load the model
        try:
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                cpu_threads=4,
            )
            logger.info(f"Loaded faster-whisper {model_size} on {device} (compute_type={compute_type})")
            print(f"Loaded faster-whisper {model_size} on {device} (compute_type={compute_type})")

            # Warmup: transcribe 1 second of silence to pre-allocate CTranslate2 buffers
            # This eliminates the first-call penalty (~500ms)
            warmup_audio = np.zeros(DEFAULT_SAMPLE_RATE, dtype=np.float32)
            segments, _ = self.model.transcribe(warmup_audio, language='en')
            list(segments)  # Materialize generator to trigger actual computation
            logger.info("Model warmup complete")

        except Exception as e:
            logger.error(f"Error loading faster-whisper model: {e}")
            print(f"Error loading faster-whisper model: {e}")
            raise

    def transcribe(self, audio_input, language=None, prompt=None):
        """
        Transcribe audio from file path OR numpy array.

        :param audio_input: Either:
                           - str: Path to audio file
                           - np.ndarray: Audio data (float32, 16kHz, mono)
        :param language: Language code (optional, e.g., 'en')
        :param prompt: Initial transcription prompt (optional)
        :return: Transcription result dictionary
        """
        if isinstance(audio_input, np.ndarray):
            return self._transcribe_from_array(audio_input, language, prompt)
        elif isinstance(audio_input, str):
            return self._run_transcription(audio_input, language, prompt)
        else:
            raise ValueError("audio_input must be either a file path (str) or numpy array")

    def _transcribe_from_array(self, audio_data, language=None, prompt=None):
        """
        Transcribe from numpy array — direct, no temp file.
        faster-whisper accepts float32 numpy arrays natively.
        """
        # Ensure float32
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Normalize to [-1.0, 1.0] if needed
        max_val = np.max(np.abs(audio_data))
        if max_val > 1.0:
            audio_data = audio_data / max_val

        # Flatten if multi-dimensional (e.g., stereo → mono)
        if audio_data.ndim > 1:
            audio_data = audio_data.flatten()

        return self._run_transcription(audio_data, language, prompt)

    def _run_transcription(self, audio_input, language=None, prompt=None):
        """
        Run transcription on audio input (file path or numpy array).

        Returns dict with identical keys to the old openai-whisper implementation
        so voice_pipeline.py needs zero changes.
        """
        try:
            segments_gen, info = self.model.transcribe(
                audio_input,
                language=language,
                initial_prompt=prompt,
                beam_size=3,            # Beam search — better accuracy for ~50-100ms cost
                temperature=0,
                condition_on_previous_text=False,  # Prevent hallucination cascading
                vad_filter=True,        # Silero VAD trims silence before transcription
                vad_parameters={"min_silence_duration_ms": 300},
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
            )

            # Materialize the generator (transcription runs lazily)
            segment_list = list(segments_gen)

            # Build text from segments
            text = " ".join(seg.text.strip() for seg in segment_list).strip()

            # Compute average quality metrics from segments
            avg_confidence = None
            avg_no_speech_prob = None
            avg_compression_ratio = None

            if segment_list:
                avg_confidence = sum(
                    seg.avg_logprob for seg in segment_list
                ) / len(segment_list)
                avg_no_speech_prob = sum(
                    seg.no_speech_prob for seg in segment_list
                ) / len(segment_list)
                avg_compression_ratio = sum(
                    seg.compression_ratio for seg in segment_list
                ) / len(segment_list)

            return {
                'text': text,
                'language': info.language or language or 'en',
                'segments': [
                    {
                        'text': seg.text,
                        'start': seg.start,
                        'end': seg.end,
                        'confidence': seg.avg_logprob,
                    }
                    for seg in segment_list
                ],
                'confidence': avg_confidence,
                'no_speech_prob': avg_no_speech_prob,
                'compression_ratio': avg_compression_ratio,
                'duration': segment_list[-1].end if segment_list else 0,
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            print(f"Transcription error: {e}")
            return {
                'text': '',
                'error': str(e),
            }


# Backwards compatibility alias
class WhisperTranscriber(WhisperTranscriberOptimized):
    """Alias for backwards compatibility."""
    pass


def main():
    """Test the transcriber."""
    import time

    print("Testing faster-whisper Transcriber")
    print("=" * 60)

    # Initialize
    start = time.time()
    transcriber = WhisperTranscriberOptimized(model_size='base')
    load_time = time.time() - start
    print(f"Model load time: {load_time:.2f}s")
    print()

    # Test with a sample audio file
    test_file = 'test_recording.wav'
    if os.path.exists(test_file):
        print(f"Transcribing {test_file}...")
        start = time.time()
        result = transcriber.transcribe(test_file)
        transcribe_time = time.time() - start

        print(f"Transcription: \"{result['text']}\"")
        print(f"Language: {result['language']}")
        print(f"Transcription time: {transcribe_time:.2f}s")

        if result.get('duration'):
            realtime_factor = transcribe_time / result['duration']
            print(f"Realtime factor: {realtime_factor:.2f}x")
    else:
        print(f"Test file {test_file} not found")
        print("Create a test recording to benchmark performance")


if __name__ == '__main__':
    main()
