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
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_DIR"

# Use project-local directories (NOT ~/.openclaw)
RUNTIME_DIR="$PROJECT_DIR/runtime"
LOGS_DIR="$PROJECT_DIR/logs"
mkdir -p "$RUNTIME_DIR" "$LOGS_DIR"

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

# Check if voice loop is already running
if [ -f "$RUNTIME_DIR/integration.pid" ] && [ -f "$RUNTIME_DIR/audio.pid" ]; then
    INTEGRATION_PID=$(cat "$RUNTIME_DIR/integration.pid" 2>/dev/null)
    AUDIO_PID=$(cat "$RUNTIME_DIR/audio.pid" 2>/dev/null)

    # Check if both processes are actually running
    if ps -p "$INTEGRATION_PID" > /dev/null 2>&1 && ps -p "$AUDIO_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ Voice loop is already running${NC}"
        echo ""
        echo -e "${BLUE}Running Systems:${NC}"
        echo "  • Integration Coordinator (PID: $INTEGRATION_PID)"
        echo "  • Unified Audio System    (PID: $AUDIO_PID)"
        echo ""
        echo -e "${GREEN}✓ Voice loop is active and running${NC}"
        echo ""
        echo -e "${BLUE}To stop:${NC}"
        echo "  • Run: ./stop_voice_loop.sh"
        echo "  • Or:  kill $INTEGRATION_PID $AUDIO_PID"
        echo ""
        exit 0
    fi
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

nohup python3 main.py > "$LOGS_DIR/integration.log" 2>&1 &
INTEGRATION_PID=$!
echo "      PID: $INTEGRATION_PID"
sleep 2

if ps -p $INTEGRATION_PID > /dev/null; then
    echo -e "      ${GREEN}✓ Integration Coordinator started${NC}"
else
    echo -e "      ${RED}✗ Failed to start Integration Coordinator${NC}" >&2
    echo "      Check log: $LOGS_DIR/integration.log" >&2
    # Output actual error from log
    if [ -f "$LOGS_DIR/integration.log" ]; then
        echo "" >&2
        echo "Last 10 lines of log:" >&2
        tail -10 "$LOGS_DIR/integration.log" >&2
    fi
    exit 1
fi

# 2. Start Unified Audio System (Mouth + Ears in single process)
echo ""
echo -e "${YELLOW}[2/2]${NC} Starting Unified Audio System (Mouth + Ears)..."

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start unified audio system
nohup python3 src/unified_audio.py > "$LOGS_DIR/audio.log" 2>&1 &
AUDIO_PID=$!
echo "      PID: $AUDIO_PID"
sleep 3

if ps -p $AUDIO_PID > /dev/null; then
    echo -e "      ${GREEN}✓ Unified Audio System started${NC}"
    echo "      ${BLUE}  (Mouth + Ears running in single process)${NC}"
else
    echo -e "      ${RED}✗ Failed to start Unified Audio System${NC}" >&2
    echo "      Check log: $LOGS_DIR/audio.log" >&2
    # Output actual error from log
    if [ -f "$LOGS_DIR/audio.log" ]; then
        echo "" >&2
        echo "Last 20 lines of audio log:" >&2
        tail -20 "$LOGS_DIR/audio.log" >&2
    fi
    # Also check mouth log for errors
    if [ -f "$LOGS_DIR/mouth.log" ]; then
        echo "" >&2
        echo "Last 10 lines of mouth log:" >&2
        tail -10 "$LOGS_DIR/mouth.log" >&2
    fi
    exit 1
fi

# Save PIDs for shutdown script (in project runtime directory)
echo "$INTEGRATION_PID" > "$RUNTIME_DIR/integration.pid"
echo "$AUDIO_PID" > "$RUNTIME_DIR/audio.pid"
# Keep old PID files for compatibility
echo "$AUDIO_PID" > "$RUNTIME_DIR/mouth.pid"
echo "$AUDIO_PID" > "$RUNTIME_DIR/ears.pid"

# Create speech output directory in standard location
SPEECH_OUTPUT_DIR="$HOME/openclaw-workspace/molt-speak"
mkdir -p "$SPEECH_OUTPUT_DIR"
# Clear speech output file to ensure fresh start
: > "$SPEECH_OUTPUT_DIR/speech_output.txt"
echo -e "      ${GREEN}✓ Created speech output at $SPEECH_OUTPUT_DIR/speech_output.txt${NC}"

# Create simple symlink for agent to use (no spaces in path)
# Clean up any stale symlink (ignore errors if it doesn't exist or has permission issues)
rm -f /tmp/speak.txt 2>/dev/null || true
ln -sf "$SPEECH_OUTPUT_DIR/speech_output.txt" /tmp/speak.txt 2>/dev/null || true
echo -e "      ${GREEN}✓ Created /tmp/speak.txt symlink${NC}"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║             🎉 Voice Loop Started Successfully! 🎉          ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Running Systems:${NC}"
echo "  • Integration Coordinator (PID: $INTEGRATION_PID)"
echo "  • Unified Audio System    (PID: $AUDIO_PID)"
echo "    ${BLUE}↳ OpenClaw Mouth + Ears (single process)${NC}"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo "  • Integration: tail -f $LOGS_DIR/integration.log"
echo "  • Audio:       tail -f $LOGS_DIR/audio.log"
echo ""
echo -e "${BLUE}Agent Instructions:${NC}"
echo "  • Check: cat $SCRIPT_DIR/AGENT_INSTRUCTIONS.txt"
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
echo "  • Or:  kill $INTEGRATION_PID $AUDIO_PID"
echo ""
echo -e "${GREEN}✓ Ready for voice conversations!${NC}"
echo -e "${GREEN}  Speak naturally - commands appear in your agent automatically${NC}"
echo ""
