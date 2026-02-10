#!/bin/bash
# Simple run script - activates venv and starts ultra-fast mode

set -e

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found"
    echo "Run ./quick_install.sh first"
    exit 1
fi

# Activate venv
source venv/bin/activate

# Check if dependencies are installed
if ! python3 -c "import faster_whisper" 2>/dev/null; then
    echo "❌ Dependencies not installed"
    echo "Run ./quick_install.sh first"
    exit 1
fi

# Start ultra-fast mode
echo "🚀 Starting OpenClaw Ears (Ultra-Fast Mode)"
echo ""

cd "$(dirname "$0")/.." && python3 main.py --model tiny --duration 1.5 --tts "$@"
