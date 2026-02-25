#!/bin/bash

# Test Microphone - Visual Audio Level Monitor

cd "$(dirname "$0")"
source venv/bin/activate

echo "🎙️  Starting Audio Visualizer..."
echo ""
echo "This will show you:"
echo "  - Real-time audio levels from your microphone"
echo "  - Visual waveform of recent audio"
echo "  - Speech detection indicator"
echo ""
echo "Color coding:"
echo "  Gray   = Too quiet (below threshold)"
echo "  Yellow = Getting there"
echo "  Green  = Speech level detected!"
echo ""
echo "Press Ctrl+C to stop"
echo ""
sleep 3

python3 audio_visualizer.py --waveform --threshold 500
