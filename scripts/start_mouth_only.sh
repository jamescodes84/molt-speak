#!/bin/bash
#
# Start OpenClaw Mouth Only (TTS output)
#
# Use this when you only need voice OUTPUT (text-to-speech)
# without voice input.
#

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_DIR"

# Use project-local directories
RUNTIME_DIR="$PROJECT_DIR/runtime"
LOGS_DIR="$PROJECT_DIR/logs"
mkdir -p "$RUNTIME_DIR" "$LOGS_DIR"

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         OpenClaw Mouth Only - TTS Output                   ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Activate venv
if [ -d "open_mouth/venv" ]; then
    source open_mouth/venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Parse arguments
USE_LOCAL=""
if [ "$1" == "--local" ]; then
    USE_LOCAL="--local"
    echo -e "${BLUE}Using LOCAL TTS (macOS 'say') for instant playback${NC}"
else
    echo -e "${BLUE}Using CLOUD TTS (Edge-TTS) for high-quality voices${NC}"
fi

echo ""
echo -e "${YELLOW}Starting OpenClaw Mouth...${NC}"

# Start mouth
cd open_mouth
nohup python main.py $USE_LOCAL > "$LOGS_DIR/mouth.log" 2>&1 &
MOUTH_PID=$!
echo "$MOUTH_PID" > "$RUNTIME_DIR/mouth.pid"

sleep 2

if ps -p $MOUTH_PID > /dev/null; then
    echo -e "${GREEN}✓ OpenClaw Mouth started (PID: $MOUTH_PID)${NC}"
else
    echo -e "${RED}✗ Failed to start OpenClaw Mouth${NC}"
    echo "  Check log: $LOGS_DIR/mouth.log"
    exit 1
fi

echo ""
echo -e "${GREEN}Mouth is running!${NC}"
echo ""
echo -e "${BLUE}To speak, write text to:${NC}"
echo "  echo 'Hello world' >> $RUNTIME_DIR/speech_output.txt"
echo ""
echo -e "${BLUE}View log:${NC}"
echo "  tail -f $LOGS_DIR/mouth.log"
echo ""
echo -e "${BLUE}To stop:${NC}"
echo "  kill $MOUTH_PID"
echo ""
