#!/bin/bash
# NO set -e — we handle errors explicitly so failures are always visible

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

error_exit() {
    echo "" >&2
    echo -e "${RED}ERROR: $1${NC}" >&2
    echo "" >&2
    exit 1
}

# Installation directory
INSTALL_DIR="$HOME/openclaw-workspace/molt-speak/app"
REPO_URL="https://github.com/jamescodes84/molt-speak.git"
BRANCH="${BRANCH:-main}"

# Function to kill all orphaned molt-speak processes
kill_orphaned_processes() {
    echo -e "${YELLOW}! Cleaning up orphaned processes...${NC}"
    pkill -9 -f "unified_menu_bar" 2>/dev/null || true
    pkill -9 -f "unified_audio" 2>/dev/null || true
    pkill -9 -f "voice_pipeline" 2>/dev/null || true
    pkill -9 -f "mouth_pipeline" 2>/dev/null || true
    pkill -9 -f "molt-speak" 2>/dev/null || true
    pkill -9 -f "open_ears" 2>/dev/null || true
    pkill -9 -f "open_mouth" 2>/dev/null || true
    # Clean up any stale PID files
    rm -f "$INSTALL_DIR/runtime/"*.pid 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Orphaned processes cleaned up"
}

# Kill any orphaned processes before starting
kill_orphaned_processes

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

# Determine source: local directory (tar/dev) or git clone
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOCAL_SOURCE=false

# If this script is inside a directory with main.py + open_ears/ + open_mouth/,
# use local files instead of cloning from GitHub
if [ -f "$SCRIPT_DIR/main.py" ] && [ -d "$SCRIPT_DIR/open_ears" ] && [ -d "$SCRIPT_DIR/open_mouth" ]; then
    LOCAL_SOURCE=true
    echo -e "${GREEN}✓${NC} Local source detected — installing from local files"
fi

if [ "$LOCAL_SOURCE" = true ]; then
    # Install from local files (tar or dev directory)
    # Preserve runtime config
    if [ -d "$INSTALL_DIR/runtime" ]; then
        cp -r "$INSTALL_DIR/runtime" /tmp/molt-speak-runtime-backup 2>/dev/null || true
    fi

    # Remove old venv to avoid conflicts
    if [ -d "$INSTALL_DIR/venv" ]; then
        echo -e "${BLUE}  Removing old venv to avoid conflicts...${NC}"
        rm -rf "$INSTALL_DIR/venv"
    fi

    # Copy local files to install directory (exclude dev artifacts)
    mkdir -p "$INSTALL_DIR"
    rsync -a --delete \
        --exclude='.git' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='.env' \
        --exclude='runtime' \
        --exclude='logs' \
        --exclude='*.pyc' \
        --exclude='.DS_Store' \
        "$SCRIPT_DIR/" "$INSTALL_DIR/"

    cd "$INSTALL_DIR"

    # Restore runtime config
    if [ -d /tmp/molt-speak-runtime-backup ]; then
        mkdir -p "$INSTALL_DIR/runtime"
        cp -r /tmp/molt-speak-runtime-backup/* "$INSTALL_DIR/runtime/" 2>/dev/null || true
        rm -rf /tmp/molt-speak-runtime-backup
    fi
elif [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${YELLOW}! Molt-Speak directory exists. Updating from GitHub...${NC}"
    cd "$INSTALL_DIR"

    # Remove venv before reset to avoid conflicts (it was tracked in old commits)
    if [ -d "$INSTALL_DIR/venv" ]; then
        echo -e "${BLUE}  Removing old venv to avoid conflicts...${NC}"
        rm -rf "$INSTALL_DIR/venv"
    fi

    # Try to update via git — if anything fails, fall back to fresh clone
    UPDATE_OK=true
    # Force-fetch to handle history rewrites (orphan commits, force pushes)
    git fetch origin "+refs/heads/*:refs/remotes/origin/*" 2>&1 || UPDATE_OK=false
    if [ "$UPDATE_OK" = true ]; then
        git reset --hard origin/$BRANCH 2>&1 || UPDATE_OK=false
    fi
    if [ "$UPDATE_OK" = true ]; then
        git clean -fd -e runtime/ 2>/dev/null || true
    fi

    if [ "$UPDATE_OK" = false ]; then
        echo -e "${YELLOW}! Git update failed. Performing fresh install...${NC}"
        # Preserve runtime config
        if [ -d "$INSTALL_DIR/runtime" ]; then
            cp -r "$INSTALL_DIR/runtime" /tmp/molt-speak-runtime-backup 2>/dev/null || true
        fi
        cd "$HOME"
        rm -rf "$INSTALL_DIR"
        git clone -b $BRANCH "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
        # Restore runtime config
        if [ -d /tmp/molt-speak-runtime-backup ]; then
            cp -r /tmp/molt-speak-runtime-backup/* "$INSTALL_DIR/runtime/" 2>/dev/null || true
            rm -rf /tmp/molt-speak-runtime-backup
        fi
    fi
else
    # No .git directory — clean slate or corrupted install
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}! Corrupted install detected. Performing fresh install...${NC}"
        # Preserve runtime config
        if [ -d "$INSTALL_DIR/runtime" ]; then
            cp -r "$INSTALL_DIR/runtime" /tmp/molt-speak-runtime-backup 2>/dev/null || true
        fi
        rm -rf "$INSTALL_DIR"
    fi

    echo -e "${YELLOW}! Cloning Molt-Speak repository (branch: $BRANCH)...${NC}"
    git clone -b $BRANCH "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    # Restore runtime config if backed up
    if [ -d /tmp/molt-speak-runtime-backup ]; then
        mkdir -p "$INSTALL_DIR/runtime"
        cp -r /tmp/molt-speak-runtime-backup/* "$INSTALL_DIR/runtime/" 2>/dev/null || true
        rm -rf /tmp/molt-speak-runtime-backup
    fi
fi

echo -e "${GREEN}✓${NC} Repository ready at $INSTALL_DIR"

# Ensure scripts are executable (tar may strip permissions)
chmod +x "$INSTALL_DIR/scripts/"*.sh 2>/dev/null || true

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
    if [ $? -ne 0 ]; then
        error_exit "Failed to create virtual environment. Is python3 installed?"
    fi
fi

source "$MAIN_VENV/bin/activate" || error_exit "Failed to activate virtual environment"
echo -e "${BLUE}  Upgrading pip...${NC}"
pip install --upgrade pip > /dev/null 2>&1

# Install all dependencies from unified requirements.txt
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    echo -e "${YELLOW}  Installing dependencies (PyTorch + Whisper - may take 2-5 min)...${NC}"
    # Write pip output to a temp file so we can capture BOTH the exit code AND show progress
    PIP_LOG=$(mktemp)
    pip install -r "$INSTALL_DIR/requirements.txt" 2>&1 | tee "$PIP_LOG" | while IFS= read -r line; do
        if [[ "$line" =~ "Collecting" ]] || [[ "$line" =~ "Downloading" ]] || [[ "$line" =~ "Installing" ]] || [[ "$line" =~ "Successfully" ]]; then
            echo "    $line"
        fi
    done
    # Check if pip actually succeeded by verifying a critical import
    if ! python3 -c "import sounddevice, edge_tts, rumps" 2>/dev/null; then
        echo ""
        echo -e "${RED}Some dependencies failed to install. Pip output:${NC}"
        tail -20 "$PIP_LOG"
        rm -f "$PIP_LOG"
        error_exit "pip install failed. Check the output above and try again."
    fi
    rm -f "$PIP_LOG"
else
    error_exit "requirements.txt not found — installation is incomplete"
fi

deactivate

echo -e "${GREEN}✓${NC} Virtual environment configured with all dependencies"

# Create moltspeak CLI launcher
echo -e "${YELLOW}! Creating moltspeak command...${NC}"

LAUNCHER_SCRIPT="/usr/local/bin/moltspeak"

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
            echo "  moltspeak quit"
            echo "  moltspeak start"
            exit 0
        fi

        # Clean up stale tmp files that may have wrong permissions
        rm -f /tmp/speak.txt 2>/dev/null || sudo rm -f /tmp/speak.txt 2>/dev/null || true

        echo "Starting OpenSpeak Menu Bar..."
        cd "$INSTALL_DIR"

        # Start menu bar app for voice control
        if [ -f "scripts/start_menu_bar.sh" ]; then
            bash scripts/start_menu_bar.sh
        elif [ -f "venv/bin/activate" ]; then
            # Fallback: run directly
            source venv/bin/activate
            python3 unified_menu_bar.py
        else
            echo "Error: Cannot start — venv not found. Run: bash install.sh"
            exit 1
        fi
        ;;

    stop)
        echo "Stopping OpenSpeak Voice Loop..."
        cd "$INSTALL_DIR"

        # Use the project's stop script if available
        if [ -f "scripts/stop_voice_loop.sh" ]; then
            bash scripts/stop_voice_loop.sh
        else
            # Fallback: kill processes
            pkill -f "unified_audio"
            pkill -f "main.py"
            echo "Voice loop stopped."
        fi
        echo ""
        echo "Note: Menu bar app still running. Use 'moltspeak quit' to quit everything."
        ;;

    quit)
        echo "Quitting OpenSpeak completely..."
        cd "$INSTALL_DIR"

        # Stop voice loop first
        if [ -f "scripts/stop_voice_loop.sh" ]; then
            bash scripts/stop_voice_loop.sh 2>/dev/null
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
                echo "Usage: moltspeak logs [audio|integration]"
                ls -1 "$LOG_DIR"/*.log 2>/dev/null | xargs -n1 basename
                ;;
        esac
        ;;

    update)
        # Block update if installed from tar (no .git = no remote to pull from)
        if [ ! -d "$INSTALL_DIR/.git" ]; then
            echo "This install was done from a local package."
            echo "To update, download the latest package and run install.sh again."
            exit 0
        fi

        echo "Updating OpenSpeak..."

        # Kill all orphaned processes first
        echo "  Killing orphaned processes..."
        pkill -9 -f "unified_menu_bar" 2>/dev/null || true
        pkill -9 -f "unified_audio" 2>/dev/null || true
        pkill -9 -f "voice_pipeline" 2>/dev/null || true
        pkill -9 -f "mouth_pipeline" 2>/dev/null || true
        pkill -9 -f "open_ears" 2>/dev/null || true
        pkill -9 -f "open_mouth" 2>/dev/null || true
        rm -f "$INSTALL_DIR/runtime/"*.pid 2>/dev/null || true
        echo "  ✓ Processes cleaned up"

        cd "$INSTALL_DIR"

        # Detect current branch
        CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
        echo "  Current branch: $CURRENT_BRANCH"

        # Fetch with force to handle history rewrites (orphan commits, force pushes)
        git fetch origin "+refs/heads/*:refs/remotes/origin/*" 2>/dev/null

        # Remove venv before reset to avoid conflicts
        if [ -d "$INSTALL_DIR/venv" ]; then
            echo "  Removing old venv to avoid conflicts..."
            rm -rf "$INSTALL_DIR/venv"
        fi

        # Reset to remote branch — if this fails (e.g. no common history), do a fresh clone
        if ! git reset --hard origin/$CURRENT_BRANCH 2>/dev/null; then
            echo -e "${YELLOW}! Git history diverged. Performing fresh install...${NC}"
            # Preserve user config
            mkdir -p /tmp/molt-speak-update-backup
            cp "$INSTALL_DIR/runtime/molt_speak_config.json" /tmp/molt-speak-update-backup/ 2>/dev/null || true
            cp "$INSTALL_DIR/runtime/known_entities.json" /tmp/molt-speak-update-backup/ 2>/dev/null || true
            # Fresh clone
            cd /tmp
            rm -rf "$INSTALL_DIR"
            git clone -b main "$REPO_URL" "$INSTALL_DIR"
            cd "$INSTALL_DIR"
            # Restore user config
            if [ -d /tmp/molt-speak-update-backup ]; then
                mkdir -p "$INSTALL_DIR/runtime"
                cp /tmp/molt-speak-update-backup/* "$INSTALL_DIR/runtime/" 2>/dev/null || true
                rm -rf /tmp/molt-speak-update-backup
            fi
        fi
        # Clean untracked files but preserve runtime/ (contains user config)
        git clean -fd -e runtime/ 2>/dev/null || true

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
        echo ""
        echo "Commands:"
        echo "  moltspeak start   - Start the voice loop"
        echo "  moltspeak update  - Update to latest version"
        echo "  moltspeak elapi   - Set ElevenLabs API key"
        ;;

    elapi)
        echo "Setting ElevenLabs API Key..."
        cd "$INSTALL_DIR"

        # Check if script exists
        if [ ! -f "scripts/molt-speak-elapi.sh" ]; then
            echo "Error: ElevenLabs API key script not found"
            echo "ElevenLabs script missing. Reinstall: rm -rf venv && bash install.sh"
            exit 1
        fi

        # Run the configuration script
        bash scripts/molt-speak-elapi.sh
        ;;

    diagnose)
        echo ""
        cd "$INSTALL_DIR"
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        if [ -f "src/diagnostics/preflight.py" ]; then
            if [ "$2" = "--network" ]; then
                python3 -m src.diagnostics.preflight --network
            else
                python3 -m src.diagnostics.preflight
            fi
        else
            echo "Diagnostics not available — reinstall: rm -rf venv && bash install.sh"
        fi
        ;;

    kill)
        echo "Nuclear kill - terminating ALL molt-speak processes..."
        # Kill by process name patterns (SIGKILL)
        pkill -9 -f "unified_menu_bar" 2>/dev/null || true
        pkill -9 -f "unified_audio" 2>/dev/null || true
        pkill -9 -f "voice_pipeline" 2>/dev/null || true
        pkill -9 -f "mouth_pipeline" 2>/dev/null || true
        pkill -9 -f "open_ears" 2>/dev/null || true
        pkill -9 -f "open_mouth" 2>/dev/null || true
        pkill -9 -f "MoltSpeak" 2>/dev/null || true
        pkill -9 -f "molt-speak" 2>/dev/null || true
        # Kill any Python processes in the molt-speak directory
        pkill -9 -f "$INSTALL_DIR" 2>/dev/null || true
        # Clean up PID files
        rm -f "$INSTALL_DIR/runtime/"*.pid 2>/dev/null || true
        # Clean up status files
        rm -f "$INSTALL_DIR/runtime/"*_status.txt 2>/dev/null || true
        echo "✓ All moltspeak processes terminated"
        ;;

    *)
        echo "OpenSpeak Voice Loop - moltspeak command"
        echo ""
        echo "Usage: moltspeak [command]"
        echo ""
        echo "Commands:"
        echo "  start     - Open menu bar control (select voice & start)"
        echo "  stop      - Stop the voice loop (menu bar stays open)"
        echo "  quit      - Quit everything (voice loop + menu bar)"
        echo "  kill      - Nuclear kill all processes (use if stuck)"
        echo "  status    - Check if voice loop is running"
        echo "  diagnose  - Run diagnostic checks"
        echo "  logs      - View logs (audio|integration)"
        echo "  update    - Update OpenSpeak to latest version"
        echo "  elapi     - Set ElevenLabs API key"
        echo ""
        ;;
esac
EOF

sudo chmod +x "$LAUNCHER_SCRIPT"

echo -e "${GREEN}✓${NC} moltspeak command installed"

# Create runtime directory
mkdir -p "$INSTALL_DIR/runtime"
mkdir -p "$INSTALL_DIR/logs"

# Create speech output file in project runtime directory
touch "$INSTALL_DIR/runtime/speech_output.txt"
chmod 666 "$INSTALL_DIR/runtime/speech_output.txt"

# Clean up stale tmp files that may have wrong permissions from other users
rm -f /tmp/speak.txt 2>/dev/null || sudo rm -f /tmp/speak.txt 2>/dev/null || true

# Set up PostHog Analytics
echo -e "${YELLOW}! Configuring PostHog Analytics...${NC}"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cat > "$INSTALL_DIR/.env" << 'ENVEOF'
# Analytics (PostHog)
POSTHOG_API_KEY=phc_pVyyYuhVRHc2CEON7HApwzVZ9Mqt5zczNtzyiIUO7mI
POSTHOG_HOST=https://us.i.posthog.com
POSTHOG_DISABLED=false

# Integration Settings
ENABLE_INTEGRATION=true
ENABLE_BIDIRECTIONAL=false

# Monitoring Configuration
MOUTH_STATUS_POLL_INTERVAL=0.1
MOUTH_STATUS_DEBOUNCE_MS=200

# Logging
LOG_LEVEL=INFO
LOG_FILE=

# Performance Tuning
MAX_QUEUE_SIZE=10
PROCESSING_TIMEOUT=30.0
ENVEOF
    echo -e "${GREEN}✓${NC} PostHog Analytics configured"
else
    # Fix stale PostHog host URL from pre-1.1 installs
    if grep -q "app.posthog.com" "$INSTALL_DIR/.env" 2>/dev/null; then
        sed -i '' 's|https://app.posthog.com|https://us.i.posthog.com|g' "$INSTALL_DIR/.env"
        echo -e "${GREEN}✓${NC} .env updated (fixed PostHog host URL)"
    else
        echo -e "${GREEN}✓${NC} .env already exists (keeping existing config)"
    fi
fi

# Initialize analytics and send installation event
echo -e "${YELLOW}! Initializing analytics...${NC}"
cd "$INSTALL_DIR"
source "$MAIN_VENV/bin/activate"

python3 << 'ANALYTICS_INIT'
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path('.').resolve()))

try:
    # Initialize analytics with direct config (load_dotenv doesn't work in heredoc)
    from src.services.analytics import initialize_analytics

    # Initialize with persistent directory (survives uninstalls)
    analytics = initialize_analytics(
        api_key='phc_pVyyYuhVRHc2CEON7HApwzVZ9Mqt5zczNtzyiIUO7mI',
        host='https://us.i.posthog.com',
        disabled=False
    )

    # Send installation event
    analytics.track_event('installation_completed', {
        'install_method': 'curl_script',
        'platform': os.uname().sysname,
        'platform_version': os.uname().release
    })

    # Flush events
    analytics.shutdown()

    # Print to stderr to ensure it shows up
    import sys
    sys.stderr.write(f"✓ Analytics initialized (User ID: {analytics.user_id})\n")
    sys.stderr.flush()

except Exception as e:
    import sys
    sys.stderr.write(f"⚠ Analytics initialization failed (non-fatal): {e}\n")
    sys.stderr.flush()
    # Don't fail the installation if analytics fails
    pass
ANALYTICS_INIT

deactivate
echo -e "${GREEN}✓${NC} Analytics ready"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Molt Speak v1.1.0 Installed! 🎉     ║${NC}"
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
echo -e "  2. Run: ${YELLOW}moltspeak start${NC}"
echo -e "  3. Start talking!"
echo ""
echo -e "Commands:"
echo -e "  ${YELLOW}moltspeak start${NC}   - Start the voice loop"
echo -e "  ${YELLOW}moltspeak stop${NC}    - Stop the voice loop"
echo -e "  ${YELLOW}moltspeak status${NC}  - Check status"
echo -e "  ${YELLOW}moltspeak update${NC}  - Update to latest version"
echo -e "  ${YELLOW}moltspeak elapi${NC}   - Set ElevenLabs API key"
echo ""
