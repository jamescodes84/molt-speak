#!/usr/bin/env python3
"""Launcher script for OpenClaw Mouth menu bar application."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gui.menu_bar_app import main

if __name__ == "__main__":
    main()
