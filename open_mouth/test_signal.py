#!/usr/bin/env python3
"""Quick test to verify the signal file mechanism works."""

import time
from pathlib import Path
from src.utils.openclaw_notifier import OpenClawNotifier


def test_signal_file():
    """Test that the signal file is created and updated correctly."""
    print("Testing OpenClaw Mouth signal file...\n")

    # Create notifier
    notifier = OpenClawNotifier()
    status_file = Path.home() / ".openclaw" / "mouth_status.txt"

    print(f"Signal file location: {status_file}\n")

    # Test different states
    states = [
        ("IDLE", ""),
        ("QUEUED", "3 items"),
        ("SPEAKING", "Hello, this is a test message"),
        ("IDLE", ""),
    ]

    for status, details in states:
        print(f"Setting status: {status} - {details}")
        notifier.update_status(status, details)

        # Verify file contents
        if status_file.exists():
            with open(status_file, "r") as f:
                content = f.read().strip()
            print(f"  File contents: {content}")
        else:
            print(f"  ERROR: File not found!")

        print()
        time.sleep(1)

    # Cleanup
    notifier.cleanup()
    print(f"Cleanup complete. File removed: {not status_file.exists()}")


if __name__ == "__main__":
    test_signal_file()
