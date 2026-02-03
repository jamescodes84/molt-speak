#!/bin/bash
# Quick fix to set up missing venvs

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="${HOME}/.openspeak"
cd "$INSTALL_DIR"

echo ""
echo -e "${BLUE}Setting up open_mouth venv...${NC}"
cd open_mouth
if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo "  Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "  Installing dependencies (this may take a minute)..."
pip install -r requirements.txt 2>&1 | while IFS= read -r line; do
    if [[ "$line" =~ "Collecting" ]] || [[ "$line" =~ "Downloading" ]] || [[ "$line" =~ "Installing" ]]; then
        echo "    $line"
    fi
done
deactivate
echo -e "${GREEN}✓ open_mouth ready${NC}"
echo ""

cd "$INSTALL_DIR"
echo -e "${BLUE}Setting up open_ears venv...${NC}"
cd open_ears
if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo "  Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo -e "${YELLOW}  Installing dependencies (PyTorch + Whisper - this takes 2-5 minutes)...${NC}"
pip install -r requirements.txt 2>&1 | while IFS= read -r line; do
    if [[ "$line" =~ "Collecting" ]] || [[ "$line" =~ "Downloading" ]] || [[ "$line" =~ "Installing" ]]; then
        echo "    $line"
    fi
done
deactivate
echo -e "${GREEN}✓ open_ears ready${NC}"

echo ""
echo -e "${GREEN}✓ All venvs configured${NC}"
echo ""
echo "Now run: molt-speak start"
