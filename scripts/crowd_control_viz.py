#!/usr/bin/env python3
"""Crowd Control debug visualizer (terminal-based).

Polls runtime/crowd_control_status.json every 200ms and displays
real-time audio level, speaker gate decisions, and a decision log
using ANSI escape codes in the terminal.

Launched from the menu bar (opens in a Terminal window) or CLI:
    python3 scripts/crowd_control_viz.py --config-dir ./runtime
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

# ── ANSI Colors ──────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

BAR_WIDTH = 40  # characters wide for meters


def bar(value: float, max_val: float, width: int = BAR_WIDTH,
        fill_color: str = GREEN) -> str:
    """Render a colored progress bar."""
    ratio = min(1.0, value / max_val) if max_val > 0 else 0.0
    filled = int(ratio * width)
    empty = width - filled
    return f"{fill_color}{'█' * filled}{DIM}{'░' * empty}{RESET}"


def threshold_bar(value: float, threshold: float, width: int = BAR_WIDTH) -> str:
    """Render a similarity bar with a threshold marker."""
    val_pos = min(width, int(value * width))
    thresh_pos = min(width, int(threshold * width))

    color = GREEN if value >= threshold else (RED if value > 0 else DIM)
    chars = []
    for i in range(width):
        if i == thresh_pos:
            chars.append(f"{RED}│{RESET}")
        elif i < val_pos:
            chars.append(f"{color}█{RESET}")
        else:
            chars.append(f"{DIM}░{RESET}")
    return "".join(chars)


class CrowdControlViz:
    """Terminal-based real-time Crowd Control debug visualizer."""

    def __init__(self, config_dir: Path):
        self.status_file = config_dir / "crowd_control_status.json"
        self.decision_log: deque[str] = deque(maxlen=12)
        self.accepted_count = 0
        self.rejected_count = 0
        self._last_decision_ts = 0.0
        self._running = True

    def run(self) -> None:
        """Main loop — poll and redraw."""
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

        sys.stdout.write(HIDE_CURSOR)
        sys.stdout.flush()

        try:
            while self._running:
                data = self._read_status()
                self._draw(data)
                time.sleep(0.2)
        finally:
            sys.stdout.write(SHOW_CURSOR + "\n")
            sys.stdout.flush()

    def _handle_exit(self, sig: int, frame) -> None:
        self._running = False

    def _read_status(self) -> dict:
        try:
            if self.status_file.exists():
                raw = self.status_file.read_text()
                if raw.strip():
                    return json.loads(raw)
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _draw(self, data: dict) -> None:
        rms = data.get("rms", 0)
        vad = data.get("vad", False)
        gate_state = data.get("gate_state", "idle")
        decision = data.get("decision", "pending")
        similarity = data.get("similarity", 0.0)
        threshold = data.get("threshold", 0.82)
        buffered_ms = data.get("buffered_ms", 0)
        enrolled = data.get("enrolled", False)
        ts = data.get("ts", 0)

        # ── Track decisions ─────────────────────────────────────────────
        if gate_state == "decided" and ts > self._last_decision_ts:
            self._last_decision_ts = ts
            time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            color = GREEN if decision == "accepted" else RED
            tag = "ACCEPTED" if decision == "accepted" else "REJECTED"
            entry = f"  {color}{time_str}  {tag:>8s}  sim={similarity:.2f}  rms={rms:.0f}{RESET}"
            self.decision_log.appendleft(entry)
            if decision == "accepted":
                self.accepted_count += 1
            else:
                self.rejected_count += 1

        # ── Audio level color ───────────────────────────────────────────
        if rms > 200:
            level_color = GREEN
        elif rms > 50:
            level_color = YELLOW
        else:
            level_color = DIM

        # ── Decision badge ──────────────────────────────────────────────
        if not enrolled:
            badge = f"{DIM}  NOT ENROLLED  {RESET}"
        elif gate_state == "decided":
            if decision == "accepted":
                badge = f"{GREEN}{BOLD}  ACCEPTED — Owner ({similarity:.2f})  {RESET}"
            else:
                badge = f"{RED}{BOLD}  REJECTED — Not Owner ({similarity:.2f})  {RESET}"
        elif gate_state == "accumulating":
            badge = f"{YELLOW}{BOLD}  ACCUMULATING ({buffered_ms}ms)  {RESET}"
        elif vad:
            badge = f"{BLUE}{BOLD}  SPEECH (no gate)  {RESET}"
        else:
            badge = f"{DIM}  IDLE  {RESET}"

        # ── VAD ─────────────────────────────────────────────────────────
        if vad:
            vad_str = f"{GREEN}Speech{RESET}"
        else:
            vad_str = f"{DIM}Silence{RESET}"

        # ── Compose screen ──────────────────────────────────────────────
        lines = []
        lines.append(CLEAR_SCREEN)
        lines.append(f"{BLUE}{BOLD}╔════════════════════════════════════════════════════════════╗{RESET}")
        lines.append(f"{BLUE}{BOLD}║          Crowd Control Debug Visualizer                   ║{RESET}")
        lines.append(f"{BLUE}{BOLD}╚════════════════════════════════════════════════════════════╝{RESET}")
        lines.append("")

        # Audio Level
        lines.append(f"  {BOLD}Audio Level{RESET}")
        lines.append(f"  {bar(rms, 1000, BAR_WIDTH, level_color)}  RMS: {rms:.0f}")
        lines.append("")

        # Speaker Gate
        lines.append(f"  {BOLD}Speaker Gate{RESET}")
        lines.append(f"  {badge}")
        lines.append("")
        lines.append(f"  Similarity: {threshold_bar(similarity, threshold)}  {similarity:.2f} / {threshold:.2f}")
        lines.append(f"  VAD: {vad_str}    Buffer: {buffered_ms}ms    State: {gate_state}")
        lines.append("")

        # Decision Log
        lines.append(f"  {BOLD}Decision Log{RESET}")
        if self.decision_log:
            for entry in self.decision_log:
                lines.append(entry)
        else:
            lines.append(f"  {DIM}(no decisions yet){RESET}")
        lines.append("")

        # Stats
        lines.append(f"  {DIM}Session: {self.accepted_count} accepted, {self.rejected_count} rejected    Threshold: {threshold:.2f}{RESET}")
        lines.append(f"  {DIM}Ctrl+C to exit{RESET}")

        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Crowd Control debug visualizer")
    parser.add_argument("--config-dir", type=str, default=None,
                        help="Path to config/runtime directory")
    args = parser.parse_args()

    if args.config_dir:
        config_dir = Path(args.config_dir)
    else:
        config_dir = Path(__file__).resolve().parent.parent / "runtime"

    viz = CrowdControlViz(config_dir)
    viz.run()


if __name__ == "__main__":
    main()
