#!/bin/bash
# Quick speak command for OpenClaw voice loop
# Usage: ./speak.sh "Hello, this is a test"

# Use /tmp/speak.txt symlink for reliable cross-user access
SPEECH_FILE="/tmp/speak.txt"

if [ -n "$1" ]; then
    echo "$*" >> "$SPEECH_FILE"
    echo "[SPEAKING] $*"
else
    echo "Usage: ./speak.sh 'text to speak'"
fi
