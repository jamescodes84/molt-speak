#!/bin/bash
# Test script for instant speech improvements

SPEECH_FILE="$HOME/.openclaw/speech_output.txt"

echo "Testing instant speech with incremental phrase delivery..."
echo ""
echo "Make sure OpenClaw Mouth is running with --local flag:"
echo "  ./start_speech_system.sh --local"
echo ""
echo "Press Enter to start test..."
read

echo "Sending phrases one at a time (should speak each immediately):"
echo ""

sleep 1
echo "First phrase: Hello, I am testing instant speech" | tee -a "$SPEECH_FILE"
echo "✓ Sent phrase 1"

sleep 2
echo "Second phrase: Each phrase should start speaking immediately" | tee -a "$SPEECH_FILE"
echo "✓ Sent phrase 2"

sleep 2
echo "Third phrase: Not waiting for the entire response to finish" | tee -a "$SPEECH_FILE"
echo "✓ Sent phrase 3"

sleep 2
echo "Fourth phrase: This is much faster than before" | tee -a "$SPEECH_FILE"
echo "✓ Sent phrase 4"

echo ""
echo "Test complete! Each phrase should have started speaking within milliseconds."
