#!/bin/bash
#
# Molt Speak ElevenLabs API Key Setup
# Shorthand: molt-speak elapi
#

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_DIR"

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the configuration script
python3 scripts/configure_elevenlabs.py
