#!/bin/bash
#
# Stop Complete OpenClaw Voice Loop
#
# Gracefully stops all three systems in reverse order:
# 1. OpenClaw Ears (voice input)
# 2. OpenClaw Mouth (voice output)
# 3. Integration Coordinator (echo prevention)
#

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║                                                            ║${NC}"
echo -e "${YELLOW}║        OpenClaw Voice Loop - Graceful Shutdown             ║${NC}"
echo -e "${YELLOW}║                                                            ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to stop a process gracefully
stop_process() {
    local name=$1
    local pid_file=$2

    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")

        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${BLUE}Stopping $name (PID: $PID)...${NC}"
            kill -TERM $PID 2>/dev/null

            # Wait for graceful shutdown (max 5 seconds)
            local waited=0
            while ps -p $PID > /dev/null 2>&1 && [ $waited -lt 5 ]; do
                sleep 1
                waited=$((waited + 1))
            done

            # Force kill if still running
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "  ${YELLOW}Force stopping...${NC}"
                kill -9 $PID 2>/dev/null
            fi

            echo -e "  ${GREEN}✓ $name stopped${NC}"
        else
            echo -e "${YELLOW}$name not running (PID: $PID)${NC}"
        fi

        rm -f "$pid_file"
    else
        echo -e "${YELLOW}$name: No PID file found${NC}"
    fi
}

# Stop in reverse order
echo -e "${BLUE}[1/2]${NC} Stopping Unified Audio System..."
stop_process "Unified Audio System" ~/.openclaw/audio.pid
# Also remove old PID files for compatibility
rm -f ~/.openclaw/mouth.pid
rm -f ~/.openclaw/ears.pid

echo ""
echo -e "${BLUE}[2/2]${NC} Stopping Integration Coordinator..."
stop_process "Integration Coordinator" ~/.openclaw/integration.pid

# Kill any lingering voice-related Python processes
echo ""
echo -e "${BLUE}[3/3]${NC} Checking for lingering processes..."

# Find and kill any Python processes in open_ears or open_mouth directories
LINGERING_PIDS=$(lsof -t +D "$(pwd)/open_ears" 2>/dev/null)
if [ ! -z "$LINGERING_PIDS" ]; then
    echo -e "  ${YELLOW}Found lingering open_ears processes, stopping...${NC}"
    echo "$LINGERING_PIDS" | xargs kill -TERM 2>/dev/null
    sleep 1
    echo "$LINGERING_PIDS" | xargs kill -9 2>/dev/null
fi

LINGERING_PIDS=$(lsof -t +D "$(pwd)/open_mouth" 2>/dev/null)
if [ ! -z "$LINGERING_PIDS" ]; then
    echo -e "  ${YELLOW}Found lingering open_mouth processes, stopping...${NC}"
    echo "$LINGERING_PIDS" | xargs kill -TERM 2>/dev/null
    sleep 1
    echo "$LINGERING_PIDS" | xargs kill -9 2>/dev/null
fi

# Kill voice-responder if running
VOICE_RESP=$(pgrep -f "voice-responder" 2>/dev/null)
if [ ! -z "$VOICE_RESP" ]; then
    echo -e "  ${YELLOW}Found voice-responder process, stopping...${NC}"
    kill -TERM $VOICE_RESP 2>/dev/null
    sleep 1
    kill -9 $VOICE_RESP 2>/dev/null
fi

# Final sweep: kill any remaining main.py processes in this project
PROJECT_DIR="$(pwd)"
for pid in $(pgrep -f "main.py" 2>/dev/null); do
    # Check if process is in our project directory
    if lsof -p $pid 2>/dev/null | grep -q "$PROJECT_DIR"; then
        echo -e "  ${YELLOW}Found orphaned main.py process ($pid), stopping...${NC}"
        kill -9 $pid 2>/dev/null
    fi
done

echo -e "  ${GREEN}✓ All processes verified stopped${NC}"

# Clean up any remaining files
echo ""
echo -e "${BLUE}Cleaning up...${NC}"

# Remove signal files
rm -f ~/.openclaw/agent_instructions.active
rm -f ~/.openclaw/agent_shutdown.signal
rm -f ~/.openclaw/ears_pause.signal
rm -f ~/.openclaw/mouth_status.txt

# Clear speech output queue to prevent old messages on restart
: > ~/.openclaw/speech_output.txt

echo -e "  ${GREEN}✓ Signal files cleaned${NC}"
echo -e "  ${GREEN}✓ Speech queue cleared${NC}"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║            Voice Loop Stopped Successfully                 ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Logs preserved at:${NC}"
echo "  • ~/.openclaw/logs/integration.log"
echo "  • ~/.openclaw/logs/audio.log (Mouth + Ears combined)"
echo ""
