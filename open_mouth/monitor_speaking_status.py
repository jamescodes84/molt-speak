#!/usr/bin/env python3
"""
Demonstration script showing how OpenClaw Ears can monitor when Mouth is speaking.

This script monitors the ~/.openclaw/mouth_status.txt file and prints status changes.
OpenClaw Ears can use this mechanism to pause listening when the agent is speaking.
"""

import time
from pathlib import Path
from datetime import datetime


def monitor_mouth_status(interval: float = 0.1):
    """
    Monitor the Mouth status file and report when speaking status changes.

    Args:
        interval: How often to check the file (in seconds)
    """
    status_file = Path.home() / ".openclaw" / "mouth_status.txt"
    last_status = None
    last_content = None

    print("=" * 70)
    print("OpenClaw Ears - Mouth Status Monitor")
    print("=" * 70)
    print(f"\nMonitoring: {status_file}")
    print("\nThis demonstrates how OpenClaw Ears can detect when the agent is speaking")
    print("and pause listening to avoid picking up the agent's own voice.\n")
    print("Press Ctrl+C to stop.\n")
    print("-" * 70)

    try:
        while True:
            try:
                if status_file.exists():
                    with open(status_file, "r") as f:
                        content = f.read().strip()

                    # Only report if content changed
                    if content != last_content:
                        last_content = content

                        # Parse status file format: timestamp|status|details
                        parts = content.split("|")
                        if len(parts) >= 2:
                            timestamp_str = parts[0]
                            status = parts[1]
                            details = parts[2] if len(parts) > 2 else ""

                            # Report status change
                            if status != last_status:
                                last_status = status
                                now = datetime.now().strftime("%H:%M:%S")

                                if status == "SPEAKING":
                                    print(f"[{now}] 🔊 AGENT SPEAKING - Ears should PAUSE listening")
                                    if details:
                                        print(f"         Text: {details}")
                                elif status == "IDLE":
                                    print(f"[{now}] ✅ AGENT IDLE - Ears can RESUME listening")
                                elif status == "QUEUED":
                                    print(f"[{now}] ⏳ QUEUED - {details}")
                                elif status == "ERROR":
                                    print(f"[{now}] ❌ ERROR - {details}")
                                else:
                                    print(f"[{now}] Status: {status} - {details}")

                                print("-" * 70)
                else:
                    if last_status is not None:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ℹ️  Status file not found - Mouth may not be running")
                        print("-" * 70)
                        last_status = None
                        last_content = None

            except Exception as e:
                print(f"Error reading status file: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


if __name__ == "__main__":
    monitor_mouth_status()
