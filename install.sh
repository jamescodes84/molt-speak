#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="$HOME/.molt-speak"
REPO_URL="https://github.com/jamescodes84/molt-speak.git"

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
    echo -e "${YELLOW}! Molt-Speak directory exists. Updating...${NC}"
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout main
    git pull origin main
else
    echo -e "${YELLOW}! Cloning Molt-Speak repository...${NC}"
    git clone -b main "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "${GREEN}✓${NC} Repository ready at $INSTALL_DIR"

# Set up Python virtual environment
echo -e "${YELLOW}! Setting up Python virtual environment...${NC}"

# Deactivate any existing venv first
deactivate 2>/dev/null || true

# Main environment - use absolute paths
MAIN_VENV="$INSTALL_DIR/venv"
if [ ! -d "$MAIN_VENV" ]; then
    python3 -m venv "$MAIN_VENV"
fi
source "$MAIN_VENV/bin/activate"
pip install --upgrade pip

# Install dependencies
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    pip install -r "$INSTALL_DIR/requirements.txt"
else
    echo -e "${YELLOW}Warning: No requirements.txt found${NC}"
fi

# Install rumps for menu bar (might not be in requirements.txt)
pip install rumps 2>/dev/null || true

deactivate

echo -e "${GREEN}✓${NC} Virtual environment configured"

# Set up open_mouth and open_ears virtual environments
echo -e "${YELLOW}! Setting up open_mouth and open_ears environments...${NC}"

for dir in open_mouth open_ears; do
    DIR_PATH="$INSTALL_DIR/$dir"
    VENV_PATH="$DIR_PATH/venv"

    if [ -d "$DIR_PATH" ]; then
        echo -e "${BLUE}  Setting up $dir...${NC}"

        # Remove existing venv to ensure clean install
        if [ -d "$VENV_PATH" ]; then
            echo "    Removing old virtual environment..."
            rm -rf "$VENV_PATH"
        fi

        echo "    Creating virtual environment..."
        python3 -m venv "$VENV_PATH"

        if [ -f "$DIR_PATH/requirements.txt" ]; then
            source "$VENV_PATH/bin/activate"
            echo "    Upgrading pip..."
            pip install --upgrade pip > /dev/null 2>&1

            if [ "$dir" = "open_ears" ]; then
                echo -e "    ${YELLOW}Installing dependencies (PyTorch + Whisper - 2-5 min)...${NC}"
            else
                echo "    Installing dependencies..."
            fi

            pip install -r "$DIR_PATH/requirements.txt" 2>&1 | while IFS= read -r line; do
                if [[ "$line" =~ "Collecting" ]] || [[ "$line" =~ "Downloading" ]] || [[ "$line" =~ "Installing" ]]; then
                    echo "      $line"
                fi
            done
            deactivate
            echo -e "${GREEN}  ✓${NC} $dir configured"
        fi
    fi
done

cd "$INSTALL_DIR"
echo -e "${GREEN}✓${NC} Sub-environments configured"

# Create molt-speak CLI launcher
echo -e "${YELLOW}! Creating molt-speak command...${NC}"

LAUNCHER_SCRIPT="/usr/local/bin/molt-speak"

sudo tee "$LAUNCHER_SCRIPT" > /dev/null << 'EOF'
#!/bin/bash

INSTALL_DIR="$HOME/.molt-speak"

case "$1" in
    start)
        # Check if menu bar app is already running
        if pgrep -f "unified_menu_bar.py" > /dev/null; then
            echo "OpenSpeak menu bar is already running"
            echo ""
            echo "To stop and restart:"
            echo "  molt-speak quit"
            echo "  molt-speak start"
            exit 0
        fi

        echo "Starting OpenSpeak Menu Bar..."
        cd "$INSTALL_DIR"

        # Start menu bar app for voice control
        if [ -f "start_menu_bar.sh" ]; then
            ./start_menu_bar.sh
        else
            # Fallback: run directly
            source venv/bin/activate
            python3 unified_menu_bar.py
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
        echo ""
        echo "Note: Menu bar app still running. Use 'molt-speak quit' to quit everything."
        ;;

    quit)
        echo "Quitting OpenSpeak completely..."
        cd "$INSTALL_DIR"

        # Stop voice loop first
        if [ -f "stop_voice_loop.sh" ]; then
            ./stop_voice_loop.sh 2>/dev/null
        else
            pkill -f "unified_audio" 2>/dev/null
            pkill -f "main.py" 2>/dev/null
        fi

        # Quit menu bar app
        pkill -f "unified_menu_bar.py" 2>/dev/null
        echo "✓ All OpenSpeak processes stopped"
        ;;

    status)
        echo "Checking OpenSpeak status..."
        if pgrep -f "unified_menu_bar.py" > /dev/null; then
            echo "✓ Menu bar app is running"
        else
            echo "✗ Menu bar app is not running"
        fi
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
        echo "  start    - Open menu bar control (select voice & start)"
        echo "  stop     - Stop the voice loop (menu bar stays open)"
        echo "  quit     - Quit everything (voice loop + menu bar)"
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
echo -e "${RED}⚠️  IMPORTANT:${NC} You must have OpenClaw TUI running in"
echo -e "   its own terminal window for Molt-Speak to work."
echo -e "   The voice system types transcribed speech into the agent."
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
