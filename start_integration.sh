#!/bin/bash
#
# Start OpenClaw Voice Loop Integration
#
# This script starts the coordinator that bridges OpenClaw Ears and OpenClaw Mouth
# to prevent echo/feedback in voice conversations.
#

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}OpenClaw Voice Loop Integration${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Run the integration coordinator
echo "Starting coordinator..."
echo ""
python main.py "$@"
