#!/bin/bash
#
# Start Molt Speak Menu Bar App
#
# Provides easy control of the voice loop from the macOS menu bar
#

# NO set -e — we handle errors explicitly so failures are always visible

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_DIR"

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

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║          Molt Speak - Voice Loop Menu Bar                  ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Activate venv first
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || error_exit "Failed to activate virtual environment. Try: rm -rf venv && moltspeak start"
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        error_exit "Failed to create virtual environment. Is python3 installed?"
    fi
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt 2>&1
    if [ $? -ne 0 ]; then
        error_exit "Failed to install dependencies. Check requirements.txt and your internet connection."
    fi
fi

# Check if rumps is installed in the venv
if ! python3 -c "import rumps" 2>/dev/null; then
    echo -e "${YELLOW}rumps library not installed${NC}"
    echo ""
    echo -e "${BLUE}Installing rumps...${NC}"
    pip install rumps pyobjc-framework-Cocoa
    if [ $? -ne 0 ]; then
        error_exit "Failed to install rumps. Check your internet connection."
    fi
    echo ""
    echo -e "${GREEN}rumps installed${NC}"
fi

echo ""
echo -e "${BLUE}Starting menu bar app...${NC}"
echo ""
echo -e "${GREEN}Menu bar icon should appear in your status bar${NC}"
echo ""
echo -e "${BLUE}Features:${NC}"
echo "  Start/Stop complete voice loop"
echo "  23 voices across 7 accents"
echo "  Control individual systems"
echo "  View logs in real-time"
echo "  Quick access to configuration"
echo "  System status monitoring"
echo ""
echo -e "${YELLOW}To quit: Use menu bar icon > Quit${NC}"
echo ""

# Run the menu bar app
python3 unified_menu_bar.py
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    error_exit "Menu bar app exited with code $EXIT_CODE"
fi
