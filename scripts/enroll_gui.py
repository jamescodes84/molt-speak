#!/usr/bin/env python3
"""Terminal-based enrollment for Crowd Control.

Guides the user through voice enrollment with real-time audio level
display using ANSI escape codes. No tkinter dependency.

Launched from the menu bar (opens in a Terminal window) or CLI:
    python3 scripts/enroll_gui.py --config-dir /path/to/runtime
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger("enroll_gui")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

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

# ── Module loading (avoid open_ears/__init__.py import conflicts) ────────────

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

BAR_WIDTH = 40


def bar(value: float, max_val: float, color: str = GREEN) -> str:
    ratio = min(1.0, value / max_val) if max_val > 0 else 0.0
    filled = int(ratio * BAR_WIDTH)
    empty = BAR_WIDTH - filled
    return f"{color}{'█' * filled}{DIM}{'░' * empty}{RESET}"


def clear():
    sys.stdout.write(CLEAR_SCREEN)
    sys.stdout.flush()


def record_audio(duration: float, label: str = "Recording") -> np.ndarray | None:
    """Record audio for `duration` seconds with a live level meter."""
    import sounddevice as sd

    chunks = []
    current_rms = [0.0]

    def callback(indata, frames, time_info, status):
        chunks.append(indata.copy())
        current_rms[0] = float(np.sqrt(np.mean(indata ** 2)) * 10000)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32",
        callback=callback
    )

    sys.stdout.write(HIDE_CURSOR)
    stream.start()
    start = time.time()

    try:
        while True:
            elapsed = time.time() - start
            remaining = max(0, duration - elapsed)
            if elapsed >= duration:
                break

            rms = current_rms[0]
            if rms > 200:
                color = GREEN
            elif rms > 50:
                color = YELLOW
            else:
                color = DIM

            sys.stdout.write(f"\r  {RED}● {label}{RESET}  {bar(rms, 1000, color)}  {remaining:.0f}s  ")
            sys.stdout.flush()
            time.sleep(0.05)
    finally:
        stream.stop()
        stream.close()
        sys.stdout.write(SHOW_CURSOR + "\n")
        sys.stdout.flush()

    if not chunks:
        return None

    audio = np.concatenate(chunks).flatten()
    rms = float(np.sqrt(np.mean(audio ** 2)) * 10000)

    if rms < 200:
        print(f"  {RED}✗ Too quiet (RMS: {rms:.0f}). Speak louder.{RESET}")
        return None

    return audio


def main():
    parser = argparse.ArgumentParser(description="Voice enrollment for Crowd Control")
    parser.add_argument("--config-dir", required=True,
                        help="Directory containing molt_speak_config.json")
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    profile_path = config_dir / "speaker_profile.npy"

    gate = SpeakerGate(profile_path=profile_path)
    session = EnrollmentSession(gate)

    # ── Welcome ──────────────────────────────────────────────────────────
    clear()
    print(f"{BLUE}{BOLD}╔════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BLUE}{BOLD}║          Crowd Control — Voice Enrollment                 ║{RESET}")
    print(f"{BLUE}{BOLD}╚════════════════════════════════════════════════════════════╝{RESET}")
    print()
    print(f"  Crowd Control learns your unique voice so Molt Speak")
    print(f"  can tell you apart from other people talking nearby.")
    print()
    print(f"  How it works:")
    print(f"    1. You'll read {session.num_phrases} short phrases out loud")
    print(f"    2. Each recording captures your voice signature")
    print(f"    3. The recordings are averaged into a voiceprint")
    print(f"    4. During use, speech is compared to your voiceprint")
    print(f"    5. Only YOUR voice reaches the AI — others are ignored")
    print()
    print(f"  {DIM}This takes about 30 seconds. Find a quiet room")
    print(f"  and speak in your normal voice.{RESET}")
    print()

    resp = input(f"  Press {BOLD}Enter{RESET} to start (or 'q' to cancel): ").strip().lower()
    if resp == 'q':
        print(f"\n  {DIM}Enrollment cancelled.{RESET}")
        return

    # ── Record phrases ───────────────────────────────────────────────────
    for i in range(session.num_phrases):
        prompt = session.prompts[i]

        while True:
            clear()
            # Progress
            dots = ""
            for j in range(session.num_phrases):
                if j < i:
                    dots += f"{GREEN}■ {RESET}"
                elif j == i:
                    dots += f"{BLUE}● {RESET}"
                else:
                    dots += f"{DIM}□ {RESET}"

            print(f"\n  {BOLD}Phrase {i + 1} of {session.num_phrases}{RESET}   {dots}")
            print()
            print(f"  Say this out loud:")
            print(f"  {BOLD}\"{prompt}\"{RESET}")
            print()

            input(f"  Press {BOLD}Enter{RESET} when ready to record...")
            print()

            audio = record_audio(RECORD_DURATION, "Recording")

            if audio is not None and session.add_recording(audio):
                print(f"  {GREEN}✓ Captured!{RESET}")
                time.sleep(0.8)
                break
            else:
                print(f"  {YELLOW}Try again — speak louder and closer to the mic.{RESET}")
                input(f"  Press {BOLD}Enter{RESET} to retry...")

    # ── Finalize ─────────────────────────────────────────────────────────
    clear()
    print(f"\n  {BLUE}{BOLD}Processing...{RESET}")
    print(f"  {DIM}Creating your voiceprint from {session.num_phrases} recordings.{RESET}")
    print()

    success = session.finalize()

    if not success:
        print(f"  {RED}✗ Enrollment failed.{RESET}")
        print(f"  {DIM}Please try again in a quieter room.{RESET}")
        return

    # ── Verification test ────────────────────────────────────────────────
    print(f"  {GREEN}✓ Voiceprint created!{RESET}")
    print()
    print(f"  {BOLD}Verification Test{RESET}")
    print(f"  Say anything for 3 seconds to confirm your voiceprint works.")
    print()

    resp = input(f"  Press {BOLD}Enter{RESET} to verify (or 's' to skip): ").strip().lower()

    similarity = None
    if resp != 's':
        print()
        audio = record_audio(3.0, "Verifying")

        if audio is not None:
            gate.reset()
            is_owner, similarity = gate.verify(audio)
            logger.info("Verification: is_owner=%s, similarity=%.3f", is_owner, similarity)

    # ── Save config ──────────────────────────────────────────────────────
    config_file = config_dir / "molt_speak_config.json"
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
    except Exception as e:
        logger.error("Failed to update config: %s", e)

    # ── Result ───────────────────────────────────────────────────────────
    clear()
    print()

    if similarity is not None and similarity >= gate.threshold:
        print(f"  {GREEN}{BOLD}✓ Voice Profile Saved!{RESET}")
        print(f"  {GREEN}Verification passed — {similarity:.0%} confidence{RESET}")
    elif similarity is not None:
        print(f"  {YELLOW}{BOLD}⚠ Voice Profile Saved{RESET}")
        print(f"  {YELLOW}Verification scored {similarity:.0%} (needs {gate.threshold:.0%}).{RESET}")
        print(f"  {YELLOW}Consider re-enrolling in a quieter room.{RESET}")
    else:
        print(f"  {GREEN}{BOLD}✓ Voice Profile Saved!{RESET}")

    print()
    print(f"  Crowd Control is now active.")
    print(f"  Molt Speak will only respond to your voice.")
    print(f"  Other speakers will be silently ignored.")
    print()
    print(f"  {DIM}Restart the voice loop for changes to take effect.{RESET}")
    print()


if __name__ == "__main__":
    main()
