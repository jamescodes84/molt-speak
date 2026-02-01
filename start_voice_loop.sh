#!/bin/bash
#
# Start Complete OpenClaw Voice Loop
#
# Starts all three systems in the correct order:
# 1. Integration Coordinator (echo prevention)
# 2. OpenClaw Mouth (voice output)
# 3. OpenClaw Ears (voice input)
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║        OpenClaw Voice Loop - Complete System Startup       ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if required directories exist
if [ ! -d "open_ears" ]; then
    echo -e "${RED}✗ Error: open_ears directory not found${NC}"
    exit 1
fi

if [ ! -d "open_mouth" ]; then
    echo -e "${RED}✗ Error: open_mouth directory not found${NC}"
    exit 1
fi

if [ ! -f "main.py" ]; then
    echo -e "${RED}✗ Error: Integration main.py not found${NC}"
    exit 1
fi

echo -e "${BLUE}Starting systems in background...${NC}"
echo ""

# Function to check if a process is running
check_process() {
    local logfile=$1
    local max_wait=5
    local waited=0

    while [ $waited -lt $max_wait ]; do
        if [ -f "$logfile" ] && grep -q "started\|running" "$logfile" 2>/dev/null; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

# Create logs directory
mkdir -p ~/.openclaw/logs

# 1. Start Integration Coordinator
echo -e "${YELLOW}[1/3]${NC} Starting Integration Coordinator..."
if [ ! -d "venv" ]; then
    echo "      Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
fi

nohup python main.py > ~/.openclaw/logs/integration.log 2>&1 &
INTEGRATION_PID=$!
echo "      PID: $INTEGRATION_PID"
sleep 2

if ps -p $INTEGRATION_PID > /dev/null; then
    echo -e "      ${GREEN}✓ Integration Coordinator started${NC}"
else
    echo -e "      ${RED}✗ Failed to start Integration Coordinator${NC}"
    echo "      Check log: ~/.openclaw/logs/integration.log"
    exit 1
fi

# 2. Start OpenClaw Mouth
echo ""
echo -e "${YELLOW}[2/3]${NC} Starting OpenClaw Mouth (voice output)..."
cd open_mouth

if [ ! -d "venv" ]; then
    echo "      Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
fi

nohup python main.py > ~/.openclaw/logs/mouth.log 2>&1 &
MOUTH_PID=$!
echo "      PID: $MOUTH_PID"
cd "$SCRIPT_DIR"
sleep 2

if ps -p $MOUTH_PID > /dev/null; then
    echo -e "      ${GREEN}✓ OpenClaw Mouth started${NC}"
else
    echo -e "      ${RED}✗ Failed to start OpenClaw Mouth${NC}"
    echo "      Check log: ~/.openclaw/logs/mouth.log"
    exit 1
fi

# 3. Start OpenClaw Ears
echo ""
echo -e "${YELLOW}[3/3]${NC} Starting OpenClaw Ears (voice input)..."
cd open_ears

if [ ! -d "venv" ]; then
    echo "      Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
fi

nohup python main.py > ~/.openclaw/logs/ears.log 2>&1 &
EARS_PID=$!
echo "      PID: $EARS_PID"
cd "$SCRIPT_DIR"
sleep 2

if ps -p $EARS_PID > /dev/null; then
    echo -e "      ${GREEN}✓ OpenClaw Ears started${NC}"
else
    echo -e "      ${RED}✗ Failed to start OpenClaw Ears${NC}"
    echo "      Check log: ~/.openclaw/logs/ears.log"
    exit 1
fi

# Save PIDs for shutdown script
echo "$INTEGRATION_PID" > ~/.openclaw/integration.pid
echo "$MOUTH_PID" > ~/.openclaw/mouth.pid
echo "$EARS_PID" > ~/.openclaw/ears.pid

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║             🎉 Voice Loop Started Successfully! 🎉          ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Running Systems:${NC}"
echo "  • Integration Coordinator (PID: $INTEGRATION_PID)"
echo "  • OpenClaw Mouth          (PID: $MOUTH_PID)"
echo "  • OpenClaw Ears           (PID: $EARS_PID)"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo "  • Integration: tail -f ~/.openclaw/logs/integration.log"
echo "  • Mouth:       tail -f ~/.openclaw/logs/mouth.log"
echo "  • Ears:        tail -f ~/.openclaw/logs/ears.log"
echo ""
echo -e "${BLUE}Agent Instructions:${NC}"
echo "  • Check: cat ~/.openclaw/agent_instructions.active"
echo ""
echo -e "${GREEN}🎯 Intelligent Window Targeting:${NC}"
echo "  • OpenClaw Ears automatically finds your terminal"
echo "  • Types into \"OpenClaw Agent\" window in background"
echo "  • No need to focus the window before speaking!"
echo ""
echo -e "${BLUE}💡 Setup (if not done already):${NC}"
echo "  • Paste in your agent's terminal:"
echo -e "    ${YELLOW}echo -n -e \"\\\\033]0;OpenClaw Agent\\\\007\"${NC}"
echo "  • Or use menu bar: 📝 Setup → Copy Echo Command"
echo ""
echo -e "${BLUE}To stop:${NC}"
echo "  • Run: ./stop_voice_loop.sh"
echo "  • Or:  kill $INTEGRATION_PID $MOUTH_PID $EARS_PID"
echo ""
echo -e "${GREEN}✓ Ready for voice conversations!${NC}"
echo -e "${GREEN}  Speak naturally - commands appear in your agent automatically${NC}"
echo ""
