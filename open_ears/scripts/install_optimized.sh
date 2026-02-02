#!/bin/bash
# Install Optimized Dependencies for OpenClaw Ears
# Installs faster-whisper (4x faster) and edge-tts (free TTS)

set -e

echo "🚀 Installing Optimized OpenClaw Ears Dependencies"
echo "="
echo ""
echo "This will install:"
echo "  ✅ faster-whisper (4x faster than openai-whisper)"
echo "  ✅ edge-tts (free Microsoft TTS)"
echo "  ✅ All required audio libraries"
echo ""

# Check if in virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Consider activating venv first: source venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install optimized requirements
echo "📦 Installing optimized requirements..."
pip install -r requirements_optimized.txt

# Install package in development mode
echo "📦 Installing openclaw-ears package..."
cd openclaw-ears
pip install -e .
cd ..

echo ""
echo "✅ Installation complete!"
echo ""
echo "📊 Performance Improvements:"
echo "  • 4x faster transcription (faster-whisper vs openai-whisper)"
echo "  • 2x faster inference (INT8 quantization)"
echo "  • Zero file I/O overhead (in-memory transcription)"
echo "  • Free TTS capability (edge-tts)"
echo ""
echo "🚀 To start ultra-fast mode:"
echo "   ./start_ultra_fast.sh"
echo ""
echo "🎯 To test the complete pipeline:"
echo "   python3 demo_complete_pipeline.py"
echo ""
