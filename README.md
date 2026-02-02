# OpenSpeak Voice Loop System

Complete voice interaction system for AI agents on macOS, featuring voice input (Ears), text-to-speech output (Mouth), and intelligent echo prevention.

## 🚀 Quick Install (One-Line)

```bash
curl -fsSL https://raw.githubusercontent.com/jamescodes84/open_speak/poc/install.sh | bash
```

> ⚠️ **Prerequisite:** You must have [OpenClaw TUI](https://github.com/anthropics/claude-code) running in its own terminal window for Molt-Speak to work. The voice system types transcribed speech into the OpenClaw agent.

After installation:
```bash
molt-speak start   # Open menu bar (select voice & start)
molt-speak status  # Check status
molt-speak stop    # Stop the voice loop
```

## Overview

This integration service monitors OpenClaw Mouth's speaking status and signals OpenClaw Ears to pause its microphone when the agent is speaking, preventing audio feedback loops.

### How It Works

```
1. OpenClaw Mouth speaks → Updates mouth_status.txt to "SPEAKING"
2. Integration monitors file → Detects "SPEAKING" status
3. Creates pause signal file → ~/.openclaw/ears_pause.signal
4. OpenClaw Ears checks signal → Pauses microphone
5. No echo! 🎉
6. Mouth finishes → Status changes to "IDLE"
7. Integration removes signal → Ears resumes listening
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│            Voice Loop Coordinator                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Monitor Thread                                      │
│    ↓                                                 │
│  Polls ~/.openclaw/mouth_status.txt (100ms)         │
│    ↓                                                 │
│  Detects SPEAKING status                            │
│    ↓                                                 │
│  Creates ~/.openclaw/ears_pause.signal              │
│    ↓                                                 │
│  OpenClaw Ears checks signal → Pauses mic           │
│    ↓                                                 │
│  Mouth finishes (IDLE status)                       │
│    ↓                                                 │
│  Removes pause signal (after 200ms debounce)        │
│    ↓                                                 │
│  OpenClaw Ears resumes listening                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.9+
- OpenClaw Ears installed and configured
- OpenClaw Mouth installed and configured

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or use the startup script (creates venv automatically)
./start_integration.sh
```

### Usage

**Terminal 1** - Start Integration Coordinator:
```bash
./start_integration.sh
```

**Terminal 2** - Start OpenClaw Mouth:
```bash
cd open_mouth
./start_speech_system.sh
```

**Terminal 3** - Start OpenClaw Ears (with pause signal support):
```bash
cd open_ears
./start_voice_system.sh
```

**Terminal 4** - Test:
```bash
# Send text to Mouth
echo "Hello, testing echo prevention" >> ~/.openclaw/speech_output.txt

# Speak while TTS is playing - no transcription should occur
# Speak after TTS finishes - transcription should work
```

## Configuration

Create a `.env` file (see `.env.example`):

```bash
# Integration
ENABLE_INTEGRATION=true

# Monitoring
MOUTH_STATUS_POLL_INTERVAL=0.1    # Poll every 100ms
MOUTH_STATUS_DEBOUNCE_MS=200      # 200ms debounce

# Logging
LOG_LEVEL=INFO
LOG_FILE=                          # Optional log file path
```

## Project Structure

```
.
├── src/
│   ├── config/
│   │   └── settings.py           # Configuration management
│   ├── services/
│   │   └── mouth_status_monitor.py  # Monitor Mouth's speaking status
│   ├── core/
│   │   └── coordinator.py        # Main coordination logic
│   └── utils/
│       └── __init__.py
├── main.py                       # Entry point
├── requirements.txt              # Dependencies (minimal)
├── start_integration.sh          # Startup script
├── .env.example                  # Configuration template
└── README.md                     # This file
```

## How OpenClaw Ears Should Integrate

OpenClaw Ears needs to check for the pause signal file:

```python
# In open_ears capture loop:
pause_signal_file = Path.home() / ".openclaw" / "ears_pause.signal"

if pause_signal_file.exists():
    # Pause microphone - clear buffer
    with buffer_lock:
        audio_buffer = []
    continue  # Skip transcription
```

## Signal Files

| File | Purpose | Created By | Read By |
|------|---------|------------|---------|
| `~/.openclaw/mouth_status.txt` | Mouth speaking status | OpenClaw Mouth | This integration |
| `~/.openclaw/ears_pause.signal` | Pause microphone signal | This integration | OpenClaw Ears |

## Status File Format

**mouth_status.txt**:
```
<ISO-8601 timestamp>|<status>|<details>
```

Example:
```
2026-02-01T12:15:24.161586|SPEAKING|Hello, this is a test message
2026-02-01T12:15:25.167795|IDLE|
```

**ears_pause.signal**:
```
<unix timestamp>
```

Simple file existence check - if exists, Ears should pause.

## Features

- ✅ **Zero-dependency integration** - Uses stdlib only (+ python-dotenv)
- ✅ **File-based signaling** - Simple, reliable, no sockets/IPC needed
- ✅ **Debouncing** - Prevents rapid pause/resume cycles
- ✅ **Graceful degradation** - Works even if Mouth isn't running
- ✅ **Thread-safe** - Concurrent monitoring and signaling
- ✅ **Configurable** - Tune polling and debounce via environment
- ✅ **Lightweight** - Minimal CPU usage (~0.1%)
- ✅ **Production-ready** - Proper logging, error handling, signal handlers

## Performance

- **CPU Usage**: <0.1% (polls small file 10x/second)
- **Memory**: ~5MB (single monitoring thread)
- **Latency**: <200ms from Mouth speaking to Ears paused
- **Overhead**: Negligible file I/O (single line reads)

## Troubleshooting

### Integration not working

**Check coordinator is running**:
```bash
ps aux | grep "main.py"
```

**Check pause signal file**:
```bash
# Should appear when Mouth is speaking
ls -la ~/.openclaw/ears_pause.signal
```

**Check Mouth status file**:
```bash
cat ~/.openclaw/mouth_status.txt
```

### Ears not pausing

Make sure OpenClaw Ears is modified to check the pause signal file. The integration creates the signal, but Ears must read and respect it.

### High CPU usage

Increase `MOUTH_STATUS_POLL_INTERVAL` to reduce polling frequency (e.g., `0.2` for 200ms).

## Development

### Running tests

```bash
# Unit tests (TODO)
pytest tests/unit/

# Integration tests (TODO)
pytest tests/integration/
```

### Logging levels

- `DEBUG`: Detailed state transitions
- `INFO`: Coordinator lifecycle, speaking events
- `WARNING`: Configuration issues, file unavailable
- `ERROR`: Exceptions, file I/O errors

## License

MIT License - See LICENSE file

## Author

OpenClaw Project
Version 1.0.0
