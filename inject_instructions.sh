#!/bin/bash
# Manually inject agent instructions into openclaw terminal

INSTRUCTIONS_FILE="$HOME/.openclaw/agent_instructions.active"

if [ ! -f "$INSTRUCTIONS_FILE" ]; then
    echo "Error: Instructions file not found"
    echo "Start the voice loop first: molt-speak start"
    exit 1
fi

# Copy to clipboard
cat "$INSTRUCTIONS_FILE" | pbcopy

echo "Instructions copied to clipboard!"
echo ""
echo "Now paste in your agent terminal:"
echo "  1. Focus your Claude agent terminal window"
echo "  2. Press Cmd+V to paste"
echo "  3. Press Enter"
echo ""
echo "Or just run this in your agent terminal:"
echo "  cat $INSTRUCTIONS_FILE"
