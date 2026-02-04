#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="$HOME/openclaw-workspace/molt-speak/app"
REPO_URL="https://github.com/jamescodes84/molt-speak.git"
BRANCH="${BRANCH:-develop}"  # Default to develop branch (main uses main)

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

    # Fetch first so we can reset to remote
    git fetch origin

    # Remove venv before reset to avoid conflicts (it was tracked in old commits)
    if [ -d "$INSTALL_DIR/venv" ]; then
        echo -e "${BLUE}  Removing old venv to avoid conflicts...${NC}"
        rm -rf "$INSTALL_DIR/venv"
    fi

    # Reset to remote branch (not local HEAD) to skip over commits where venv was tracked
    git reset --hard origin/$BRANCH 2>/dev/null || true
    git clean -fd 2>/dev/null || true
    git checkout $BRANCH 2>/dev/null || true
else
    echo -e "${YELLOW}! Cloning Molt-Speak repository (branch: $BRANCH)...${NC}"
    git clone -b $BRANCH "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "${GREEN}✓${NC} Repository ready at $INSTALL_DIR"

# Set up Python virtual environment
echo -e "${YELLOW}! Setting up unified Python virtual environment...${NC}"

# Deactivate any existing venv first
deactivate 2>/dev/null || true

# Remove old separate venvs if they exist (cleanup from old architecture)
if [ -d "$INSTALL_DIR/open_mouth/venv" ]; then
    echo -e "${BLUE}  Removing old open_mouth/venv...${NC}"
    rm -rf "$INSTALL_DIR/open_mouth/venv"
fi
if [ -d "$INSTALL_DIR/open_ears/venv" ]; then
    echo -e "${BLUE}  Removing old open_ears/venv...${NC}"
    rm -rf "$INSTALL_DIR/open_ears/venv"
fi

# Create unified environment - use absolute paths
MAIN_VENV="$INSTALL_DIR/venv"
if [ ! -d "$MAIN_VENV" ]; then
    echo -e "${BLUE}  Creating virtual environment...${NC}"
    python3 -m venv "$MAIN_VENV"
fi

source "$MAIN_VENV/bin/activate"
echo -e "${BLUE}  Upgrading pip...${NC}"
pip install --upgrade pip > /dev/null 2>&1

# Install all dependencies from unified requirements.txt
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    echo -e "${YELLOW}  Installing dependencies (PyTorch + Whisper - may take 2-5 min)...${NC}"
    pip install -r "$INSTALL_DIR/requirements.txt" 2>&1 | while IFS= read -r line; do
        if [[ "$line" =~ "Collecting" ]] || [[ "$line" =~ "Downloading" ]] || [[ "$line" =~ "Installing" ]] || [[ "$line" =~ "Successfully" ]]; then
            echo "    $line"
        fi
    done
else
    echo -e "${YELLOW}Warning: No requirements.txt found${NC}"
fi

deactivate

echo -e "${GREEN}✓${NC} Virtual environment configured with all dependencies"

# Create molt-speak CLI launcher
echo -e "${YELLOW}! Creating molt-speak command...${NC}"

LAUNCHER_SCRIPT="/usr/local/bin/molt-speak"

sudo tee "$LAUNCHER_SCRIPT" > /dev/null << 'EOF'
#!/bin/bash

INSTALL_DIR="$HOME/openclaw-workspace/molt-speak/app"

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

        # Clean up stale tmp files that may have wrong permissions
        rm -f /tmp/speak.txt 2>/dev/null || sudo rm -f /tmp/speak.txt 2>/dev/null || true

        echo "Starting OpenSpeak Menu Bar..."
        cd "$INSTALL_DIR"

        # Start menu bar app for voice control
        if [ -f "scripts/start_menu_bar.sh" ]; then
            ./scripts/start_menu_bar.sh
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
        if [ -f "scripts/stop_voice_loop.sh" ]; then
            ./scripts/stop_voice_loop.sh
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
        if [ -f "scripts/stop_voice_loop.sh" ]; then
            ./scripts/stop_voice_loop.sh 2>/dev/null
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

        # Detect current branch
        CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
        echo "  Current branch: $CURRENT_BRANCH"

        # Fetch first so we can reset to remote
        git fetch origin

        # Remove venv before reset to avoid conflicts
        if [ -d "$INSTALL_DIR/venv" ]; then
            echo "  Removing old venv to avoid conflicts..."
            rm -rf "$INSTALL_DIR/venv"
        fi

        # Reset to remote branch (not local HEAD) to skip over commits where venv was tracked
        git reset --hard origin/$CURRENT_BRANCH 2>/dev/null || true
        git clean -fd 2>/dev/null || true

        # Recreate venv
        echo "  Recreating virtual environment..."
        python3 -m venv "$INSTALL_DIR/venv"
        source "$INSTALL_DIR/venv/bin/activate"
        pip install --upgrade pip > /dev/null 2>&1
        pip install -r requirements.txt 2>&1 | grep -E "(Collecting|Installing|Successfully)" || true
        deactivate

        # Clean up stale tmp files that may have wrong permissions
        rm -f /tmp/speak.txt 2>/dev/null || sudo rm -f /tmp/speak.txt 2>/dev/null || true

        echo "✓ OpenSpeak updated"
        ;;

    elo)
        echo "Configuring ElevenLabs TTS..."
        cd "$INSTALL_DIR"

        # Check if script exists
        if [ ! -f "scripts/molt-speak-elo.sh" ]; then
            echo "Error: ElevenLabs configuration script not found"
            echo "Please update to the latest version: molt-speak update"
            exit 1
        fi

        # Run the configuration script
        ./scripts/molt-speak-elo.sh
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
        echo "  elo      - Configure ElevenLabs TTS (premium voices)"
        echo ""
        ;;
esac
EOF

sudo chmod +x "$LAUNCHER_SCRIPT"

echo -e "${GREEN}✓${NC} molt-speak command installed"

# Create runtime directory
mkdir -p "$INSTALL_DIR/runtime"
mkdir -p "$INSTALL_DIR/logs"

# Create speech output file in project runtime directory
touch "$INSTALL_DIR/runtime/speech_output.txt"
chmod 666 "$INSTALL_DIR/runtime/speech_output.txt"

# Clean up stale tmp files that may have wrong permissions from other users
rm -f /tmp/speak.txt 2>/dev/null || sudo rm -f /tmp/speak.txt 2>/dev/null || true

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Installation Complete! 🎉          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║                    ⚠️  IMPORTANT ⚠️                         ║${NC}"
echo -e "${RED}╠════════════════════════════════════════════════════════════╣${NC}"
echo -e "${RED}║  You MUST have OpenClaw TUI running in its own terminal    ║${NC}"
echo -e "${RED}║  window for Molt-Speak to work.                            ║${NC}"
echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Installed at: ${BLUE}$INSTALL_DIR${NC}"
echo ""
echo -e "Quick Start:"
echo -e "  1. Open a terminal and start OpenClaw TUI (your AI agent)"
echo -e "  2. Run: ${YELLOW}molt-speak start${NC}"
echo -e "  3. Start talking!"
echo ""
echo -e "Commands:"
echo -e "  ${YELLOW}molt-speak start${NC}   - Start the voice loop"
echo -e "  ${YELLOW}molt-speak stop${NC}    - Stop the voice loop"
echo -e "  ${YELLOW}molt-speak status${NC}  - Check status"
echo -e "  ${YELLOW}molt-speak update${NC}  - Update to latest version"
echo ""
