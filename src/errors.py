"""
Molt-Speak Error Registry — centralized error definitions with user-friendly messages.

Every error follows the pattern: WHAT happened + WHY + WHAT TO DO.
Raw exceptions go to log files only; users see plain English.
"""

import re
import time
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    FATAL = "fatal"          # User must fix — app cannot continue
    TRANSIENT = "transient"  # Auto-retry — usually resolves itself
    DEGRADED = "degraded"    # Reduced capability — app continues


@dataclass(frozen=True)
class MoltError:
    code: str
    user_message: str
    fix: str
    severity: Severity
    restartable: bool
    alert_title: str

    def log_message(self, exc: Exception = None) -> str:
        """Structured log line: registry message + raw exception for debugging."""
        detail = f" | Detail: {type(exc).__name__}: {exc}" if exc else ""
        return f"[{self.code}] {self.user_message}{detail}"

    def to_crash_dict(self, component: str, exit_code: int) -> dict:
        """Build the crash JSON dict consumed by the menu bar."""
        return {
            "component": component,
            "message": self.user_message,
            "fix": self.fix,
            "exit_code": exit_code,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "restartable": self.restartable,
            "error_code": self.code,
        }


# ── Registry ────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, MoltError] = {}


def _reg(code, user_message, fix, severity, restartable=True, alert_title=None):
    """Register an error definition."""
    err = MoltError(
        code=code,
        user_message=user_message,
        fix=fix,
        severity=severity,
        restartable=restartable,
        alert_title=alert_title or code.replace("_", " ").title(),
    )
    _REGISTRY[code] = err


# ── Microphone / Audio Input ────────────────────────────────────────────────

_reg(
    "MIC_NOT_FOUND",
    "No microphone detected.",
    "Plug in a microphone or check System Preferences > Sound > Input.",
    Severity.FATAL,
    restartable=False,
)

_reg(
    "MIC_PERMISSION_DENIED",
    "Microphone access is not allowed.",
    "Open System Preferences > Security & Privacy > Microphone and enable access.",
    Severity.FATAL,
    restartable=False,
)

_reg(
    "MIC_STREAM_WARNING",
    "Audio stream hiccup detected.",
    "This usually resolves on its own. If audio cuts out, restart the voice loop.",
    Severity.TRANSIENT,
)

# ── Whisper / Transcription ─────────────────────────────────────────────────

_reg(
    "WHISPER_MODEL_LOAD_FAILED",
    "Speech recognition model failed to load.",
    "Check that you have enough disk space and memory. Try: moltspeak kill && moltspeak start",
    Severity.FATAL,
    restartable=False,
)

_reg(
    "TRANSCRIPTION_FAILED",
    "Could not understand what was said.",
    "Try speaking again. If this keeps happening, check your microphone connection.",
    Severity.TRANSIENT,
)

# ── VAD ─────────────────────────────────────────────────────────────────────

_reg(
    "VAD_LOAD_FAILED",
    "Advanced voice detection unavailable — using basic detection instead.",
    "This is normal on first run. Speech recognition still works.",
    Severity.DEGRADED,
)

# ── TTS / Speech Output ────────────────────────────────────────────────────

_reg(
    "EDGE_TTS_NOT_INSTALLED",
    "Text-to-speech engine is not installed.",
    "Run: pip install edge-tts",
    Severity.FATAL,
    restartable=False,
)

_reg(
    "TTS_SYNTHESIS_FAILED",
    "Voice output failed.",
    "The text-to-speech engine encountered an error. It will retry automatically.",
    Severity.TRANSIENT,
)

_reg(
    "TTS_PLAYBACK_FAILED",
    "Could not play audio.",
    "Check that your speakers or headphones are connected and volume is up.",
    Severity.TRANSIENT,
)

_reg(
    "TTS_PIPELINE_ERROR",
    "Voice output pipeline encountered an error.",
    "The system will attempt to recover automatically.",
    Severity.TRANSIENT,
)

_reg(
    "TTS_ALL_VOICES_FAILED",
    "No text-to-speech voices are available.",
    "Check your internet connection. If using ElevenLabs, verify your API key with: moltspeak elapi",
    Severity.FATAL,
    restartable=True,
    alert_title="No Voices Available",
)

_reg(
    "TTS_VOICE_TEST_FAILED",
    "The selected voice could not be verified.",
    "Trying a different voice. If this persists, check your internet connection.",
    Severity.DEGRADED,
    alert_title="Voice Test Failed",
)

_reg(
    "TTS_VOICE_CHANGE_FAILED",
    "Could not switch to the new voice.",
    "The previous voice is still active. Try selecting a different voice.",
    Severity.DEGRADED,
    alert_title="Voice Change Failed",
)

_reg(
    "TTS_DIRECT_SPEECH_FAILED",
    "Local speech output failed.",
    "The system voice encountered an error. Try restarting the voice loop.",
    Severity.TRANSIENT,
)

# ── ElevenLabs ──────────────────────────────────────────────────────────────

_reg(
    "ELEVENLABS_KEY_MISSING",
    "ElevenLabs API key is not configured.",
    "Run: moltspeak elapi  — falling back to free Edge-TTS voice.",
    Severity.DEGRADED,
    alert_title="ElevenLabs Not Configured",
)

_reg(
    "ELEVENLABS_INIT_FAILED",
    "Could not connect to ElevenLabs.",
    "Your API key may be expired or invalid. Run: moltspeak elapi  — falling back to Edge-TTS.",
    Severity.DEGRADED,
    alert_title="ElevenLabs Unavailable",
)

_reg(
    "ELEVENLABS_SYNTHESIS_FAILED",
    "ElevenLabs voice output failed.",
    "Falling back to free Edge-TTS voice. Check your API key or internet connection.",
    Severity.DEGRADED,
)

# ── AppleScript / TUI Delivery ──────────────────────────────────────────────

_reg(
    "APPLESCRIPT_COMPILE_FAILED",
    "Text delivery script could not be prepared.",
    "This is usually a temporary issue. Text delivery will retry.",
    Severity.TRANSIENT,
)

_reg(
    "TUI_DELIVERY_FAILED",
    "Could not deliver text to the terminal.",
    "Make sure the OpenClaw TUI window is open and focused.",
    Severity.TRANSIENT,
)

_reg(
    "TUI_DELIVERY_TIMEOUT",
    "Text delivery to the terminal timed out.",
    "The terminal may be busy. Try speaking again.",
    Severity.TRANSIENT,
)

_reg(
    "TUI_ALL_METHODS_FAILED",
    "Cannot type into the terminal — all delivery methods failed.",
    "Restart the OpenClaw TUI and try again. Make sure it has accessibility permissions.",
    Severity.FATAL,
    restartable=True,
    alert_title="Text Delivery Failed",
)

_reg(
    "TUI_TYPING_FAILED",
    "Error while typing text into the terminal.",
    "Make sure the OpenClaw TUI window is open. Try speaking again.",
    Severity.TRANSIENT,
)

_reg(
    "AGENT_CANCEL_FAILED",
    "Could not cancel the agent's current response.",
    "This is usually harmless — the agent will finish its current response.",
    Severity.TRANSIENT,
)

# ── Background / IO ────────────────────────────────────────────────────────

_reg(
    "BACKGROUND_IO_ERROR",
    "A background file operation failed.",
    "This is usually harmless and will not affect voice functionality.",
    Severity.TRANSIENT,
)

# ── Supervisor / System ─────────────────────────────────────────────────────

_reg(
    "SYSTEM_TOTAL_FAILURE",
    "The voice system has stopped completely.",
    "Try: moltspeak kill && moltspeak start",
    Severity.FATAL,
    restartable=False,
    alert_title="Voice System Down",
)

_reg(
    "SUPERVISOR_ERROR",
    "The voice system encountered an unexpected error.",
    "Try restarting: moltspeak kill && moltspeak start",
    Severity.FATAL,
    restartable=True,
)

_reg(
    "COMPONENT_RESTART_FAILED",
    "A voice component could not restart after crashing.",
    "Try: moltspeak kill && moltspeak start",
    Severity.FATAL,
    restartable=True,
)

# ── Menu Bar / Settings ─────────────────────────────────────────────────────

_reg(
    "SETTINGS_SAVE_FAILED",
    "Could not save your setting.",
    "Please try again. If this persists, restart the app.",
    Severity.TRANSIENT,
    alert_title="Setting Not Saved",
)

_reg(
    "VOICE_LOOP_START_FAILED",
    "The voice loop could not start.",
    "Check the logs for details: moltspeak logs audio",
    Severity.FATAL,
    restartable=True,
    alert_title="Voice Loop Failed",
)

_reg(
    "VOICE_LOOP_STOP_FAILED",
    "The voice loop could not be stopped cleanly.",
    "Try: moltspeak kill",
    Severity.TRANSIENT,
    alert_title="Stop Failed",
)

_reg(
    "COMPONENT_START_FAILED",
    "A voice component could not start.",
    "Check the logs for details: moltspeak logs audio",
    Severity.FATAL,
    restartable=True,
)

_reg(
    "COMPONENT_STOP_FAILED",
    "A voice component could not be stopped.",
    "Try: moltspeak kill",
    Severity.TRANSIENT,
)

# ── Catch-all ───────────────────────────────────────────────────────────────

_reg(
    "UNKNOWN",
    "Something went wrong.",
    "Try restarting: moltspeak kill && moltspeak start  — check logs for details.",
    Severity.TRANSIENT,
)


# ── Public API ──────────────────────────────────────────────────────────────

def lookup_error(code: str) -> MoltError:
    """Look up an error by code. Returns UNKNOWN if not found."""
    return _REGISTRY.get(code, _REGISTRY["UNKNOWN"])


# Pattern → error code mapping for crash log analysis
_CRASH_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"permission denied|not authorized", re.I), "MIC_PERMISSION_DENIED"),
    (re.compile(r"no (audio|input) device|no microphone|could not find.*mic", re.I), "MIC_NOT_FOUND"),
    (re.compile(r"(faster.?whisper|whisper).*load|model.*load.*fail|cannot.*model", re.I), "WHISPER_MODEL_LOAD_FAILED"),
    (re.compile(r"edge.?tts.*not installed|no module.*edge_tts", re.I), "EDGE_TTS_NOT_INSTALLED"),
    (re.compile(r"elevenlabs.*key|api.?key.*missing|api.?key.*invalid", re.I), "ELEVENLABS_KEY_MISSING"),
    (re.compile(r"elevenlabs.*(fail|error|exception)", re.I), "ELEVENLABS_SYNTHESIS_FAILED"),
    (re.compile(r"tts.*synth.*(fail|error)|synthesis.*fail", re.I), "TTS_SYNTHESIS_FAILED"),
    (re.compile(r"all voices unavailable|no.*voices.*available", re.I), "TTS_ALL_VOICES_FAILED"),
    (re.compile(r"voice test failed", re.I), "TTS_VOICE_TEST_FAILED"),
    (re.compile(r"applescript.*(fail|error|timeout)", re.I), "TUI_DELIVERY_FAILED"),
    (re.compile(r"transcription.*(error|fail)", re.I), "TRANSCRIPTION_FAILED"),
]


def classify_crash(component: str, exit_code: int, log_tail: str) -> MoltError:
    """Pattern-match log text to a known error. Falls back to UNKNOWN."""
    for pattern, code in _CRASH_PATTERNS:
        if pattern.search(log_tail):
            return lookup_error(code)

    # Signal-based classification
    if exit_code == -9 or exit_code == 137:
        return MoltError(
            code="KILLED_BY_SIGNAL",
            user_message=f"{component.capitalize()} was terminated by the system.",
            fix="This may happen if the system is low on memory. Try restarting.",
            severity=Severity.TRANSIENT,
            restartable=True,
            alert_title=f"{component.capitalize()} Terminated",
        )

    return lookup_error("UNKNOWN")
