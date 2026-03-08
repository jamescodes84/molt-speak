#!/bin/bash
#
# Start OpenClaw Ears Only (Voice input)
#
# Use this when you only need voice INPUT (speech-to-text)
# without TTS output.
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
echo -e "${GREEN}║         OpenClaw Ears Only - Voice Input                   ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Activate unified venv
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo -e "${RED}Error: Virtual environment not found${NC}"
    echo "Please run: molt-speak update"
    exit 1
fi

echo -e "${BLUE}Voice input will type into terminal matching 'openclaw' pattern${NC}"
echo ""
echo -e "${YELLOW}Starting OpenClaw Ears...${NC}"

# Start ears
cd open_ears
nohup python3 main.py > "$LOGS_DIR/ears.log" 2>&1 &
EARS_PID=$!
echo "$EARS_PID" > "$RUNTIME_DIR/ears.pid"

sleep 3

if ps -p $EARS_PID > /dev/null; then
    echo -e "${GREEN}✓ OpenClaw Ears started (PID: $EARS_PID)${NC}"
else
    echo -e "${RED}✗ Failed to start OpenClaw Ears${NC}"
    echo "  Check log: $LOGS_DIR/ears.log"
    exit 1
fi

echo ""
echo -e "${GREEN}Ears is running!${NC}"
echo ""
echo -e "${BLUE}Setup your terminal:${NC}"
echo "  echo -n -e \"\\033]0;OpenClaw Agent\\007\""
echo ""
echo -e "${BLUE}View log:${NC}"
echo "  tail -f $LOGS_DIR/ears.log"
echo ""
echo -e "${BLUE}To stop:${NC}"
echo "  kill $EARS_PID"
echo ""
