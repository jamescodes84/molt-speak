#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="$HOME/.openspeak"
REPO_URL="https://github.com/jamescodes84/open_speak.git"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     OpenSpeak Voice Loop Installer     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Detect OS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}Error: OpenSpeak currently only supports macOS${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} macOS detected"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed${NC}"
    echo "Please install Python 3 from https://www.python.org/downloads/"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}! Homebrew not found. Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo -e "${GREEN}✓${NC} Homebrew found"
fi

# Install ffmpeg if needed
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}! Installing ffmpeg...${NC}"
    brew install ffmpeg
else
    echo -e "${GREEN}✓${NC} ffmpeg found"
fi

# Install portaudio if needed (for pyaudio)
if ! brew list portaudio &> /dev/null; then
    echo -e "${YELLOW}! Installing portaudio...${NC}"
    brew install portaudio
else
    echo -e "${GREEN}✓${NC} portaudio found"
fi

# Clone or update repository
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}! OpenSpeak directory exists. Updating...${NC}"
    cd "$INSTALL_DIR"
    git pull
else
    echo -e "${YELLOW}! Cloning OpenSpeak repository...${NC}"
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "${GREEN}✓${NC} Repository ready at $INSTALL_DIR"

# Set up Python virtual environments
echo -e "${YELLOW}! Setting up Python virtual environments...${NC}"

# Main environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt 2>/dev/null || echo "No main requirements.txt found"
deactivate

# open_mouth environment
if [ -d "open_mouth" ]; then
    cd open_mouth
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt 2>/dev/null || echo "No open_mouth requirements.txt found"
    deactivate
    cd ..
fi

# open_ears environment
if [ -d "open_ears" ]; then
    cd open_ears
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt 2>/dev/null || echo "No open_ears requirements.txt found"
    deactivate
    cd ..
fi

echo -e "${GREEN}✓${NC} Virtual environments configured"

# Create molt-speak CLI launcher
echo -e "${YELLOW}! Creating molt-speak command...${NC}"

LAUNCHER_SCRIPT="/usr/local/bin/molt-speak"

sudo tee "$LAUNCHER_SCRIPT" > /dev/null << 'EOF'
#!/bin/bash

INSTALL_DIR="$HOME/.openspeak"

case "$1" in
    start)
        echo "Starting OpenSpeak Voice Loop..."
        cd "$INSTALL_DIR"
        source venv/bin/activate
        python -m open_mouth.src.unified_audio start &
        echo "Voice loop started. Use 'molt-speak stop' to stop."
        ;;

    stop)
        echo "Stopping OpenSpeak Voice Loop..."
        pkill -f "unified_audio"
        pkill -f "open_ears"
        pkill -f "open_mouth"
        echo "Voice loop stopped."
        ;;

    menu)
        echo "Opening Voice Menu..."
        cd "$INSTALL_DIR"
        source venv/bin/activate
        python -m open_mouth.src.gui.unified_menu_bar
        ;;

    status)
        echo "Checking OpenSpeak status..."
        if pgrep -f "unified_audio" > /dev/null; then
            echo "✓ Voice loop is running"
        else
            echo "✗ Voice loop is not running"
        fi
        ;;

    logs)
        LOG_DIR="$INSTALL_DIR/logs"
        if [ ! -d "$LOG_DIR" ]; then
            echo "No logs directory found"
            exit 1
        fi

        case "$2" in
            ears)
                tail -f "$LOG_DIR/ears.log"
                ;;
            mouth)
                tail -f "$LOG_DIR/mouth.log"
                ;;
            *)
                echo "Available logs: ears, mouth"
                echo "Usage: molt-speak logs [ears|mouth]"
                ;;
        esac
        ;;

    update)
        echo "Updating OpenSpeak..."
        cd "$INSTALL_DIR"
        git pull
        source venv/bin/activate
        pip install --upgrade -r requirements.txt 2>/dev/null || true
        cd open_mouth && source venv/bin/activate && pip install --upgrade -r requirements.txt 2>/dev/null || true && deactivate && cd ..
        cd open_ears && source venv/bin/activate && pip install --upgrade -r requirements.txt 2>/dev/null || true && deactivate && cd ..
        echo "✓ OpenSpeak updated"
        ;;

    *)
        echo "OpenSpeak Voice Loop - molt-speak command"
        echo ""
        echo "Usage: molt-speak [command]"
        echo ""
        echo "Commands:"
        echo "  start    - Start the voice loop"
        echo "  stop     - Stop the voice loop"
        echo "  menu     - Open voice selection menu"
        echo "  status   - Check if voice loop is running"
        echo "  logs     - View logs (ears|mouth)"
        echo "  update   - Update OpenSpeak to latest version"
        echo ""
        ;;
esac
EOF

sudo chmod +x "$LAUNCHER_SCRIPT"

echo -e "${GREEN}✓${NC} molt-speak command installed"

# Create runtime directory
mkdir -p "$INSTALL_DIR/runtime"
mkdir -p "$INSTALL_DIR/logs"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Installation Complete! 🎉          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "OpenSpeak is installed at: ${BLUE}$INSTALL_DIR${NC}"
echo ""
echo -e "Quick Start:"
echo -e "  ${YELLOW}molt-speak start${NC}   - Start the voice loop"
echo -e "  ${YELLOW}molt-speak menu${NC}    - Open voice selection"
echo -e "  ${YELLOW}molt-speak status${NC}  - Check status"
echo -e "  ${YELLOW}molt-speak stop${NC}    - Stop the voice loop"
echo ""
echo -e "For more commands: ${YELLOW}molt-speak${NC}"
echo ""
