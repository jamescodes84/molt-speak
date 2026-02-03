#!/bin/bash
# OpenClaw Mouth - TTS System Startup Script

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   OpenClaw Mouth - TTS System Startup${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install/update dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create speech output directory - use hidden directory for reliable permissions
SPEECH_OUTPUT_DIR="$HOME/.molt-speak/runtime"
if [ ! -d "$SPEECH_OUTPUT_DIR" ]; then
    echo -e "${YELLOW}Creating $SPEECH_OUTPUT_DIR...${NC}"
    mkdir -p "$SPEECH_OUTPUT_DIR"
    chmod 755 "$SPEECH_OUTPUT_DIR"
    echo -e "${GREEN}✓ Directory created${NC}"
fi

# Create input file if it doesn't exist
INPUT_FILE="$SPEECH_OUTPUT_DIR/speech_output.txt"
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${YELLOW}Creating input file...${NC}"
    touch "$INPUT_FILE"
    echo -e "${GREEN}✓ Input file created at $INPUT_FILE${NC}"
fi

echo ""
echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}Starting OpenClaw Mouth TTS System...${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""
echo -e "Input file: ${YELLOW}$INPUT_FILE${NC}"
echo -e "To speak text, write to this file:"
echo -e "  ${YELLOW}echo \"Hello world\" >> $INPUT_FILE${NC}"
echo ""
echo -e "Options:"
echo -e "  ${YELLOW}--local${NC}     Use local TTS for INSTANT playback (recommended)"
echo -e "  ${YELLOW}--compact${NC}   Use compact display mode"
echo -e "  ${YELLOW}--voice${NC}     Specify voice (e.g., --voice Alex)"
echo ""
echo -e "Press ${RED}Ctrl+C${NC} to stop"
echo ""

# Start the system
python3 main.py "$@"

# Deactivate virtual environment on exit
deactivate
