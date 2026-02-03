#!/bin/bash
# Quick speak command for OpenClaw voice loop
# Usage: ./speak.sh "Hello, this is a test"

SPEECH_FILE="$HOME/.molt-speak/runtime/speech_output.txt"

# Ensure directory exists
mkdir -p "$(dirname "$SPEECH_FILE")"

if [ -n "$1" ]; then
    echo "$*" >> "$SPEECH_FILE"
    echo "[SPEAKING] $*"
else
    echo "Usage: ./speak.sh 'text to speak'"
fi
