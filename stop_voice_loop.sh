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
echo -e "${BLUE}[1/3]${NC} Stopping OpenClaw Ears..."
stop_process "OpenClaw Ears" ~/.openclaw/ears.pid

echo ""
echo -e "${BLUE}[2/3]${NC} Stopping OpenClaw Mouth..."
stop_process "OpenClaw Mouth" ~/.openclaw/mouth.pid

echo ""
echo -e "${BLUE}[3/3]${NC} Stopping Integration Coordinator..."
stop_process "Integration Coordinator" ~/.openclaw/integration.pid

# Clean up any remaining files
echo ""
echo -e "${BLUE}Cleaning up...${NC}"

# Remove signal files
rm -f ~/.openclaw/agent_instructions.active
rm -f ~/.openclaw/agent_shutdown.signal
rm -f ~/.openclaw/ears_pause.signal
rm -f ~/.openclaw/mouth_status.txt

echo -e "  ${GREEN}✓ Signal files cleaned${NC}"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║            Voice Loop Stopped Successfully                 ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Logs preserved at:${NC}"
echo "  • ~/.openclaw/logs/integration.log"
echo "  • ~/.openclaw/logs/mouth.log"
echo "  • ~/.openclaw/logs/ears.log"
echo ""
