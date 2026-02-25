#!/usr/bin/env python3
"""
Performance Benchmark: Old vs New Implementation
Compare openai-whisper vs faster-whisper + optimizations
"""

import sys
import os
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openclaw-ears'))


def create_test_audio(duration=2.0, sample_rate=16000):
    """Create synthetic test audio"""
    # Generate white noise (simulates speech)
    samples = int(duration * sample_rate)
    audio = np.random.randn(samples).astype(np.float32)

    # Normalize
    audio = audio / np.max(np.abs(audio))
    audio = (audio * 32767).astype(np.int16)

    return audio, sample_rate


def benchmark_old_implementation():
    """Benchmark original openai-whisper implementation"""
    print("📊 Benchmarking OLD Implementation (openai-whisper)")
    print("-" * 60)

    try:
        from openclaw_ears.transcription.whisper_transcriber import WhisperTranscriber
        import scipy.io.wavfile as wavfile
        import tempfile

        # Load model
        print("Loading model...")
        start = time.time()
        transcriber = WhisperTranscriber(model_size='tiny')
        load_time = time.time() - start
        print(f"✅ Model loaded in {load_time:.2f}s")

        # Create test audio
        audio, sample_rate = create_test_audio(duration=2.0)

        # Save to file (old method requires this)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        # Benchmark file I/O + transcription
        iterations = 5
        times = []

        print(f"\nRunning {iterations} iterations...")
        for i in range(iterations):
            start = time.time()

            # Write to disk
            wavfile.write(tmp_path, sample_rate, audio)

            # Transcribe from file
            result = transcriber.transcribe(tmp_path)

            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  Iteration {i+1}: {elapsed:.2f}s")

        # Cleanup
        os.unlink(tmp_path)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n📈 Results:")
        print(f"  Average: {avg_time:.2f}s")
        print(f"  Min: {min_time:.2f}s")
        print(f"  Max: {max_time:.2f}s")
        print(f"  Realtime factor: {avg_time/2.0:.2f}x")

        return {
            'implementation': 'openai-whisper',
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time
        }

    except ImportError as e:
        print(f"⚠️  Old implementation not available: {e}")
        print("   This is expected if you haven't installed openai-whisper")
        return None


def benchmark_new_implementation():
    """Benchmark optimized faster-whisper implementation"""
    print("\n📊 Benchmarking NEW Implementation (faster-whisper + INT8)")
    print("-" * 60)

    try:
        from openclaw_ears.transcription.whisper_transcriber_optimized import WhisperTranscriberOptimized

        # Load model with INT8
        print("Loading model...")
        start = time.time()
        transcriber = WhisperTranscriberOptimized(
            model_size='tiny',
            compute_type='int8'
        )
        load_time = time.time() - start
        print(f"✅ Model loaded in {load_time:.2f}s")

        # Create test audio
        audio, sample_rate = create_test_audio(duration=2.0)

        # Benchmark in-memory transcription (no file I/O)
        iterations = 5
        times = []

        print(f"\nRunning {iterations} iterations...")
        for i in range(iterations):
            start = time.time()

            # Transcribe directly from memory (no file I/O!)
            result = transcriber.transcribe(audio, language='en')

            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  Iteration {i+1}: {elapsed:.2f}s")

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n📈 Results:")
        print(f"  Average: {avg_time:.2f}s")
        print(f"  Min: {min_time:.2f}s")
        print(f"  Max: {max_time:.2f}s")
        print(f"  Realtime factor: {avg_time/2.0:.2f}x")

        return {
            'implementation': 'faster-whisper + INT8',
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time
        }

    except ImportError as e:
        print(f"❌ New implementation not available: {e}")
        print("   Run: ./install_optimized.sh")
        return None


def benchmark_tts():
    """Benchmark TTS performance"""
    print("\n📊 Benchmarking TTS (edge-tts)")
    print("-" * 60)

    try:
        from openclaw_ears.tts.edge_tts_speaker import EdgeTTSSpeaker

        # Initialize speaker
        print("Initializing TTS...")
        speaker = EdgeTTSSpeaker(voice='us_male')
        print("✅ TTS ready")

        # Test phrases
        phrases = [
            "Hello, I am JARVIS.",
            "The quick brown fox jumps over the lazy dog.",
            "Welcome to the future of voice interaction."
        ]

        times = []

        print(f"\nGenerating {len(phrases)} TTS samples...")
        for i, phrase in enumerate(phrases, 1):
            start = time.time()
            audio_file = speaker.speak(phrase)
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  Sample {i}: {elapsed:.2f}s ({len(phrase)} chars)")

        avg_time = sum(times) / len(times)

        print(f"\n📈 Results:")
        print(f"  Average: {avg_time:.2f}s")
        print(f"  Min: {min(times):.2f}s")
        print(f"  Max: {max(times):.2f}s")

        return {
            'implementation': 'edge-tts',
            'avg_time': avg_time,
            'min_time': min(times),
            'max_time': max(times)
        }

    except ImportError as e:
        print(f"⚠️  TTS not available: {e}")
        print("   Run: pip install edge-tts")
        return None


def print_comparison(old_result, new_result, tts_result):
    """Print comparison of results"""
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE COMPARISON")
    print("=" * 60)

    if old_result and new_result:
        speedup = old_result['avg_time'] / new_result['avg_time']
        time_saved = old_result['avg_time'] - new_result['avg_time']

        print(f"\nSTT Performance:")
        print(f"  Old (openai-whisper):          {old_result['avg_time']:.2f}s")
        print(f"  New (faster-whisper + INT8):   {new_result['avg_time']:.2f}s")
        print(f"  ⚡ Speedup: {speedup:.2f}x faster")
        print(f"  ⚡ Time saved: {time_saved:.2f}s ({time_saved/old_result['avg_time']*100:.0f}%)")

    if tts_result:
        print(f"\nTTS Performance:")
        print(f"  edge-tts:                      {tts_result['avg_time']:.2f}s")

    if new_result and tts_result:
        total_pipeline = new_result['avg_time'] + 0.05 + tts_result['avg_time']
        print(f"\nComplete Pipeline (STT + Agent + TTS):")
        print(f"  STT:         {new_result['avg_time']:.2f}s")
        print(f"  Agent:       0.05s (estimated)")
        print(f"  TTS:         {tts_result['avg_time']:.2f}s")
        print(f"  ───────────────────────")
        print(f"  Total:       {total_pipeline:.2f}s")

        if old_result:
            old_total = old_result['avg_time'] + 0.05
            print(f"\n  Old pipeline (no TTS):  {old_total:.2f}s")
            print(f"  New pipeline (with TTS): {total_pipeline:.2f}s")
            if total_pipeline < old_total:
                improvement = (old_total - total_pipeline) / old_total * 100
                print(f"  ✅ Complete pipeline is faster despite adding TTS!")
                print(f"  ⚡ {improvement:.0f}% improvement")

    print("\n" + "=" * 60)


def main():
    """Run all benchmarks"""
    print("🚀 OpenClaw Ears - Performance Benchmark")
    print("=" * 60)
    print()
    print("This benchmark will compare:")
    print("  • Old: openai-whisper (if available)")
    print("  • New: faster-whisper + INT8 quantization")
    print("  • TTS: edge-tts performance")
    print()

    # Run benchmarks
    old_result = benchmark_old_implementation()
    new_result = benchmark_new_implementation()
    tts_result = benchmark_tts()

    # Print comparison
    print_comparison(old_result, new_result, tts_result)

    # Recommendations
    print("\n💡 Recommendations:")
    if new_result:
        if new_result['avg_time'] < 1.0:
            print("  ✅ Excellent! Your STT latency is under 1 second.")
        elif new_result['avg_time'] < 1.5:
            print("  ✅ Good! Your STT latency is under 1.5 seconds.")
        else:
            print("  ⚠️  STT latency is higher than expected.")
            print("     Try using a smaller model or enabling GPU acceleration.")

    if tts_result:
        if tts_result['avg_time'] < 0.7:
            print("  ✅ Excellent! Your TTS latency is under 700ms.")
        else:
            print("  ℹ️  TTS latency depends on text length and network.")

    print()
    print("🎯 Target latency for production:")
    print("  • STT: < 1.2s")
    print("  • Agent: < 0.1s")
    print("  • TTS: < 0.7s")
    print("  • Total: < 2s end-to-end")
    print()


if __name__ == '__main__':
    main()
