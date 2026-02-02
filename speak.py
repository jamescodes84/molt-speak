#!/usr/bin/env python3
"""
Simple speak command for OpenClaw voice loop.

Usage:
    python speak.py "Hello, this is a test"
    echo "Hello" | python speak.py

Or import and use:
    from speak import speak
    speak("Hello, this is a test")
"""

import sys
from pathlib import Path

SPEECH_FILE = Path.home() / ".molt-speak" / "runtime" / "speech_output.txt"


def speak(text: str) -> None:
    """Write text to the speech output file for OpenClaw Mouth to speak."""
    SPEECH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEECH_FILE, "a") as f:
        f.write(f"{text}\n")
        f.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Text passed as argument
        text = " ".join(sys.argv[1:])
        speak(text)
        print(f"[SPEAKING] {text}")
    elif not sys.stdin.isatty():
        # Text piped from stdin
        for line in sys.stdin:
            line = line.strip()
            if line:
                speak(line)
                print(f"[SPEAKING] {line}")
    else:
        print("Usage: python speak.py 'text to speak'")
        print("       echo 'text' | python speak.py")
        sys.exit(1)
