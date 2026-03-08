#!/bin/bash
#
# Start Complete OpenClaw Voice Loop
#
# Starts systems in the correct order:
# 1. Integration Coordinator (echo prevention)
# 2. Unified Audio System (Mouth + Ears)
#

# NO set -e — we handle errors explicitly so failures are always visible

# Parse arguments
DEBUG_FLAG=""
if [[ "$1" == "--debug" ]]; then
    export DEBUG_MODE=true
    DEBUG_FLAG="--debug"
fi

# Colors — disabled when captured by another process (no terminal)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    BLUE='\033[0;34m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m'
else
    GREEN=''
    BLUE=''
    YELLOW=''
    RED=''
    NC=''
fi

error_exit() {
    echo "" >&2
    echo "ERROR: $1" >&2
    echo "" >&2
    exit 1
}

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

if [[ -n "$DEBUG_FLAG" ]]; then
    echo -e "${YELLOW}Debug mode enabled — inline tags will appear in agent messages${NC}"
    echo ""
fi

# Check if required directories exist
if [ ! -d "open_ears" ]; then
    error_exit "open_ears directory not found"
fi

if [ ! -d "open_mouth" ]; then
    error_exit "open_mouth directory not found"
fi

if [ ! -f "main.py" ]; then
    error_exit "Integration main.py not found"
fi

# Check if voice loop is already running
if [ -f "$RUNTIME_DIR/integration.pid" ] && [ -f "$RUNTIME_DIR/audio.pid" ]; then
    INTEGRATION_PID=$(cat "$RUNTIME_DIR/integration.pid" 2>/dev/null)
    AUDIO_PID=$(cat "$RUNTIME_DIR/audio.pid" 2>/dev/null)

    # Check if both processes are actually running
    if ps -p "$INTEGRATION_PID" > /dev/null 2>&1 && ps -p "$AUDIO_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}Voice loop is already running${NC}"
        echo ""
        echo -e "${BLUE}Running Systems:${NC}"
        echo "  Integration Coordinator (PID: $INTEGRATION_PID)"
        echo "  Unified Audio System    (PID: $AUDIO_PID)"
        echo ""
        echo -e "${GREEN}Voice loop is active and running${NC}"
        echo ""
        echo -e "${BLUE}To stop:${NC}"
        echo "  Run: ./stop_voice_loop.sh"
        echo "  Or:  kill $INTEGRATION_PID $AUDIO_PID"
        echo ""
        exit 0
    fi
fi

# ── Environment setup ─────────────────────────────────────────────────────
echo -e "${BLUE}Setting up environment...${NC}"

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        error_exit "Failed to create virtual environment. Is python3 installed?"
    fi
    source venv/bin/activate
    echo "  Installing dependencies..."
    pip install -r requirements.txt 2>&1
    if [ $? -ne 0 ]; then
        error_exit "Failed to install dependencies. Check requirements.txt and your internet connection."
    fi
else
    source venv/bin/activate 2>/dev/null || error_exit "Failed to activate virtual environment. Try: rm -rf venv && moltspeak start"
fi

# ── Pre-flight: catch critical issues BEFORE launching anything ──
if [ -f "$PROJECT_DIR/src/diagnostics/preflight.py" ]; then
    PREFLIGHT_OUTPUT=$(python3 -m src.diagnostics.preflight --critical-only --project-root "$PROJECT_DIR" 2>&1)
    PREFLIGHT_EXIT=$?
    if [ $PREFLIGHT_EXIT -ne 0 ]; then
        echo ""
        echo -e "${RED}$PREFLIGHT_OUTPUT${NC}"
        echo ""
        echo -e "${RED}Cannot start — fix the issue above, then try again.${NC}"
        echo -e "Run ${YELLOW}moltspeak diagnose${NC} for a full diagnostic report."
        exit 1
    fi
fi

# ── Import smoke test: catch missing modules NOW, not in background ──
# Check exit code only — warnings (e.g. urllib3 NotOpenSSLWarning) go to stderr
# and would cause a false failure if we checked output content
echo "  Checking imports..."
IMPORT_OUTPUT=$(python3 -c "from src.config import settings; from src.core.coordinator import VoiceLoopCoordinator" 2>&1)
if [ $? -ne 0 ]; then
    echo "" >&2
    echo -e "${RED}Import check failed:${NC}" >&2
    echo "$IMPORT_OUTPUT" >&2
    error_exit "Python imports failed. Try: rm -rf venv && bash install.sh"
fi

IMPORT_OUTPUT=$(python3 -c "import src.unified_audio" 2>&1)
if [ $? -ne 0 ]; then
    echo "" >&2
    echo -e "${RED}Import check failed:${NC}" >&2
    echo "$IMPORT_OUTPUT" >&2
    error_exit "Unified audio imports failed. Reinstall: rm -rf venv && bash install.sh"
fi

echo -e "  ${GREEN}Environment ready${NC}"
echo ""

# ── Launch processes ───────────────────────────────────────────────────────
echo -e "${BLUE}Starting systems in background...${NC}"
echo ""

# 1. Start Integration Coordinator
echo -e "${YELLOW}[1/2]${NC} Starting Integration Coordinator..."

nohup python3 main.py > "$LOGS_DIR/integration.log" 2>&1 &
INTEGRATION_PID=$!
echo "      PID: $INTEGRATION_PID"
sleep 2

if ps -p $INTEGRATION_PID > /dev/null 2>&1; then
    echo -e "      ${GREEN}Integration Coordinator started${NC}"
else
    echo -e "      ${RED}Failed to start Integration Coordinator${NC}" >&2
    if [ -f "$LOGS_DIR/integration.log" ]; then
        echo "" >&2
        echo "Log output:" >&2
        tail -15 "$LOGS_DIR/integration.log" >&2
    fi
    error_exit "Integration Coordinator crashed on startup. See log above."
fi

# 2. Start Unified Audio System (Mouth + Ears in single process)
echo ""
echo -e "${YELLOW}[2/2]${NC} Starting Unified Audio System (Mouth + Ears)..."

nohup python3 src/unified_audio.py $DEBUG_FLAG > "$LOGS_DIR/audio.log" 2>&1 &
AUDIO_PID=$!
echo "      PID: $AUDIO_PID"
sleep 3

if ps -p $AUDIO_PID > /dev/null 2>&1; then
    echo -e "      ${GREEN}Unified Audio System started${NC}"
    echo "      ${BLUE}  (Mouth + Ears running in single process)${NC}"
else
    echo -e "      ${RED}Failed to start Unified Audio System${NC}" >&2
    if [ -f "$LOGS_DIR/audio.log" ]; then
        echo "" >&2
        echo "Audio log:" >&2
        tail -20 "$LOGS_DIR/audio.log" >&2
    fi
    if [ -f "$LOGS_DIR/mouth.log" ]; then
        echo "" >&2
        echo "Mouth log:" >&2
        tail -10 "$LOGS_DIR/mouth.log" >&2
    fi
    error_exit "Unified Audio System crashed on startup. See logs above."
fi

# Save PIDs for shutdown script (in project runtime directory)
echo "$INTEGRATION_PID" > "$RUNTIME_DIR/integration.pid"
echo "$AUDIO_PID" > "$RUNTIME_DIR/audio.pid"
# Keep old PID files for compatibility
echo "$AUDIO_PID" > "$RUNTIME_DIR/mouth.pid"
echo "$AUDIO_PID" > "$RUNTIME_DIR/ears.pid"

# Create speech output file in project runtime directory
SPEECH_OUTPUT_DIR="$RUNTIME_DIR"
touch "$SPEECH_OUTPUT_DIR/speech_output.txt"
chmod 666 "$SPEECH_OUTPUT_DIR/speech_output.txt" 2>/dev/null || true

# Create simple symlink for agent to use (no spaces in path)
rm -f /tmp/speak.txt 2>/dev/null || sudo rm -f /tmp/speak.txt 2>/dev/null || true
ln -sf "$RUNTIME_DIR/speech_output.txt" /tmp/speak.txt 2>/dev/null || true

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║              Voice Loop Started Successfully!              ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Running Systems:${NC}"
echo "  Integration Coordinator (PID: $INTEGRATION_PID)"
echo "  Unified Audio System    (PID: $AUDIO_PID)"
echo "    ${BLUE}OpenClaw Mouth + Ears (single process)${NC}"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo "  Integration: tail -f $LOGS_DIR/integration.log"
echo "  Audio:       tail -f $LOGS_DIR/audio.log"
echo ""
echo -e "${BLUE}Agent Instructions:${NC}"
echo "  Check: cat $SCRIPT_DIR/AGENT_INSTRUCTIONS.txt"
echo ""
echo -e "${GREEN}Intelligent Window Targeting:${NC}"
echo "  OpenClaw Ears automatically finds your terminal"
echo "  Types into \"OpenClaw Agent\" window in background"
echo "  No need to focus the window before speaking!"
echo ""
echo -e "${BLUE}Setup (if not done already):${NC}"
echo "  Paste in your agent's terminal:"
echo -e "    ${YELLOW}echo -n -e \"\\\\033]0;OpenClaw Agent\\\\007\"${NC}"
echo "  Or use menu bar: Setup > Copy Echo Command"
echo ""
echo -e "${BLUE}To stop:${NC}"
echo "  Run: ./stop_voice_loop.sh"
echo "  Or:  kill $INTEGRATION_PID $AUDIO_PID"
echo ""
echo -e "${GREEN}Ready for voice conversations!${NC}"
echo -e "${GREEN}  Speak naturally - commands appear in your agent automatically${NC}"
echo ""
