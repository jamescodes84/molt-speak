#!/bin/bash
#
# Start Molt Speak Menu Bar App
#
# Provides easy control of the voice loop from the macOS menu bar
#

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║          Molt Speak - Voice Loop Menu Bar                  ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if rumps is installed
if ! python3 -c "import rumps" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  rumps library not installed${NC}"
    echo ""
    echo -e "${BLUE}Installing rumps...${NC}"

    # Check if venv exists
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi

    source venv/bin/activate
    pip install rumps
    echo ""
    echo -e "${GREEN}✅ rumps installed${NC}"
else
    # Activate venv if it exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
fi

echo ""
echo -e "${BLUE}Starting menu bar app...${NC}"
echo ""
echo -e "${GREEN}✅ Menu bar icon should appear in your status bar${NC}"
echo ""
echo -e "${BLUE}Features:${NC}"
echo "  • Start/Stop complete voice loop"
echo "  • 23 voices across 7 accents"
echo "  • Control individual systems"
echo "  • View logs in real-time"
echo "  • Quick access to configuration"
echo "  • System status monitoring"
echo ""
echo -e "${YELLOW}To quit: Use menu bar icon → Quit${NC}"
echo ""

# Run the menu bar app
python3 unified_menu_bar.py
