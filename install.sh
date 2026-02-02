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

# Set up Python virtual environment
echo -e "${YELLOW}! Setting up Python virtual environment...${NC}"

# Main environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip

# Install dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${YELLOW}Warning: No requirements.txt found${NC}"
fi

# Install rumps for menu bar (might not be in requirements.txt)
pip install rumps 2>/dev/null || true

deactivate

echo -e "${GREEN}✓${NC} Virtual environment configured"

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

        # Start using the project's startup script
        if [ -f "start_voice_loop.sh" ]; then
            ./start_voice_loop.sh
        else
            # Fallback: start manually
            source venv/bin/activate
            nohup python main.py > logs/integration.log 2>&1 &
            nohup python src/unified_audio.py > logs/audio.log 2>&1 &
            echo "Voice loop started. Use 'molt-speak stop' to stop."
        fi
        ;;

    stop)
        echo "Stopping OpenSpeak Voice Loop..."
        cd "$INSTALL_DIR"

        # Use the project's stop script if available
        if [ -f "stop_voice_loop.sh" ]; then
            ./stop_voice_loop.sh
        else
            # Fallback: kill processes
            pkill -f "unified_audio"
            pkill -f "main.py"
            echo "Voice loop stopped."
        fi
        ;;

    menu)
        echo "Opening Voice Menu..."
        cd "$INSTALL_DIR"

        # Use the project's menu script if available
        if [ -f "start_menu_bar.sh" ]; then
            ./start_menu_bar.sh
        else
            # Fallback: run directly
            source venv/bin/activate
            python3 unified_menu_bar.py
        fi
        ;;

    status)
        echo "Checking OpenSpeak status..."
        if pgrep -f "unified_audio" > /dev/null; then
            echo "✓ Voice loop is running"
            if pgrep -f "main.py" > /dev/null; then
                echo "✓ Integration coordinator is running"
            fi
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
            audio)
                tail -f "$LOG_DIR/audio.log"
                ;;
            integration)
                tail -f "$LOG_DIR/integration.log"
                ;;
            *)
                echo "Available logs: audio, integration"
                echo "Usage: molt-speak logs [audio|integration]"
                ls -1 "$LOG_DIR"/*.log 2>/dev/null | xargs -n1 basename
                ;;
        esac
        ;;

    update)
        echo "Updating OpenSpeak..."
        cd "$INSTALL_DIR"
        git pull
        source venv/bin/activate
        pip install --upgrade -r requirements.txt 2>/dev/null || true
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
        echo "  logs     - View logs (audio|integration)"
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
