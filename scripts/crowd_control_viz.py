#!/usr/bin/env python3
"""Crowd Control debug visualizer.

Polls runtime/crowd_control_status.json every 100ms and displays
real-time audio level, speaker gate decisions, and a decision log.

Launched as a subprocess from the menu bar or CLI:
    python3 scripts/crowd_control_viz.py --config-dir ./runtime
"""
from __future__ import annotations

import argparse
import json
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path

# ── Colors (matches enroll_gui.py dark theme) ─────────────────────────────

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#89b4fa"
GREEN = "#a6e3a1"
RED = "#f38ba8"
YELLOW = "#f9e2af"
DIM = "#585b70"
METER_BG = "#313244"
BTN_BG = "#45475a"
SURFACE = "#313244"

# Decision colors
COLOR_ACCEPTED = GREEN
COLOR_REJECTED = RED
COLOR_ACCUMULATING = YELLOW
COLOR_IDLE = DIM

POLL_MS = 100  # poll interval


class CrowdControlViz(tk.Tk):
    """Real-time Crowd Control debug visualizer window."""

    def __init__(self, config_dir: Path):
        super().__init__()

        self.config_dir = config_dir
        self.status_file = config_dir / "crowd_control_status.json"

        # Window setup
        self.title("Crowd Control Debug")
        self.geometry("560x520")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._center_window()

        # Session stats
        self.accepted_count = 0
        self.rejected_count = 0
        self._last_decision_ts = 0.0

        self._build_ui()
        self._poll()

    def _center_window(self):
        self.update_idletasks()
        w, h = 560, 520
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        # Title
        tk.Label(self, text="Crowd Control Debug", font=("SF Pro Display", 18, "bold"),
                 bg=BG, fg=FG).pack(pady=(12, 4))

        # ── Audio Level Section ──────────────────────────────────────────
        level_frame = tk.LabelFrame(self, text=" Audio Level ", font=("SF Mono", 11),
                                    bg=BG, fg=DIM, bd=1, relief="groove",
                                    highlightbackground=DIM, highlightthickness=1)
        level_frame.pack(fill="x", padx=16, pady=(8, 4))

        meter_row = tk.Frame(level_frame, bg=BG)
        meter_row.pack(fill="x", padx=8, pady=8)

        self.level_canvas = tk.Canvas(meter_row, width=420, height=22,
                                      bg=METER_BG, highlightthickness=0)
        self.level_canvas.pack(side="left")
        self.level_bar = self.level_canvas.create_rectangle(0, 0, 0, 22, fill=GREEN, outline="")

        self.rms_label = tk.Label(meter_row, text="RMS: 0", font=("SF Mono", 11),
                                  bg=BG, fg=DIM, width=10, anchor="e")
        self.rms_label.pack(side="right", padx=(8, 0))

        # ── Speaker Gate Section ─────────────────────────────────────────
        gate_frame = tk.LabelFrame(self, text=" Speaker Gate ", font=("SF Mono", 11),
                                   bg=BG, fg=DIM, bd=1, relief="groove",
                                   highlightbackground=DIM, highlightthickness=1)
        gate_frame.pack(fill="x", padx=16, pady=4)

        # Decision badge
        self.decision_label = tk.Label(gate_frame, text="  IDLE  ",
                                       font=("SF Pro Display", 14, "bold"),
                                       bg=SURFACE, fg=DIM, padx=12, pady=4)
        self.decision_label.pack(pady=(8, 4))

        # Similarity bar
        sim_row = tk.Frame(gate_frame, bg=BG)
        sim_row.pack(fill="x", padx=8, pady=4)

        tk.Label(sim_row, text="Similarity:", font=("SF Mono", 10),
                 bg=BG, fg=DIM).pack(side="left")

        self.sim_canvas = tk.Canvas(sim_row, width=320, height=18,
                                    bg=METER_BG, highlightthickness=0)
        self.sim_canvas.pack(side="left", padx=(8, 0))
        self.sim_bar = self.sim_canvas.create_rectangle(0, 0, 0, 18, fill=ACCENT, outline="")
        self.threshold_line = self.sim_canvas.create_line(0, 0, 0, 18, fill=RED, width=2)

        self.sim_label = tk.Label(sim_row, text="0.00 / 0.82", font=("SF Mono", 10),
                                  bg=BG, fg=DIM, anchor="e")
        self.sim_label.pack(side="right", padx=(8, 0))

        # Info row: VAD | Buffer | State
        info_row = tk.Frame(gate_frame, bg=BG)
        info_row.pack(fill="x", padx=8, pady=(2, 8))

        self.vad_label = tk.Label(info_row, text="VAD: --", font=("SF Mono", 10),
                                  bg=BG, fg=DIM)
        self.vad_label.pack(side="left", padx=(0, 16))

        self.buffer_label = tk.Label(info_row, text="Buffer: --", font=("SF Mono", 10),
                                     bg=BG, fg=DIM)
        self.buffer_label.pack(side="left", padx=(0, 16))

        self.state_label = tk.Label(info_row, text="State: idle", font=("SF Mono", 10),
                                    bg=BG, fg=DIM)
        self.state_label.pack(side="left")

        # ── Decision Log ─────────────────────────────────────────────────
        log_frame = tk.LabelFrame(self, text=" Decision Log ", font=("SF Mono", 11),
                                  bg=BG, fg=DIM, bd=1, relief="groove",
                                  highlightbackground=DIM, highlightthickness=1)
        log_frame.pack(fill="both", expand=True, padx=16, pady=4)

        self.log_text = tk.Text(log_frame, height=8, font=("SF Mono", 10),
                                bg=SURFACE, fg=FG, bd=0, highlightthickness=0,
                                state="disabled", wrap="none")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Tag colors for log entries
        self.log_text.tag_configure("accepted", foreground=GREEN)
        self.log_text.tag_configure("rejected", foreground=RED)
        self.log_text.tag_configure("dim", foreground=DIM)

        # ── Session Stats ────────────────────────────────────────────────
        stats_row = tk.Frame(self, bg=BG)
        stats_row.pack(fill="x", padx=16, pady=(4, 12))

        self.stats_label = tk.Label(stats_row,
                                    text="Session: 0 accepted, 0 rejected",
                                    font=("SF Mono", 10), bg=BG, fg=DIM)
        self.stats_label.pack(side="left")

        self.thresh_label = tk.Label(stats_row, text="Threshold: 0.82",
                                     font=("SF Mono", 10), bg=BG, fg=DIM)
        self.thresh_label.pack(side="right")

    # ── Polling ──────────────────────────────────────────────────────────

    def _poll(self):
        """Read status file and update UI."""
        try:
            if self.status_file.exists():
                raw = self.status_file.read_text()
                if raw.strip():
                    data = json.loads(raw)
                    self._update_ui(data)
        except (json.JSONDecodeError, OSError):
            pass  # file may be mid-write
        self.after(POLL_MS, self._poll)

    def _update_ui(self, data: dict):
        rms = data.get("rms", 0)
        vad = data.get("vad", False)
        gate_state = data.get("gate_state", "idle")
        decision = data.get("decision", "pending")
        similarity = data.get("similarity", 0.0)
        threshold = data.get("threshold", 0.82)
        buffered_ms = data.get("buffered_ms", 0)
        enrolled = data.get("enrolled", False)
        ts = data.get("ts", 0)

        # ── Audio Level ──────────────────────────────────────────────
        # Scale RMS to bar width (0-420px). RMS typically 0-1000+
        bar_width = min(420, int(rms / 1000 * 420))
        self.level_canvas.coords(self.level_bar, 0, 0, bar_width, 22)

        if rms > 200:
            bar_color = GREEN
        elif rms > 50:
            bar_color = YELLOW
        else:
            bar_color = DIM
        self.level_canvas.itemconfig(self.level_bar, fill=bar_color)
        self.rms_label.config(text=f"RMS: {rms:.0f}")

        # ── Decision Badge ───────────────────────────────────────────
        if gate_state == "decided":
            if decision == "accepted":
                badge_text = f"  ACCEPTED — Owner ({similarity:.2f})  "
                badge_fg = COLOR_ACCEPTED
            else:
                badge_text = f"  REJECTED — Not Owner ({similarity:.2f})  "
                badge_fg = COLOR_REJECTED
        elif gate_state == "accumulating":
            badge_text = f"  ACCUMULATING ({buffered_ms}ms)  "
            badge_fg = COLOR_ACCUMULATING
        elif vad:
            badge_text = "  SPEECH (no gate)  "
            badge_fg = ACCENT
        else:
            badge_text = "  IDLE  "
            badge_fg = COLOR_IDLE

        if not enrolled:
            badge_text = "  NOT ENROLLED  "
            badge_fg = DIM

        self.decision_label.config(text=badge_text, fg=badge_fg)

        # ── Similarity Bar ───────────────────────────────────────────
        sim_width = min(320, int(similarity * 320))
        self.sim_canvas.coords(self.sim_bar, 0, 0, sim_width, 18)

        if similarity >= threshold:
            self.sim_canvas.itemconfig(self.sim_bar, fill=GREEN)
        elif similarity > 0:
            self.sim_canvas.itemconfig(self.sim_bar, fill=RED)
        else:
            self.sim_canvas.itemconfig(self.sim_bar, fill=DIM)

        # Threshold marker
        thresh_x = int(threshold * 320)
        self.sim_canvas.coords(self.threshold_line, thresh_x, 0, thresh_x, 18)

        self.sim_label.config(text=f"{similarity:.2f} / {threshold:.2f}")
        self.thresh_label.config(text=f"Threshold: {threshold:.2f}")

        # ── Info Row ─────────────────────────────────────────────────
        vad_text = "Speech" if vad else "Silence"
        vad_color = GREEN if vad else DIM
        self.vad_label.config(text=f"VAD: {vad_text}", fg=vad_color)
        self.buffer_label.config(text=f"Buffer: {buffered_ms}ms")
        self.state_label.config(text=f"State: {gate_state}")

        # ── Decision Log ─────────────────────────────────────────────
        if gate_state == "decided" and ts > self._last_decision_ts:
            self._last_decision_ts = ts
            time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            tag = "accepted" if decision == "accepted" else "rejected"
            entry = f"  {time_str}  {decision.upper():>8s}  sim={similarity:.2f}  rms={rms:.0f}\n"

            self.log_text.config(state="normal")
            self.log_text.insert("1.0", entry, tag)
            # Keep max 50 entries
            lines = int(self.log_text.index("end-1c").split(".")[0])
            if lines > 50:
                self.log_text.delete("50.0", "end")
            self.log_text.config(state="disabled")

            # Update stats
            if decision == "accepted":
                self.accepted_count += 1
            else:
                self.rejected_count += 1
            self.stats_label.config(
                text=f"Session: {self.accepted_count} accepted, {self.rejected_count} rejected")


def main():
    parser = argparse.ArgumentParser(description="Crowd Control debug visualizer")
    parser.add_argument("--config-dir", type=str, default=None,
                        help="Path to config/runtime directory")
    args = parser.parse_args()

    if args.config_dir:
        config_dir = Path(args.config_dir)
    else:
        config_dir = Path(__file__).resolve().parent.parent / "runtime"

    app = CrowdControlViz(config_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
