#!/usr/bin/env python3
"""Tkinter enrollment GUI for Crowd Control.

Opens a window that guides the user through voice enrollment with
a real-time audio level visualizer and clear progress feedback.

Launched as a subprocess from the menu bar app.
Usage: python3 scripts/enroll_gui.py --config-dir /path/to/runtime
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import threading
import time
import tkinter as tk
from pathlib import Path

import numpy as np

logger = logging.getLogger("enroll_gui")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ── Module loading (avoid open_ears/__init__.py import conflicts) ──────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name, filepath):
    spec = importlib.util.spec_from_file_location(name, str(filepath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_gate_mod = _load_module("speaker_gate", PROJECT_ROOT / "open_ears" / "src" / "services" / "speaker_gate.py")
_enroll_mod = _load_module("enrollment", PROJECT_ROOT / "open_ears" / "src" / "services" / "enrollment.py")

SpeakerGate = _gate_mod.SpeakerGate
EnrollmentSession = _enroll_mod.EnrollmentSession
SAMPLE_RATE = _enroll_mod.SAMPLE_RATE
RECORD_DURATION = _enroll_mod.RECORD_DURATION

# ── Colors ─────────────────────────────────────────────────────────────────

BG = "#1e1e2e"          # Dark background
FG = "#cdd6f4"          # Light text
ACCENT = "#89b4fa"      # Blue accent
GREEN = "#a6e3a1"       # Success green
RED = "#f38ba8"         # Error red / recording indicator
YELLOW = "#f9e2af"      # Warning yellow
DIM = "#585b70"         # Dimmed text
METER_BG = "#313244"    # Level meter background
METER_FG = "#89b4fa"    # Level meter fill
BTN_BG = "#45475a"      # Button background
BTN_FG = "#cdd6f4"      # Button text


class EnrollmentWindow(tk.Tk):
    """Tkinter enrollment GUI with real-time audio level meter."""

    def __init__(self, config_dir: Path):
        super().__init__()

        self.config_dir = config_dir
        self.profile_path = config_dir / "speaker_profile.npy"

        # Window setup
        self.title("Crowd Control — Voice Enrollment")
        self.geometry("520x480")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._center_window()

        # Enrollment state
        self.gate = SpeakerGate(profile_path=self.profile_path)
        self.session = EnrollmentSession(self.gate)
        self.current_phrase = 0
        self.current_rms = 0.0
        self.audio_chunks = []
        self.stream = None
        self.recording_start = 0.0
        self.is_recording = False

        # Build the main container
        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True, padx=30, pady=20)

        # Start with welcome screen
        self._show_welcome()

        # Bring window to front
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _center_window(self):
        self.update_idletasks()
        w, h = 520, 480
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _clear(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    # ── Welcome Screen ─────────────────────────────────────────────────

    def _show_welcome(self):
        self._clear()

        tk.Label(self.container, text="Voice Enrollment",
                 font=("SF Pro Display", 22, "bold"), fg=FG, bg=BG).pack(pady=(10, 20))

        explanation = (
            "Crowd Control learns your unique voice so Molt Speak\n"
            "can tell you apart from other people talking nearby.\n\n"
            "How it works:\n"
            "  1. You'll read 5 short phrases out loud\n"
            "  2. Each recording captures your voice signature\n"
            "  3. The recordings are averaged into a voiceprint\n"
            "  4. During use, speech is compared to your voiceprint\n"
            "  5. Only YOUR voice reaches the AI — others are ignored\n\n"
            "This takes about 30 seconds. Find a quiet room\n"
            "and speak in your normal voice."
        )
        tk.Label(self.container, text=explanation, font=("SF Pro Text", 13),
                 fg=FG, bg=BG, justify="left").pack(pady=(0, 25))

        btn_frame = tk.Frame(self.container, bg=BG)
        btn_frame.pack()

        tk.Button(btn_frame, text="Cancel", font=("SF Pro Text", 14),
                  fg=FG, bg=BTN_BG, activeforeground=FG, activebackground=DIM,
                  width=10, command=self.destroy).pack(side="left", padx=10)

        tk.Button(btn_frame, text="Start", font=("SF Pro Text", 14, "bold"),
                  fg=BG, bg=ACCENT, activeforeground=BG, activebackground=GREEN,
                  width=10, command=self._show_phrase).pack(side="left", padx=10)

    # ── Phrase Recording Screen ────────────────────────────────────────

    def _show_phrase(self):
        self._clear()
        idx = self.current_phrase
        prompt = self.session.prompts[idx]

        # Header with progress
        tk.Label(self.container,
                 text=f"Phrase {idx + 1} of {self.session.num_phrases}",
                 font=("SF Pro Display", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(pady=(10, 5))

        # Instruction
        tk.Label(self.container, text="Say this out loud:",
                 font=("SF Pro Text", 13), fg=DIM, bg=BG).pack(pady=(5, 5))

        # Phrase text
        phrase_frame = tk.Frame(self.container, bg=METER_BG, padx=15, pady=10)
        phrase_frame.pack(fill="x", pady=(0, 15))
        tk.Label(phrase_frame, text=f'"{prompt}"',
                 font=("SF Pro Text", 15, "bold"), fg=FG, bg=METER_BG,
                 wraplength=420).pack()

        # Level meter canvas
        self.meter_canvas = tk.Canvas(self.container, width=460, height=30,
                                      bg=METER_BG, highlightthickness=0)
        self.meter_canvas.pack(pady=(0, 5))
        self.meter_label = tk.Label(self.container, text="Click Record when ready",
                                    font=("SF Pro Text", 11), fg=DIM, bg=BG)
        self.meter_label.pack()

        # Status
        self.status_label = tk.Label(self.container, text="",
                                     font=("SF Pro Text", 14), fg=FG, bg=BG)
        self.status_label.pack(pady=(10, 5))

        # Progress dots
        self._draw_progress()

        # Buttons
        self.btn_frame = tk.Frame(self.container, bg=BG)
        self.btn_frame.pack(pady=(15, 0))

        self.cancel_btn = tk.Button(self.btn_frame, text="Cancel",
                                    font=("SF Pro Text", 14), fg=FG, bg=BTN_BG,
                                    activeforeground=FG, activebackground=DIM,
                                    width=10, command=self.destroy)
        self.cancel_btn.pack(side="left", padx=10)

        self.action_btn = tk.Button(self.btn_frame, text="Record",
                                    font=("SF Pro Text", 14, "bold"),
                                    fg=BG, bg=RED, activeforeground=BG,
                                    activebackground=YELLOW,
                                    width=10, command=self._start_recording)
        self.action_btn.pack(side="left", padx=10)

    def _draw_progress(self):
        prog_frame = tk.Frame(self.container, bg=BG)
        prog_frame.pack(pady=(5, 0))
        for i in range(self.session.num_phrases):
            color = GREEN if i < self.current_phrase else (
                ACCENT if i == self.current_phrase else DIM)
            symbol = "\u25a0" if i < self.current_phrase else (
                "\u25cf" if i == self.current_phrase else "\u25a1")
            tk.Label(prog_frame, text=symbol, font=("SF Pro Text", 16),
                     fg=color, bg=BG).pack(side="left", padx=4)

    # ── Recording ──────────────────────────────────────────────────────

    def _start_recording(self):
        import sounddevice as sd

        self.is_recording = True
        self.audio_chunks = []
        self.current_rms = 0.0
        self.recording_start = time.time()

        # Update UI
        self.action_btn.config(state="disabled", text="Recording...", bg=DIM)
        self.cancel_btn.config(state="disabled")
        self.status_label.config(text="Speak now!", fg=RED)
        self.meter_label.config(text="Audio Level", fg=FG)

        # Open mic stream with callback for real-time level metering
        def audio_callback(indata, frames, time_info, status):
            self.audio_chunks.append(indata.copy())
            rms = float(np.sqrt(np.mean(indata ** 2)) * 10000)
            self.current_rms = rms

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            callback=audio_callback
        )
        self.stream.start()
        self._update_meter()

    def _update_meter(self):
        if not self.is_recording:
            return

        elapsed = time.time() - self.recording_start
        remaining = max(0, RECORD_DURATION - elapsed)

        # Draw level meter
        self.meter_canvas.delete("all")
        rms = min(self.current_rms, 1000)  # Cap for display
        bar_width = int((rms / 1000) * 460)
        color = GREEN if rms > 200 else (YELLOW if rms > 50 else DIM)
        self.meter_canvas.create_rectangle(0, 0, bar_width, 30, fill=color, outline="")

        # Update countdown
        self.status_label.config(text=f"\u25cf Recording...  {remaining:.0f}s remaining", fg=RED)

        if elapsed < RECORD_DURATION:
            self.after(50, self._update_meter)
        else:
            self._stop_recording()

    def _stop_recording(self):
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Combine audio chunks
        if not self.audio_chunks:
            self._on_recording_result(None)
            return

        audio = np.concatenate(self.audio_chunks).flatten()
        rms = float(np.sqrt(np.mean(audio ** 2)) * 10000)

        if rms < 200:  # MIN_AMPLITUDE
            logger.warning("Recording too quiet (RMS: %.1f)", rms)
            self._on_recording_result(None)
        else:
            self._on_recording_result(audio)

    def _on_recording_result(self, audio):
        self.meter_canvas.delete("all")

        if audio is not None and self.session.add_recording(audio):
            # Success
            self.status_label.config(text="\u2713 Captured!", fg=GREEN)
            self.meter_label.config(text=f"Phrase {self.current_phrase + 1} recorded successfully", fg=GREEN)
            self.meter_canvas.create_rectangle(0, 0, 460, 30, fill=GREEN, outline="")

            self.current_phrase += 1
            self.cancel_btn.config(state="normal")

            if self.current_phrase >= self.session.num_phrases:
                # All phrases recorded — finalize
                self.action_btn.config(state="normal", text="Finish",
                                       bg=GREEN, fg=BG, command=self._finalize)
            else:
                self.action_btn.config(state="normal", text="Next Phrase",
                                       bg=ACCENT, fg=BG, command=self._show_phrase)
        else:
            # Failure
            self.status_label.config(text="\u2717 Too quiet — speak louder", fg=RED)
            self.meter_label.config(text="Recording didn't capture enough audio", fg=YELLOW)
            self.meter_canvas.create_rectangle(0, 0, 100, 30, fill=RED, outline="")

            self.cancel_btn.config(state="normal")
            self.action_btn.config(state="normal", text="Try Again",
                                   bg=RED, fg=BG, command=self._start_recording)

    # ── Finalize ───────────────────────────────────────────────────────

    def _finalize(self):
        self._clear()

        tk.Label(self.container, text="Processing...",
                 font=("SF Pro Display", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(pady=(30, 10))

        self.processing_label = tk.Label(self.container,
            text="Creating your voiceprint from 5 recordings.\n"
                 "This averages your voice embeddings into a unique signature.",
            font=("SF Pro Text", 13), fg=DIM, bg=BG, justify="center")
        self.processing_label.pack(pady=(0, 20))

        # Spinner / progress
        self.progress_label = tk.Label(self.container, text="\u23f3",
                                       font=("SF Pro Text", 28), fg=ACCENT, bg=BG)
        self.progress_label.pack()

        self.update()

        # Run finalization in background thread
        def do_finalize():
            success = self.session.finalize()
            self.after(0, lambda: self._on_finalize_result(success))

        threading.Thread(target=do_finalize, daemon=True).start()

    def _on_finalize_result(self, success):
        if success:
            self._show_verification()
        else:
            self._clear()
            tk.Label(self.container, text="\u2717 Enrollment Failed",
                     font=("SF Pro Display", 18, "bold"), fg=RED, bg=BG
                     ).pack(pady=(40, 15))
            tk.Label(self.container,
                     text="Could not create voice profile.\nPlease try again in a quieter room.",
                     font=("SF Pro Text", 14), fg=FG, bg=BG, justify="center"
                     ).pack(pady=(0, 30))
            tk.Button(self.container, text="Close", font=("SF Pro Text", 14),
                      fg=FG, bg=BTN_BG, width=10, command=self.destroy).pack()

    # ── Verification Test ──────────────────────────────────────────────

    def _show_verification(self):
        self._clear()

        tk.Label(self.container, text="Verification Test",
                 font=("SF Pro Display", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(pady=(10, 10))

        tk.Label(self.container,
                 text="Say anything for 3 seconds to confirm your\n"
                      "voiceprint recognizes you.",
                 font=("SF Pro Text", 13), fg=FG, bg=BG, justify="center"
                 ).pack(pady=(0, 15))

        # Level meter
        self.meter_canvas = tk.Canvas(self.container, width=460, height=30,
                                      bg=METER_BG, highlightthickness=0)
        self.meter_canvas.pack(pady=(0, 5))
        self.meter_label = tk.Label(self.container, text="Click Verify to test",
                                    font=("SF Pro Text", 11), fg=DIM, bg=BG)
        self.meter_label.pack()

        self.status_label = tk.Label(self.container, text="",
                                     font=("SF Pro Text", 14), fg=FG, bg=BG)
        self.status_label.pack(pady=(10, 10))

        self.btn_frame = tk.Frame(self.container, bg=BG)
        self.btn_frame.pack(pady=(15, 0))

        tk.Button(self.btn_frame, text="Skip", font=("SF Pro Text", 14),
                  fg=FG, bg=BTN_BG, width=10,
                  command=lambda: self._show_complete(None)).pack(side="left", padx=10)

        self.action_btn = tk.Button(self.btn_frame, text="Verify",
                                    font=("SF Pro Text", 14, "bold"),
                                    fg=BG, bg=ACCENT, width=10,
                                    command=self._start_verification)
        self.action_btn.pack(side="left", padx=10)

    def _start_verification(self):
        import sounddevice as sd

        self.is_recording = True
        self.audio_chunks = []
        self.current_rms = 0.0
        self.recording_start = time.time()

        self.action_btn.config(state="disabled", text="Listening...", bg=DIM)
        self.status_label.config(text="Speak now!", fg=ACCENT)
        self.meter_label.config(text="Audio Level", fg=FG)

        def audio_callback(indata, frames, time_info, status):
            self.audio_chunks.append(indata.copy())
            self.current_rms = float(np.sqrt(np.mean(indata ** 2)) * 10000)

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            callback=audio_callback
        )
        self.stream.start()
        self._update_verify_meter()

    def _update_verify_meter(self):
        if not self.is_recording:
            return

        elapsed = time.time() - self.recording_start
        remaining = max(0, 3.0 - elapsed)

        self.meter_canvas.delete("all")
        rms = min(self.current_rms, 1000)
        bar_width = int((rms / 1000) * 460)
        color = GREEN if rms > 200 else (YELLOW if rms > 50 else DIM)
        self.meter_canvas.create_rectangle(0, 0, bar_width, 30, fill=color, outline="")

        self.status_label.config(text=f"Listening...  {remaining:.0f}s remaining", fg=ACCENT)

        if elapsed < 3.0:
            self.after(50, self._update_verify_meter)
        else:
            self.is_recording = False
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            if self.audio_chunks:
                audio = np.concatenate(self.audio_chunks).flatten()
                self.gate.reset()
                is_owner, similarity = self.gate.verify(audio)
                logger.info("Verification: is_owner=%s, similarity=%.3f", is_owner, similarity)
                self._show_complete(similarity)
            else:
                self._show_complete(None)

    # ── Complete Screen ────────────────────────────────────────────────

    def _show_complete(self, similarity):
        self._clear()

        # Update config
        self._save_config()

        if similarity is not None and similarity >= self.gate.threshold:
            tk.Label(self.container, text="\u2713 Voice Profile Saved!",
                     font=("SF Pro Display", 22, "bold"), fg=GREEN, bg=BG
                     ).pack(pady=(30, 15))

            tk.Label(self.container,
                     text=f"Verification passed — {similarity:.0%} confidence",
                     font=("SF Pro Text", 15), fg=GREEN, bg=BG).pack(pady=(0, 15))
        elif similarity is not None:
            tk.Label(self.container, text="\u26a0 Voice Profile Saved",
                     font=("SF Pro Display", 22, "bold"), fg=YELLOW, bg=BG
                     ).pack(pady=(30, 15))

            tk.Label(self.container,
                     text=f"Verification scored {similarity:.0%} (needs {self.gate.threshold:.0%}).\n"
                          "Consider re-enrolling in a quieter room.",
                     font=("SF Pro Text", 14), fg=YELLOW, bg=BG, justify="center"
                     ).pack(pady=(0, 15))
        else:
            tk.Label(self.container, text="\u2713 Voice Profile Saved!",
                     font=("SF Pro Display", 22, "bold"), fg=GREEN, bg=BG
                     ).pack(pady=(30, 15))

        tk.Label(self.container,
                 text="Crowd Control is now active.\n"
                      "Molt Speak will only respond to your voice.\n\n"
                      "Other speakers will be silently ignored —\n"
                      "no transcription, no blue icon, no agent response.",
                 font=("SF Pro Text", 13), fg=FG, bg=BG, justify="center"
                 ).pack(pady=(0, 25))

        tk.Button(self.container, text="Done", font=("SF Pro Text", 14, "bold"),
                  fg=BG, bg=GREEN, activeforeground=BG, activebackground=ACCENT,
                  width=12, command=self.destroy).pack()

    def _save_config(self):
        """Update molt_speak_config.json to enable crowd control."""
        config_file = self.config_dir / "molt_speak_config.json"
        try:
            import json
            if config_file.exists():
                with open(config_file, "r") as f:
                    config = json.load(f)
            else:
                config = {}
            config["crowd_control_enabled"] = True
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            logger.info("Config updated: crowd_control_enabled = True")
        except Exception as e:
            logger.error("Failed to update config: %s", e)

    def destroy(self):
        """Clean up audio resources before closing."""
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        super().destroy()


def main():
    parser = argparse.ArgumentParser(description="Voice enrollment for Crowd Control")
    parser.add_argument("--config-dir", required=True,
                        help="Directory containing molt_speak_config.json")
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)

    app = EnrollmentWindow(config_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
