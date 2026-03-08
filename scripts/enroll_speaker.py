#!/usr/bin/env python3
"""CLI enrollment script for Crowd Control speaker verification.

Run this in a quiet room to enroll your voice profile.
Usage: python scripts/enroll_speaker.py
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import numpy as np

from open_ears.src.services.speaker_gate import SpeakerGate
from open_ears.src.services.enrollment import EnrollmentSession, ENROLLMENT_PROMPTS, SAMPLE_RATE

# Voice profile is stored in the runtime directory
RUNTIME_DIR = project_root / "runtime"
PROFILE_PATH = RUNTIME_DIR / "speaker_profile.npy"


def main():
    print()
    print("=" * 60)
    print("  CROWD CONTROL — Voice Enrollment")
    print("=" * 60)
    print()
    print("This will record your voice so Molt Speak can identify you")
    print("in noisy environments. Please be in a QUIET room.")
    print()

    if PROFILE_PATH.exists():
        response = input("A voice profile already exists. Overwrite? [y/N] ").strip().lower()
        if response != 'y':
            print("Enrollment cancelled.")
            return

    # Initialize
    gate = SpeakerGate(profile_path=PROFILE_PATH)
    session = EnrollmentSession(gate)

    print(f"You will be asked to say {session.num_phrases} phrases.")
    print("Each recording lasts 4 seconds. Speak naturally.")
    print()
    input("Press Enter when ready...")
    print()

    for i, prompt in enumerate(session.prompts):
        while True:
            print(f"  Phrase {i + 1}/{session.num_phrases}:")
            print(f'  Please say: "{prompt}"')
            print()
            input("  Press Enter to start recording...")
            print("  🎙️  Recording... (4 seconds)")

            audio = session.record_phrase()

            if audio is None:
                print("  ❌ Recording too quiet. Please try again.")
                print()
                continue

            if session.add_recording(audio):
                print("  ✅ Recorded!")
                print()
                break
            else:
                print("  ❌ Recording quality issue. Please try again.")
                print()

    # Finalize
    print("Processing voice profile...")
    if session.finalize():
        print()
        print("=" * 60)
        print("  ✅ Voice profile saved!")
        print()
        print("  Enable 'Crowd Control' in the Molt Speak menu bar")
        print("  to activate speaker verification.")
        print("=" * 60)
        print()
    else:
        print()
        print("❌ Enrollment failed. Please try again.")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
