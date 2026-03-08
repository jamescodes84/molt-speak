"""
Molt-Speak Preflight Checker — exhaustive startup checklist.

Runs before the voice loop starts. If anything fails, the user gets a clear
report of exactly what's wrong and how to fix it. No hieroglyphs.

Usage:
    python3 -m src.diagnostics.preflight              # Standard checks
    python3 -m src.diagnostics.preflight --network     # Include network checks
    python3 -m src.diagnostics.preflight --critical-only --project-root /path  # CI/startup mode
"""

import argparse
import importlib
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Result types ────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    fix: str = ""
    critical: bool = True  # If True, blocks startup

    @property
    def status_icon(self) -> str:
        return "PASS" if self.passed else "FAIL"


@dataclass
class PreflightReport:
    results: list[CheckResult] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def critical_failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.critical]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and not r.critical]

    def has_critical_failure(self) -> bool:
        return len(self.critical_failures) > 0


# ── Preflight Checker ──────────────────────────────────────────────────────

class PreflightChecker:
    """Exhaustive startup checklist for Molt-Speak."""

    def __init__(self, project_root: Path = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent.parent
        self.runtime_dir = self.project_root / "runtime"
        self.logs_dir = self.project_root / "logs"
        self.venv_dir = self.project_root / "venv"

    def run_all(self, include_network: bool = False) -> PreflightReport:
        """Run all preflight checks."""
        start = time.time()
        report = PreflightReport()

        # Critical checks (block startup)
        report.results.append(self._check_python_version())
        report.results.append(self._check_venv())
        report.results.append(self._check_core_imports())
        report.results.append(self._check_sounddevice_import())
        report.results.append(self._check_microphone())
        report.results.append(self._check_audio_output())
        report.results.append(self._check_whisper_import())
        report.results.append(self._check_tts_import())
        report.results.append(self._check_runtime_dir())
        report.results.append(self._check_speech_file())
        report.results.append(self._check_project_files())

        # Non-critical checks (warnings)
        if include_network:
            report.results.append(self._check_network())
        report.results.append(self._check_elevenlabs())
        report.results.append(self._check_disk_space())

        report.duration_ms = (time.time() - start) * 1000
        return report

    def run_critical_only(self) -> PreflightReport:
        """Run only critical checks (for startup gate)."""
        start = time.time()
        report = PreflightReport()

        report.results.append(self._check_python_version())
        report.results.append(self._check_venv())
        report.results.append(self._check_core_imports())
        report.results.append(self._check_sounddevice_import())
        report.results.append(self._check_microphone())
        report.results.append(self._check_audio_output())
        report.results.append(self._check_whisper_import())
        report.results.append(self._check_tts_import())
        report.results.append(self._check_runtime_dir())
        report.results.append(self._check_speech_file())
        report.results.append(self._check_project_files())

        report.duration_ms = (time.time() - start) * 1000
        return report

    # ── Individual checks ──────────────────────────────────────────────────

    def _check_python_version(self) -> CheckResult:
        """Check Python version is 3.10+."""
        v = sys.version_info
        if v.major >= 3 and v.minor >= 10:
            return CheckResult(
                "Python version",
                True,
                f"Python {v.major}.{v.minor}.{v.micro}",
            )
        return CheckResult(
            "Python version",
            False,
            f"Python {v.major}.{v.minor}.{v.micro} (need 3.10+)",
            fix="Install Python 3.10 or newer from https://www.python.org/downloads/",
        )

    def _check_venv(self) -> CheckResult:
        """Check virtual environment exists and is active."""
        if self.venv_dir.exists() and (self.venv_dir / "bin" / "python").exists():
            return CheckResult("Virtual environment", True, f"Found at {self.venv_dir}")
        return CheckResult(
            "Virtual environment",
            False,
            "Virtual environment not found",
            fix="Run: bash install.sh",
        )

    def _check_core_imports(self) -> CheckResult:
        """Check critical Python packages are importable."""
        missing = []
        for pkg in ["rumps", "numpy", "sounddevice"]:
            try:
                importlib.import_module(pkg)
            except ImportError:
                missing.append(pkg)

        if not missing:
            return CheckResult("Core packages", True, "rumps, numpy, sounddevice")
        return CheckResult(
            "Core packages",
            False,
            f"Missing: {', '.join(missing)}",
            fix=f"Run: pip install {' '.join(missing)}",
        )

    def _check_sounddevice_import(self) -> CheckResult:
        """Check sounddevice + portaudio are working."""
        try:
            import sounddevice as sd
            # This triggers PortAudio initialization
            sd.query_devices()
            return CheckResult("Audio system (PortAudio)", True, "PortAudio initialized")
        except OSError as e:
            return CheckResult(
                "Audio system (PortAudio)",
                False,
                f"PortAudio error: {e}",
                fix="Run: brew install portaudio && pip install --force-reinstall sounddevice",
            )
        except ImportError:
            return CheckResult(
                "Audio system (PortAudio)",
                False,
                "sounddevice package not installed",
                fix="Run: brew install portaudio && pip install sounddevice",
            )
        except Exception as e:
            return CheckResult(
                "Audio system (PortAudio)",
                False,
                f"Unexpected error: {e}",
                fix="Run: brew install portaudio && pip install --force-reinstall sounddevice",
            )

    def _check_microphone(self) -> CheckResult:
        """Check that a REAL microphone is connected and can capture audio.

        macOS can list virtual audio devices that pass basic enumeration and
        even allow opening an InputStream — but produce no actual audio data.
        We verify by reading a short buffer and checking it isn't all zeros.
        """
        try:
            import sounddevice as sd
            import numpy as np

            # Step 1: Check default input device exists
            try:
                default_input = sd.default.device[0]
            except Exception:
                default_input = -1

            if default_input is None or default_input < 0:
                return CheckResult(
                    "Microphone",
                    False,
                    "No default input device set",
                    fix="Plug in a microphone or headset. Check System Settings > Sound > Input.",
                )

            devices = sd.query_devices()
            default_name = devices[default_input]['name'] if default_input < len(devices) else "unknown"

            # Step 2: Try to open an input stream and actually read audio
            try:
                # Record a very short burst (0.15s) and check we got real data
                frames = int(16000 * 0.15)  # 2400 frames at 16kHz
                audio = sd.rec(frames, samplerate=16000, channels=1, dtype='int16',
                               device=default_input, blocking=True)

                # If we get here, the device opened and read successfully.
                # Check if we got actual data (not all zeros from a ghost device).
                # A real mic in a quiet room still produces some noise > 0.
                if audio is None or len(audio) == 0:
                    return CheckResult(
                        "Microphone",
                        False,
                        f"Device '{default_name}' returned no audio data",
                        fix="Plug in a microphone or headset. Check System Settings > Sound > Input.",
                    )

                peak = int(np.max(np.abs(audio)))
                if peak == 0:
                    # Every single sample is exactly zero — this is a ghost device
                    return CheckResult(
                        "Microphone",
                        False,
                        f"Device '{default_name}' is listed but not producing audio (all zeros)",
                        fix="Plug in a microphone or headset. The current device may be virtual or disconnected.",
                    )

            except sd.PortAudioError as e:
                err_str = str(e).lower()
                if "permission" in err_str or "not authorized" in err_str:
                    return CheckResult(
                        "Microphone",
                        False,
                        "Microphone permission denied",
                        fix="Open System Settings > Privacy & Security > Microphone and enable access for Terminal.",
                    )
                return CheckResult(
                    "Microphone",
                    False,
                    f"Cannot open microphone '{default_name}': {e}",
                    fix="Check that no other app is using the microphone. Try unplugging and replugging it.",
                )
            except OSError as e:
                return CheckResult(
                    "Microphone",
                    False,
                    f"Microphone found but cannot be opened: {e}",
                    fix="Check that no other app is using the microphone. Try unplugging and replugging it.",
                )

            # Count total input devices for informational message
            input_count = sum(1 for d in devices if d['max_input_channels'] > 0)
            return CheckResult(
                "Microphone",
                True,
                f"{default_name} (verified, {input_count} device{'s' if input_count > 1 else ''} available)",
            )

        except ImportError:
            return CheckResult(
                "Microphone",
                False,
                "sounddevice not installed",
                fix="Run: pip install sounddevice",
            )
        except Exception as e:
            return CheckResult(
                "Microphone",
                False,
                f"Could not check microphone: {e}",
                fix="Check System Settings > Sound > Input. Make sure a microphone is plugged in.",
            )

    def _check_audio_output(self) -> CheckResult:
        """Check that audio output (speakers/headphones) is available."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()

            output_devices = []
            for d in devices:
                if d['max_output_channels'] > 0:
                    output_devices.append(d['name'])

            if not output_devices:
                return CheckResult(
                    "Audio output",
                    False,
                    "No speakers or headphones detected",
                    fix="Connect speakers or headphones. Check System Preferences > Sound > Output.",
                    critical=False,  # Ears can still work without output
                )

            default_output = sd.default.device[1]
            default_name = devices[default_output]['name'] if default_output >= 0 else "unknown"
            return CheckResult(
                "Audio output",
                True,
                f"{default_name} ({len(output_devices)} device{'s' if len(output_devices) > 1 else ''} available)",
            )

        except Exception as e:
            return CheckResult(
                "Audio output",
                False,
                f"Could not check audio output: {e}",
                fix="Check System Preferences > Sound > Output.",
                critical=False,
            )

    def _check_whisper_import(self) -> CheckResult:
        """Check that faster-whisper (speech recognition) is importable."""
        try:
            from faster_whisper import WhisperModel
            return CheckResult("Speech recognition (Whisper)", True, "faster-whisper available")
        except ImportError:
            return CheckResult(
                "Speech recognition (Whisper)",
                False,
                "faster-whisper not installed",
                fix="Run: pip install faster-whisper",
            )
        except Exception as e:
            return CheckResult(
                "Speech recognition (Whisper)",
                False,
                f"Whisper import error: {e}",
                fix="Run: pip install --force-reinstall faster-whisper",
            )

    def _check_tts_import(self) -> CheckResult:
        """Check that text-to-speech engine is importable."""
        try:
            import edge_tts
            return CheckResult("Text-to-speech (Edge-TTS)", True, "edge-tts available")
        except ImportError:
            return CheckResult(
                "Text-to-speech (Edge-TTS)",
                False,
                "edge-tts not installed",
                fix="Run: pip install edge-tts",
            )

    def _check_runtime_dir(self) -> CheckResult:
        """Check runtime directory exists and is writable."""
        try:
            self.runtime_dir.mkdir(exist_ok=True)
            # Test write
            test_file = self.runtime_dir / ".preflight_test"
            test_file.write_text("ok")
            test_file.unlink()
            return CheckResult("Runtime directory", True, str(self.runtime_dir))
        except PermissionError:
            return CheckResult(
                "Runtime directory",
                False,
                f"Cannot write to {self.runtime_dir}",
                fix=f"Fix permissions: chmod 755 {self.runtime_dir}",
            )
        except Exception as e:
            return CheckResult(
                "Runtime directory",
                False,
                f"Runtime directory error: {e}",
                fix=f"Create it manually: mkdir -p {self.runtime_dir}",
            )

    def _check_speech_file(self) -> CheckResult:
        """Check speech output file is writable."""
        speech_file = self.runtime_dir / "speech_output.txt"
        try:
            # Create if doesn't exist
            if not speech_file.exists():
                speech_file.touch()
            # Test write
            with open(speech_file, "a") as f:
                f.write("")
            return CheckResult("Speech output file", True, str(speech_file))
        except PermissionError:
            return CheckResult(
                "Speech output file",
                False,
                f"Cannot write to {speech_file}",
                fix=f"Fix permissions: chmod 666 {speech_file}",
            )
        except Exception as e:
            return CheckResult(
                "Speech output file",
                False,
                f"Speech file error: {e}",
                fix=f"Delete and recreate: rm -f {speech_file} && touch {speech_file} && chmod 666 {speech_file}",
            )

    def _check_project_files(self) -> CheckResult:
        """Check critical project files exist."""
        required = [
            "main.py",
            "open_ears/main.py",
            "open_mouth/main.py",
            "unified_menu_bar.py",
            "AGENT_INSTRUCTIONS.txt",
        ]
        missing = []
        for f in required:
            if not (self.project_root / f).exists():
                missing.append(f)

        if not missing:
            return CheckResult("Project files", True, f"All {len(required)} critical files present")
        return CheckResult(
            "Project files",
            False,
            f"Missing: {', '.join(missing)}",
            fix="Reinstall: rm -rf ~/openclaw-workspace/molt-speak/app && bash install.sh",
        )

    def _check_network(self) -> CheckResult:
        """Check internet connectivity (for cloud TTS)."""
        try:
            import urllib.request
            urllib.request.urlopen("https://speech.platform.bing.com", timeout=5)
            return CheckResult("Network (Edge-TTS)", True, "Connected", critical=False)
        except Exception:
            return CheckResult(
                "Network (Edge-TTS)",
                False,
                "Cannot reach Edge-TTS servers",
                fix="Check your internet connection. Edge-TTS requires internet access.",
                critical=False,
            )

    def _check_elevenlabs(self) -> CheckResult:
        """Check ElevenLabs configuration (non-critical)."""
        try:
            # Check if config has ElevenLabs key
            config_file = self.runtime_dir / "molt_speak_config.json"
            if config_file.exists():
                import json
                config = json.loads(config_file.read_text())
                if config.get("elevenlabs_api_key"):
                    return CheckResult(
                        "ElevenLabs (optional)",
                        True,
                        "API key configured",
                        critical=False,
                    )
            return CheckResult(
                "ElevenLabs (optional)",
                False,
                "Not configured (using free Edge-TTS)",
                fix="Optional: run moltspeak elapi to set up premium voice",
                critical=False,
            )
        except Exception:
            return CheckResult(
                "ElevenLabs (optional)",
                False,
                "Could not check config",
                critical=False,
            )

    def _check_disk_space(self) -> CheckResult:
        """Check available disk space."""
        try:
            stat = os.statvfs(str(self.project_root))
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            if free_gb < 1.0:
                return CheckResult(
                    "Disk space",
                    False,
                    f"Only {free_gb:.1f} GB free",
                    fix="Free up disk space. Whisper models need ~1 GB.",
                    critical=False,
                )
            return CheckResult("Disk space", True, f"{free_gb:.1f} GB free", critical=False)
        except Exception:
            return CheckResult("Disk space", True, "Could not check", critical=False)

    # ── Formatting ─────────────────────────────────────────────────────────

    @staticmethod
    def format_results(report: PreflightReport) -> str:
        """Format results as a human-readable report."""
        lines = []
        lines.append("=" * 56)
        lines.append("  MOLT-SPEAK PREFLIGHT CHECK")
        lines.append("=" * 56)
        lines.append("")

        for r in report.results:
            icon = "[PASS]" if r.passed else "[FAIL]"
            lines.append(f"  {icon}  {r.name}")
            lines.append(f"         {r.message}")
            if not r.passed and r.fix:
                lines.append(f"         Fix: {r.fix}")
            lines.append("")

        lines.append("-" * 56)

        if report.has_critical_failure():
            failures = report.critical_failures
            lines.append(f"  BLOCKED: {len(failures)} critical issue{'s' if len(failures) > 1 else ''} found")
            lines.append("")
            lines.append("  Fix the issues above, then try again:")
            lines.append("    moltspeak start")
        else:
            warnings = report.warnings
            if warnings:
                lines.append(f"  READY (with {len(warnings)} warning{'s' if len(warnings) > 1 else ''})")
            else:
                lines.append("  ALL CHECKS PASSED")

        lines.append(f"  Completed in {report.duration_ms:.0f}ms")
        lines.append("=" * 56)
        return "\n".join(lines)

    # ── Legacy API (used by menu bar) ──────────────────────────────────────

    def has_critical_failure(self, report: PreflightReport) -> bool:
        """Check if report has critical failures. Legacy API for menu bar."""
        return report.has_critical_failure()


# ── CLI entry point ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Molt-Speak Preflight Checker")
    parser.add_argument("--network", action="store_true", help="Include network checks")
    parser.add_argument("--critical-only", action="store_true", help="Only run critical checks")
    parser.add_argument("--project-root", type=str, help="Project root directory")
    args = parser.parse_args()

    project_root = Path(args.project_root) if args.project_root else None
    checker = PreflightChecker(project_root=project_root)

    if args.critical_only:
        report = checker.run_critical_only()
    else:
        report = checker.run_all(include_network=args.network)

    print(PreflightChecker.format_results(report))

    if report.has_critical_failure():
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
