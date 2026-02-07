#!/bin/bash
# Combined launcher for OpenClaw Mouth + Menu Bar App

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   OpenClaw Mouth with Menu Bar GUI${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

# Parse arguments for voice
VOICE_ARG=""
for arg in "$@"; do
    if [[ $arg == --voice=* ]]; then
        VOICE_ARG="--voice ${arg#*=}"
    fi
done

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Start OpenClaw Mouth in background
echo -e "${YELLOW}Starting OpenClaw Mouth system...${NC}"
python main.py --enable-control --local $VOICE_ARG > /tmp/openclaw_mouth.log 2>&1 &
MOUTH_PID=$!

echo -e "${GREEN}✓ OpenClaw Mouth started (PID: $MOUTH_PID)${NC}"

# Wait for control socket to be ready
echo -e "${YELLOW}Waiting for control server...${NC}"
SOCKET_PATH="$HOME/.openclaw/mouth_control.sock"
MAX_WAIT=10
WAITED=0

while [ ! -S "$SOCKET_PATH" ] && [ $WAITED -lt $MAX_WAIT ]; do
    sleep 1
    WAITED=$((WAITED + 1))
    echo -n "."
done
echo ""

if [ ! -S "$SOCKET_PATH" ]; then
    echo -e "${RED}✗ Control server failed to start${NC}"
    echo -e "${YELLOW}Check logs: tail -f /tmp/openclaw_mouth.log${NC}"
    kill $MOUTH_PID 2>/dev/null || true
    exit 1
fi

echo -e "${GREEN}✓ Control server ready${NC}"
echo ""

# Launch menu bar app (foreground)
echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}Launching Menu Bar App...${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""
echo -e "The 🎙️ icon should appear in your menu bar."
echo -e "Click it to change voices!"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop both services${NC}"
echo ""

# Trap to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $MOUTH_PID 2>/dev/null || true
    wait $MOUTH_PID 2>/dev/null || true
    echo -e "${GREEN}✓ Stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Launch menu bar app
python scripts/launch_menu_bar.py

# If menu bar app exits, cleanup
cleanup
