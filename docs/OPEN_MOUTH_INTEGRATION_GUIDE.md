# OpenClaw Mouth - Integration Guide for Open Ears
## Complete Technical Documentation for Integration

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Communication Mechanisms](#core-communication-mechanisms)
4. [Speaking Signal Protocol](#speaking-signal-protocol)
5. [Integration Patterns](#integration-patterns)
6. [Runtime Control](#runtime-control)
7. [File Locations & Data Flow](#file-locations--data-flow)
8. [Configuration](#configuration)
9. [Testing & Validation](#testing--validation)
10. [Troubleshooting](#troubleshooting)
11. [Code Examples](#code-examples)

---

## System Overview

**OpenClaw Mouth** is a text-to-speech (TTS) output system designed as the companion to OpenClaw Ears (voice input). It provides real-time speech synthesis for AI agents with minimal latency and zero code changes required.

### Key Design Principles

1. **File-based Communication**: Agents write text to a monitored file
2. **Zero-configuration**: Works out of the box with sensible defaults
3. **Terminal-embedded Visualization**: Status display runs in terminal, not separate windows
4. **Speaking Signal**: Automatic coordination with OpenClaw Ears to prevent echo
5. **Independent Operation**: Can run standalone or alongside other systems
6. **Runtime Control**: Voice and settings changeable without restart

### The Complete Voice Loop

```
User speaks → OpenClaw Ears → Agent TUI → Agent processes → OpenClaw Mouth → Speaker
                    ↑                                                    ↓
                    └────────── [Speaking Signal Prevents Echo] ─────────┘
```

---

## Architecture

### System Components

```
┌───────────────────────────────────────────────────────────────────┐
│                      OpenClaw Mouth System                         │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────┐        ┌──────────────────┐                │
│  │  Input Monitor  │───────>│  Text Queue      │                │
│  │  (Watchdog)     │        │  (Thread-safe)   │                │
│  └─────────────────┘        └──────────────────┘                │
│          │                           │                            │
│          │ Detects new lines         │ FIFO processing           │
│          ▼                           ▼                            │
│  ~/.openclaw/              ┌──────────────────┐                  │
│  speech_output.txt         │  TTS Synthesis   │                  │
│                            │  (Edge-TTS/Local)│                  │
│                            └──────────────────┘                  │
│                                     │                             │
│                                     │ Audio data                  │
│                                     ▼                             │
│                            ┌──────────────────┐                  │
│                            │  Audio Player    │                  │
│                            │  (afplay/local)  │                  │
│                            └──────────────────┘                  │
│                                     │                             │
│                                     │ Speaking events             │
│                                     ▼                             │
│                            ┌──────────────────┐                  │
│                            │ Speaking Signal  │                  │
│                            │   (Notifier)     │                  │
│                            └──────────────────┘                  │
│                                     │                             │
│                                     ▼                             │
│                            ~/.openclaw/                           │
│                            mouth_status.txt                       │
│                                                                   │
│  ┌─────────────────────────────────────────────────────┐        │
│  │          Control Server (Optional)                   │        │
│  │  Unix Socket: ~/.openclaw/mouth_control.sock        │        │
│  │  - Runtime voice changes                             │        │
│  │  - Status queries                                    │        │
│  │  - Rate/volume adjustments                           │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Threading Model

OpenClaw Mouth uses **4 concurrent threads**:

1. **Text Monitor Thread**: Watches input file for changes (watchdog library)
2. **Synthesis Worker Thread**: Converts queued text to audio
3. **Audio Playback Thread**: Plays synthesized audio through speakers
4. **Display Update Thread**: Refreshes terminal UI at 20Hz
5. **Control Server Thread** (optional): Handles runtime control commands

All threads are coordinated via thread-safe queues and state management.

---

## Core Communication Mechanisms

### 1. Text Input (Agent → Mouth)

**Primary Interface**: File-based append operations

**File Location**: `~/.openclaw/speech_output.txt`

**Protocol**:
- Each line = one utterance
- Append-only (use `>>` not `>`)
- Newlines separate utterances
- Empty lines ignored
- UTF-8 encoding

**Example**:
```bash
# Bash
echo "Hello user!" >> ~/.openclaw/speech_output.txt

# Python
with open(os.path.expanduser("~/.openclaw/speech_output.txt"), "a") as f:
    f.write("Hello user!\n")
```

**Detection Mechanism**:
- Uses `watchdog` library for file system events
- Sub-100ms detection latency
- Atomic read operations
- Position tracking to avoid re-reading

### 2. Speaking Signal (Mouth → Ears)

**Critical for Integration**: This prevents OpenClaw Ears from hearing the agent's own voice.

**File Location**: `~/.openclaw/mouth_status.txt`

**Format**: Pipe-delimited single line
```
<timestamp>|<status>|<details>
```

**Status Values**:
- `IDLE`: Not speaking, safe to listen
- `SPEAKING`: Currently outputting audio - **PAUSE LISTENING**
- `QUEUED`: Speech queued but not yet playing
- `ERROR`: System error occurred

**Example Status Lines**:
```
2026-02-01T12:15:22.152594|IDLE|
2026-02-01T12:15:24.161586|SPEAKING|Hello, this is a test message
2026-02-01T12:15:25.167795|IDLE|
```

**Update Timing**:
- Updated immediately on state change
- Atomic writes (no partial reads)
- File deleted on clean shutdown

### 3. Control Socket (External → Mouth)

**Location**: `~/.openclaw/mouth_control.sock` (Unix domain socket)

**Enabled by**: `--enable-control` flag

**Commands**:
```
PING                           → OK:PONG
GET_STATUS                     → OK:IDLE|VoiceName|mode|
CHANGE_VOICE:VoiceName[,mode]  → OK:Voice changed to VoiceName
CHANGE_RATE:1.2                → OK:Rate changed to 1.2
CHANGE_VOLUME:0.8              → OK:Volume changed to 0.8
```

**Used by**: Menu bar app for runtime voice control

---

## Speaking Signal Protocol

### Integration Requirements for OpenClaw Ears

OpenClaw Ears **MUST** monitor the speaking signal to avoid echo. Here's how:

#### Polling Approach (Simple)

```python
from pathlib import Path
import time

def is_agent_speaking() -> bool:
    """
    Check if OpenClaw Mouth is currently speaking.
    Returns True if agent is speaking, False otherwise.
    """
    status_file = Path.home() / ".openclaw" / "mouth_status.txt"

    # If file doesn't exist, Mouth is not running
    if not status_file.exists():
        return False

    try:
        content = status_file.read_text().strip()
        parts = content.split("|")

        if len(parts) >= 2:
            status = parts[1]
            return status == "SPEAKING"
    except Exception as e:
        # On error, assume not speaking (safe default)
        return False

    return False

# In your listening loop
while running:
    if is_agent_speaking():
        # PAUSE microphone input
        pause_microphone()
        time.sleep(0.1)  # Check again in 100ms
    else:
        # RESUME normal listening
        process_audio_input()
```

#### File Watching Approach (Efficient)

```python
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class MouthStatusMonitor(FileSystemEventHandler):
    """
    Monitor speaking signal file for real-time updates.
    More efficient than polling - uses OS file system events.
    """

    def __init__(self, on_status_change):
        self.status_file = Path.home() / ".openclaw" / "mouth_status.txt"
        self.on_status_change = on_status_change
        self.last_status = None

    def on_modified(self, event):
        if Path(event.src_path) == self.status_file:
            self._check_status()

    def on_created(self, event):
        if Path(event.src_path) == self.status_file:
            self._check_status()

    def _check_status(self):
        try:
            content = self.status_file.read_text().strip()
            parts = content.split("|")

            if len(parts) >= 2:
                status = parts[1]

                if status != self.last_status:
                    self.last_status = status
                    is_speaking = (status == "SPEAKING")
                    self.on_status_change(is_speaking)
        except Exception:
            pass

# Usage
def on_speaking_state_change(is_speaking: bool):
    if is_speaking:
        print("🔊 Agent started speaking - PAUSING microphone")
        pause_microphone()
    else:
        print("✅ Agent stopped speaking - RESUMING microphone")
        resume_microphone()

# Setup file watcher
monitor = MouthStatusMonitor(on_speaking_state_change)
observer = Observer()
observer.schedule(monitor, str(Path.home() / ".openclaw"), recursive=False)
observer.start()
```

#### Debouncing (Recommended)

Avoid rapid pause/resume cycles:

```python
import time

class SpeakingDebouncer:
    """
    Debounce speaking signal to avoid rapid microphone toggling.
    Keeps microphone paused for a short period after speaking stops.
    """

    def __init__(self, debounce_ms: int = 150):
        self.debounce_ms = debounce_ms
        self.last_speaking_time = 0
        self.last_idle_time = 0

    def should_pause_listening(self, current_status: str) -> bool:
        now = time.time() * 1000  # Convert to milliseconds

        if current_status == "SPEAKING":
            self.last_speaking_time = now
            return True
        else:
            self.last_idle_time = now
            # Keep paused for debounce_ms after speaking stops
            time_since_speaking = now - self.last_speaking_time
            return time_since_speaking < self.debounce_ms
```

### Visual Indicators

When speaking, OpenClaw Mouth shows prominent visual cues:

**Full Display**:
- Green double-line border (`═` instead of `─`)
- Banner: "🔊 AGENT SPEAKING - EARS SHOULD PAUSE 🔊"
- Green status icon

**Compact Display**:
- Bold: "🔊 AGENT SPEAKING" prefix
- Green highlighting

---

## Integration Patterns

### Pattern 1: Minimal Integration (File Write Only)

**Best for**: Quick prototypes, simple agents

```python
import os
from pathlib import Path

SPEECH_FILE = Path.home() / ".openclaw" / "speech_output.txt"

def speak(text: str):
    """Minimal integration - just append to file."""
    with open(SPEECH_FILE, "a") as f:
        f.write(f"{text}\n")

# Usage
speak("Hello user!")
speak("How can I help you today?")
```

### Pattern 2: Production Integration (With Error Handling)

**Best for**: Production agents, robust systems

```python
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class MouthClient:
    """
    Robust client for OpenClaw Mouth integration.
    Handles errors, validates input, ensures file exists.
    """

    def __init__(self, speech_file: Optional[Path] = None):
        self.speech_file = speech_file or (Path.home() / ".openclaw" / "speech_output.txt")
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure speech file and directory exist."""
        try:
            self.speech_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.speech_file.exists():
                self.speech_file.touch()
        except Exception as e:
            logger.error(f"Failed to initialize speech file: {e}")

    def speak(self, text: str) -> bool:
        """
        Send text to OpenClaw Mouth for synthesis.

        Args:
            text: Text to speak (will be stripped and validated)

        Returns:
            True if successful, False otherwise
        """
        if not text or not text.strip():
            logger.warning("Attempted to speak empty text")
            return False

        text = text.strip()

        try:
            with open(self.speech_file, "a", encoding="utf-8") as f:
                f.write(f"{text}\n")
                f.flush()  # Ensure immediate write

            logger.debug(f"Sent to mouth: {text[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to write to speech file: {e}")
            return False

    def speak_multiple(self, texts: list[str]) -> int:
        """
        Send multiple utterances at once.

        Returns:
            Number of successfully queued utterances
        """
        count = 0
        for text in texts:
            if self.speak(text):
                count += 1
        return count

# Usage
mouth = MouthClient()
mouth.speak("Hello!")
mouth.speak("I'm ready to help you.")
```

### Pattern 3: Full Integration (With Speaking Signal)

**Best for**: Integration with OpenClaw Ears

```python
from pathlib import Path
from typing import Callable, Optional
import time
import threading

class VoiceCoordinator:
    """
    Coordinates OpenClaw Mouth and Ears.
    Automatically pauses listening when agent speaks.
    """

    def __init__(self,
                 on_pause_listening: Callable[[], None],
                 on_resume_listening: Callable[[], None]):
        self.speech_file = Path.home() / ".openclaw" / "speech_output.txt"
        self.status_file = Path.home() / ".openclaw" / "mouth_status.txt"

        self.on_pause = on_pause_listening
        self.on_resume = on_resume_listening

        self.is_listening_paused = False
        self.monitor_thread = None
        self.running = False

    def start_monitoring(self):
        """Start monitoring speaking signal."""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop monitoring speaking signal."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)

    def _monitor_loop(self):
        """Monitor speaking signal file."""
        while self.running:
            is_speaking = self._check_speaking()

            if is_speaking and not self.is_listening_paused:
                # Agent started speaking - pause listening
                self.is_listening_paused = True
                self.on_pause()
            elif not is_speaking and self.is_listening_paused:
                # Agent stopped speaking - resume listening
                self.is_listening_paused = False
                self.on_resume()

            time.sleep(0.1)  # Check every 100ms

    def _check_speaking(self) -> bool:
        """Check if agent is currently speaking."""
        if not self.status_file.exists():
            return False

        try:
            content = self.status_file.read_text().strip()
            parts = content.split("|")
            return len(parts) >= 2 and parts[1] == "SPEAKING"
        except:
            return False

    def speak(self, text: str) -> bool:
        """Send text to be spoken."""
        try:
            with open(self.speech_file, "a", encoding="utf-8") as f:
                f.write(f"{text}\n")
            return True
        except:
            return False

# Usage in your agent
coordinator = VoiceCoordinator(
    on_pause_listening=lambda: print("Pausing mic..."),
    on_resume_listening=lambda: print("Resuming mic...")
)
coordinator.start_monitoring()

# Speak something
coordinator.speak("Hello! I'm thinking about your question.")
```

---

## Runtime Control

### Menu Bar Application (macOS)

OpenClaw Mouth includes a native macOS menu bar app for runtime voice control.

**Features**:
- Change voice without restarting
- Switch between local (macOS) and cloud (Edge-TTS) voices
- Mark favorite voices
- See real-time speaking status

**Starting with Control Enabled**:
```bash
# Terminal 1: Start mouth with control server
./start_speech_system.sh --enable-control --local

# Terminal 2: Launch menu bar app
python scripts/launch_menu_bar.py
```

**Menu bar icon states**:
- 🎙️ - Idle
- 🎙️ 🔊 - Speaking
- 🎙️ ⚠️ - Not connected

### Voice Options

**Local voices** (instant, no network):
- Alex (male)
- Samantha (female)
- Victoria (female)
- Thomas (male)
- Many more (run `say -v "?"` to list)

**Cloud voices** (high quality, requires internet):
- en-US-ChristopherNeural (male, default)
- en-US-AriaNeural (female)
- en-US-JennyNeural (female)
- en-US-GuyNeural (male)
- 100+ more voices available

**Switching voices**:
```bash
# Via command line
./start_speech_system.sh --voice en-US-AriaNeural

# Via menu bar (when --enable-control is on)
Click menu bar icon → Select voice

# Via control socket
echo "CHANGE_VOICE:Samantha,local" | nc -U ~/.openclaw/mouth_control.sock
```

---

## File Locations & Data Flow

### Critical Files

| File | Purpose | Format | Created By |
|------|---------|--------|------------|
| `~/.openclaw/speech_output.txt` | Input: Text to speak | Text, one line per utterance | Agent/User |
| `~/.openclaw/mouth_status.txt` | Output: Speaking signal | `timestamp\|status\|details` | OpenClaw Mouth |
| `~/.openclaw/mouth_control.sock` | Control: Runtime commands | Unix socket | OpenClaw Mouth (with --enable-control) |
| `~/.openclaw/voice_preferences.json` | Config: Voice settings | JSON | Menu bar app |
| `~/.openclaw/voice_cache.json` | Cache: Available voices | JSON | Menu bar app |

### Data Flow Diagram

```
┌──────────────┐
│    Agent     │
│              │
└──────┬───────┘
       │ writes text
       ▼
~/.openclaw/speech_output.txt  (INPUT)
       │
       │ monitored by
       ▼
┌──────────────┐
│  Mouth       │──────┐
│  Pipeline    │      │
└──────┬───────┘      │
       │              │ updates status
       │ audio        ▼
       │         ~/.openclaw/mouth_status.txt  (SIGNAL)
       ▼              │
┌──────────────┐      │
│   Speakers   │      │ monitored by
└──────────────┘      ▼
                 ┌──────────────┐
                 │  Ears        │
                 │  (pauses)    │
                 └──────────────┘
```

---

## Configuration

### Environment Variables

Create `.env` file in project root:

```bash
# Voice Configuration
TTS_VOICE=en-US-ChristopherNeural    # Default voice
TTS_RATE=1.0                          # Speech rate (0.5 to 2.0)
TTS_VOLUME=1.0                        # Volume (0.0 to 1.0)
TTS_PITCH=0.0                         # Pitch adjustment (-100 to +100 Hz)

# Input Configuration
INPUT_FILE=~/.openclaw/speech_output.txt
MONITOR_INTERVAL=0.1                  # File check interval (seconds)

# Queue Configuration
MAX_QUEUE_SIZE=10                     # Maximum queued utterances

# Logging
LOG_LEVEL=INFO                        # DEBUG, INFO, WARNING, ERROR
LOG_FILE=                             # Optional log file path

# Display
DISPLAY_UPDATE_RATE=0.05              # UI refresh rate (20Hz)
ENABLE_COLORS=true                    # Terminal colors
```

### Command-Line Arguments

All settings can be overridden via CLI:

```bash
# Voice selection
python main.py --voice en-US-AriaNeural

# Speech rate (faster)
python main.py --rate 1.3

# Volume
python main.py --volume 0.8

# Custom input file
python main.py --input /path/to/custom/file.txt

# Compact display (single line)
python main.py --compact

# Local TTS (instant, no network)
python main.py --local

# Enable runtime control
python main.py --enable-control

# Debug mode
python main.py --log-level DEBUG

# List available voices
python main.py --list-voices
```

### Startup Script Options

The `start_speech_system.sh` script supports all the same flags:

```bash
./start_speech_system.sh --local --enable-control --compact
```

---

## Testing & Validation

### 1. Basic Functionality Test

```bash
# Terminal 1: Start OpenClaw Mouth
cd /path/to/open_mouth
./start_speech_system.sh

# Terminal 2: Send test message
echo "Hello, this is a test" >> ~/.openclaw/speech_output.txt
```

**Expected**: Hear "Hello, this is a test" within 1 second.

### 2. Speaking Signal Test

```bash
# Terminal 1: Start OpenClaw Mouth
./start_speech_system.sh

# Terminal 2: Monitor signal file
./monitor_speaking_status.py

# Terminal 3: Trigger speech
echo "Testing speaking signal" >> ~/.openclaw/speech_output.txt
```

**Expected**: Monitor shows `IDLE` → `QUEUED` → `SPEAKING` → `IDLE`

### 3. Queue Management Test

```bash
# Send multiple messages rapidly
for i in {1..5}; do
    echo "Message number $i" >> ~/.openclaw/speech_output.txt
done
```

**Expected**: All 5 messages spoken in order, queue status visible in terminal.

### 4. Runtime Control Test

```bash
# Terminal 1: Start with control enabled
./start_speech_system.sh --enable-control --local

# Terminal 2: Test control socket
echo "PING" | nc -U ~/.openclaw/mouth_control.sock
# Should return: OK:PONG

echo "CHANGE_VOICE:Samantha,local" | nc -U ~/.openclaw/mouth_control.sock
# Should return: OK:Voice changed to Samantha

# Terminal 3: Test new voice
echo "Testing new voice" >> ~/.openclaw/speech_output.txt
```

**Expected**: Speech uses Samantha voice.

### 5. Integration Test (with Open Ears)

```bash
# Terminal 1: Start Open Mouth
cd /path/to/open_mouth
./start_speech_system.sh

# Terminal 2: Start Open Ears (must monitor mouth_status.txt)
cd /path/to/open_ears
./start_voice_system.sh

# Terminal 3: Trigger speech
echo "This is the agent speaking" >> ~/.openclaw/speech_output.txt
```

**Expected**:
- Open Ears pauses listening during speech
- No echo/feedback
- Open Ears resumes after speech completes

---

## Troubleshooting

### Issue: No audio output

**Symptoms**: Text is queued but not heard

**Diagnostics**:
```bash
# Test system audio
afplay /System/Library/Sounds/Ping.aiff

# Check terminal for errors
# Look for "ERROR" messages in OpenClaw Mouth terminal

# Verify audio device
system_profiler SPAudioDataType
```

**Solutions**:
- Check system volume
- Ensure correct output device selected
- Try `--local` flag for local TTS
- Check internet connection (Edge-TTS requires network)

### Issue: Text not being detected

**Symptoms**: Write to file but nothing happens

**Diagnostics**:
```bash
# Verify file exists
ls -la ~/.openclaw/speech_output.txt

# Check file contents
cat ~/.openclaw/speech_output.txt

# Watch file changes
tail -f ~/.openclaw/speech_output.txt
```

**Solutions**:
- Ensure using `>>` (append) not `>` (overwrite)
- Check file permissions: `chmod 644 ~/.openclaw/speech_output.txt`
- Verify OpenClaw Mouth is running
- Check terminal for watchdog errors

### Issue: Speaking signal not working

**Symptoms**: Ears doesn't pause during speech

**Diagnostics**:
```bash
# Check signal file exists
ls -la ~/.openclaw/mouth_status.txt

# Monitor signal file
./monitor_speaking_status.py

# Manual check
cat ~/.openclaw/mouth_status.txt
```

**Solutions**:
- Ensure Mouth is running before Ears starts monitoring
- Check Ears is actually monitoring the file
- Verify file path is correct in Ears code
- Add debug logging to Ears' monitoring code

### Issue: High latency

**Symptoms**: >2 seconds from text write to audio start

**Diagnostics**:
```bash
# Check network speed (for Edge-TTS)
ping 1.1.1.1

# Monitor queue size in terminal display
# Check CPU usage
top -l 1 | grep -i mouth
```

**Solutions**:
- Use `--local` flag for instant local TTS
- Reduce speech rate: `--rate 0.9`
- Check queue size (may be backed up)
- Ensure adequate network bandwidth

### Issue: Control socket not working

**Symptoms**: Menu bar app won't connect

**Diagnostics**:
```bash
# Check socket exists
ls -la ~/.openclaw/mouth_control.sock

# Test socket manually
echo "PING" | nc -U ~/.openclaw/mouth_control.sock

# Check permissions
ls -l ~/.openclaw/mouth_control.sock
```

**Solutions**:
- Restart Mouth with `--enable-control` flag
- Check socket permissions
- Kill any stale processes using the socket
- Review terminal logs for socket creation errors

---

## Code Examples

### Example 1: Simple Agent Integration

```python
#!/usr/bin/env python3
"""
Simple agent that uses OpenClaw Mouth for output.
"""
import os
from pathlib import Path

SPEECH_FILE = Path.home() / ".openclaw" / "speech_output.txt"

def speak(text: str):
    """Send text to OpenClaw Mouth."""
    with open(SPEECH_FILE, "a") as f:
        f.write(f"{text}\n")

def main():
    # Greet user
    speak("Hello! I am your AI assistant.")
    speak("How can I help you today?")

    # Simulate processing
    import time
    time.sleep(2)

    speak("I'm ready to assist with your questions.")

if __name__ == "__main__":
    main()
```

### Example 2: Streaming LLM Integration

```python
#!/usr/bin/env python3
"""
Stream Claude responses to OpenClaw Mouth sentence-by-sentence.
Based on claude_speak.py in the repo.
"""
import re
from pathlib import Path
from anthropic import Anthropic

SPEECH_FILE = Path.home() / ".openclaw" / "speech_output.txt"

def speak_sentence(sentence: str):
    """Write sentence to speech file."""
    with open(SPEECH_FILE, "a") as f:
        f.write(sentence.strip() + "\n")
        f.flush()

def stream_claude_response(prompt: str, api_key: str):
    """Stream Claude response with real-time speech."""
    client = Anthropic(api_key=api_key)
    sentence_pattern = re.compile(r'([.!?])\s+')

    buffer = ""

    with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text in stream.text_stream:
            buffer += text

            # Extract complete sentences
            while True:
                match = sentence_pattern.search(buffer)
                if not match:
                    break

                end_pos = match.end()
                sentence = buffer[:end_pos].strip()

                if sentence:
                    speak_sentence(sentence)

                buffer = buffer[end_pos:]

        # Speak remaining text
        if buffer.strip():
            speak_sentence(buffer.strip())

# Usage
stream_claude_response("Tell me a story about AI assistants.", api_key="...")
```

### Example 3: Full Voice Loop with Error Handling

```python
#!/usr/bin/env python3
"""
Complete integration: Reads from Ears, writes to Mouth, monitors speaking signal.
"""
import time
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceAgent:
    """
    Agent with full OpenClaw Ears and Mouth integration.
    """

    def __init__(self):
        # File paths
        self.ears_output = Path.home() / ".openclaw" / "voice" / "input.txt"
        self.mouth_input = Path.home() / ".openclaw" / "speech_output.txt"
        self.mouth_status = Path.home() / ".openclaw" / "mouth_status.txt"

        # State
        self.last_position = 0
        self.is_speaking = False

    def is_agent_speaking(self) -> bool:
        """Check if agent is currently speaking."""
        if not self.mouth_status.exists():
            return False

        try:
            content = self.mouth_status.read_text().strip()
            parts = content.split("|")
            return len(parts) >= 2 and parts[1] == "SPEAKING"
        except:
            return False

    def speak(self, text: str) -> bool:
        """Send text to OpenClaw Mouth."""
        try:
            with open(self.mouth_input, "a", encoding="utf-8") as f:
                f.write(f"{text}\n")
            logger.info(f"Speaking: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to speak: {e}")
            return False

    def get_new_voice_input(self) -> Optional[str]:
        """Get new input from OpenClaw Ears."""
        if not self.ears_output.exists():
            return None

        try:
            # Read from last position
            with open(self.ears_output, "r") as f:
                f.seek(self.last_position)
                new_content = f.read().strip()
                self.last_position = f.tell()

            return new_content if new_content else None
        except Exception as e:
            logger.error(f"Failed to read ears output: {e}")
            return None

    def process_input(self, user_input: str):
        """Process user input and generate response."""
        logger.info(f"Processing: {user_input}")

        # Simple echo bot for demo
        response = f"You said: {user_input}"
        self.speak(response)

    def run(self):
        """Main agent loop."""
        logger.info("Starting voice agent...")
        logger.info("Monitoring OpenClaw Ears for input")
        logger.info("Speaking through OpenClaw Mouth")

        self.speak("Voice agent initialized. I'm listening!")

        try:
            while True:
                # Check if we're speaking (don't process input while speaking)
                self.is_speaking = self.is_agent_speaking()

                if not self.is_speaking:
                    # Get new voice input
                    user_input = self.get_new_voice_input()

                    if user_input:
                        self.process_input(user_input)

                time.sleep(0.1)  # Check every 100ms

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.speak("Goodbye!")

if __name__ == "__main__":
    agent = VoiceAgent()
    agent.run()
```

---

## Performance Characteristics

### Latency

| Stage | Latency | Notes |
|-------|---------|-------|
| File write detection | <100ms | Watchdog file system events |
| Text queuing | <10ms | Thread-safe queue |
| TTS synthesis (Edge-TTS) | 300-800ms | Network-dependent |
| TTS synthesis (Local) | <50ms | macOS `say` command |
| Audio playback start | <50ms | `afplay` initialization |
| Speaking signal update | <10ms | Immediate atomic write |
| **Total (Edge-TTS)** | **~500-1000ms** | First utterance |
| **Total (Local)** | **~200ms** | First utterance |

### Resource Usage

| Metric | Idle | Active (Edge-TTS) | Active (Local) |
|--------|------|-------------------|----------------|
| CPU | <5% | 15-30% | 10-20% |
| Memory | ~100-150MB | ~150-200MB | ~80-120MB |
| Network | 0 | 50-100KB per utterance | 0 |
| Disk I/O | Minimal | Temp audio files | Minimal |

### Scalability

- **Max queue size**: 10 utterances (configurable via `MAX_QUEUE_SIZE`)
- **Max utterance length**: No hard limit, but keep <500 chars for best experience
- **Concurrent operation**: Single instance per user (file-based locking)
- **Multiple agents**: Can write to same file, queued in order

---

## Summary: Integration Checklist

For integrating OpenClaw Mouth with Open Ears:

- [ ] **Start OpenClaw Mouth** with default or custom settings
- [ ] **Verify speech works** by echoing test text to `~/.openclaw/speech_output.txt`
- [ ] **Implement speaking signal monitoring** in OpenClaw Ears
  - [ ] Monitor `~/.openclaw/mouth_status.txt`
  - [ ] Pause microphone when status is `SPEAKING`
  - [ ] Resume microphone when status is `IDLE`
  - [ ] Add 100-150ms debouncing
- [ ] **Test coordination**: Verify Ears pauses during Mouth speech
- [ ] **Handle edge cases**:
  - [ ] Mouth not running (file doesn't exist)
  - [ ] Mouth crashes during speech (status stuck)
  - [ ] Rapid speech toggles (debouncing)
  - [ ] File read errors (handle gracefully)
- [ ] **Add error logging** for troubleshooting
- [ ] **Document** the integration in Open Ears README

---

## Support & Resources

### Documentation Files

- [`README.md`](README.md) - User-facing documentation
- [`AGENT_INSTRUCTIONS.txt`](AGENT_INSTRUCTIONS.txt) - Agent integration guide (emphasizes DO NOT MODIFY)
- [`SPEAKING_SIGNAL.md`](SPEAKING_SIGNAL.md) - Detailed speaking signal protocol
- [`MENU_BAR_GUIDE.md`](MENU_BAR_GUIDE.md) - Runtime control documentation
- [`OPEN_MOUTH_DESIGN.md`](OPEN_MOUTH_DESIGN.md) - Original design specification
- This file: `INTEGRATION_GUIDE.md` - Technical integration documentation

### Key Source Files

- [`main.py`](main.py) - Entry point
- [`src/core/mouth_pipeline.py`](src/core/mouth_pipeline.py) - Main orchestration
- [`src/services/tts_service.py`](src/services/tts_service.py) - TTS synthesis
- [`src/services/text_monitor.py`](src/services/text_monitor.py) - File monitoring
- [`src/utils/openclaw_notifier.py`](src/utils/openclaw_notifier.py) - Speaking signal
- [`src/control/control_server.py`](src/control/control_server.py) - Runtime control

### Testing Tools

- [`claude_speak.py`](claude_speak.py) - Stream Claude responses to speech
- [`monitor_speaking_status.py`](monitor_speaking_status.py) - Monitor speaking signal
- [`test_signal.py`](test_signal.py) - Test signal file mechanism
- [`test_instant_speech.sh`](test_instant_speech.sh) - Quick speech test

### Related Projects

- **OpenClaw Ears**: Voice input system (companion to this project)
- **OpenClaw**: Full AI agent framework

---

## Design Philosophy

> "Keep it simple. Keep it compatible. Keep it consistent."

OpenClaw Mouth is designed to be:

1. **Dead simple to use**: Just write text to a file
2. **Transparent**: Terminal UI shows exactly what's happening
3. **Non-invasive**: No code changes required in agents
4. **Reliable**: Extensive error handling, graceful degradation
5. **Compatible**: Works standalone or with OpenClaw Ears
6. **Maintainable**: Clear architecture, well-documented

The agent integrating with Open Ears should **trust the system** and focus on the speaking signal protocol for coordination. The system handles all the complexity of TTS, audio playback, queueing, and status signaling.

---

**This document is comprehensive for integration. For questions or issues, refer to the specific documentation files listed in the Support section or examine the source files mentioned.**

---

*Last updated: 2026-02-01*
*OpenClaw Mouth Version: 1.0*
*For OpenClaw Ears integration agent*
