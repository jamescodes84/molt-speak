#!/bin/bash
# Start OpenClaw Ears Voice Input System

echo "🚀 Starting OpenClaw Ears Voice Input System..."
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found!"
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Run the voice system with longer segments for full sentences
# --duration 3.0 means it waits 3 seconds before transcribing (captures full sentences)
python main.py --duration 3.0

# When stopped
echo ""
echo "✅ Voice system stopped"
