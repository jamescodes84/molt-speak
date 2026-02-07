# OpenClaw Integration Guide

This guide explains how to integrate OpenClaw Ears and OpenClaw Mouth using the standalone integration coordinator.

## Architecture Overview

The integration uses a **standalone coordinator service** that sits between OpenClaw Ears and OpenClaw Mouth:

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  OpenClaw Ears  │ ←─→ │  Integration         │ ←─→ │ OpenClaw Mouth  │
│  (Voice Input)  │     │  Coordinator         │     │  (TTS Output)   │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
        ↑                         ↓                            ↑
        │                    Monitors                          │
        │               mouth_status.txt                       │
        │                         ↓                            │
        │                    Creates/Removes                   │
        └───── Checks ───── ears_pause.signal ─────────────────┘
```

## How It Works

### 1. OpenClaw Mouth (Already Complete)

OpenClaw Mouth writes speaking status to `~/.openclaw/mouth_status.txt`:

```
2026-02-01T12:15:24.161586|SPEAKING|Hello, this is a test message
2026-02-01T12:15:25.167795|IDLE|
```

### 2. Integration Coordinator (Standalone Service)

The coordinator service (in the root `src/` directory):
- Monitors `~/.openclaw/mouth_status.txt` every 100ms
- When status changes to "SPEAKING":
  - Creates `~/.openclaw/ears_pause.signal`
- When status changes to "IDLE":
  - Removes `~/.openclaw/ears_pause.signal` (after 200ms debounce)

### 3. OpenClaw Ears (Needs Modification)

OpenClaw Ears should check for the pause signal file in its capture loop.

## Required Changes to OpenClaw Ears

### Option A: Simple File Check (Recommended)

**File**: `open_ears/src/core/voice_pipeline.py`

**In the `_capture_loop` method** (around line 141):

```python
def _capture_loop(self):
    """Capture and queue audio segments"""
    # Pause signal file
    pause_signal_file = Path.home() / ".openclaw" / "ears_pause.signal"

    while self.running:
        time.sleep(self.segment_duration)

        # Skip if we're speaking (TTS active OR pause signal exists)
        if self.is_speaking_tts or pause_signal_file.exists():
            with self.buffer_lock:
                self.audio_buffer = []  # Clear buffer to avoid echo
            continue

        # ... rest of capture loop
```

**Add import at top of file**:
```python
from pathlib import Path
```

That's it! Just one line added to the existing check.

### Option B: Enhanced with Signal Reading

For additional context, you can read the signal file timestamp:

```python
def _is_paused_by_mouth(self) -> bool:
    """Check if mouth is speaking and we should pause."""
    pause_signal_file = Path.home() / ".openclaw" / "ears_pause.signal"

    if not pause_signal_file.exists():
        return False

    try:
        # Optional: Read timestamp to check signal age
        timestamp = float(pause_signal_file.read_text().strip())
        age_seconds = time.time() - timestamp

        # Ignore stale signals (> 10 seconds old)
        if age_seconds > 10:
            return False

        return True
    except:
        # If we can't read it, assume it's valid
        return True

# Then in capture loop:
if self.is_speaking_tts or self._is_paused_by_mouth():
    with self.buffer_lock:
        self.audio_buffer = []
    continue
```

## Setup and Testing

### 1. Start the Integration Coordinator

```bash
cd /path/to/open_speak
./start_integration.sh
```

You should see:
```
============================================================
OpenClaw Voice Loop Coordinator
============================================================
Monitoring: /Users/you/.openclaw/mouth_status.txt
Signal file: /Users/you/.openclaw/ears_pause.signal
Poll interval: 0.1s
Debounce: 200ms
============================================================
✅ Coordinator started
Press Ctrl+C to stop
```

### 2. Start OpenClaw Mouth

```bash
cd open_mouth
./start_speech_system.sh
```

### 3. Start OpenClaw Ears (with modifications)

```bash
cd open_ears
./start_voice_system.sh
```

### 4. Test the Integration

```bash
# Send text to Mouth
echo "Testing echo prevention" >> ~/.openclaw/speech_output.txt
```

**Expected behavior**:
1. ✅ Mouth starts speaking (you hear TTS)
2. ✅ Coordinator creates pause signal
3. ✅ Ears detects signal and pauses (clears buffer)
4. ✅ No transcription occurs while speaking
5. ✅ Mouth finishes, coordinator removes signal (after 200ms)
6. ✅ Ears resumes listening
7. ✅ Speak now → transcription works

## File Locations

| File | Purpose | Created By | Read By |
|------|---------|------------|---------|
| `~/.openclaw/mouth_status.txt` | Mouth speaking status | OpenClaw Mouth | Integration Coordinator |
| `~/.openclaw/ears_pause.signal` | Pause microphone signal | Integration Coordinator | OpenClaw Ears |
| `~/.openclaw/speech_output.txt` | Text for TTS | User/Agent | OpenClaw Mouth |

## Configuration

The integration coordinator can be configured via `.env`:

```bash
# Integration
ENABLE_INTEGRATION=true

# Monitoring
MOUTH_STATUS_POLL_INTERVAL=0.1    # Poll every 100ms
MOUTH_STATUS_DEBOUNCE_MS=200      # 200ms debounce

# Logging
LOG_LEVEL=INFO
```

## Troubleshooting

### Ears not pausing during TTS

1. **Check coordinator is running**:
   ```bash
   ps aux | grep "main.py"
   ```

2. **Check pause signal file is created**:
   ```bash
   # Trigger speech
   echo "test" >> ~/.openclaw/speech_output.txt

   # Quickly check (while speaking)
   ls -la ~/.openclaw/ears_pause.signal
   ```

3. **Verify Ears is checking the signal**:
   - Add debug logging in Ears capture loop
   - Print when pause signal is detected

### Coordinator not detecting Mouth

1. **Verify Mouth status file exists**:
   ```bash
   cat ~/.openclaw/mouth_status.txt
   ```

2. **Check coordinator logs**:
   - Should see "OpenClaw Mouth status file found"
   - If not, Mouth may not be running

### Still getting echo

1. **Verify timing**: The debounce is 200ms - there may be a small window at the end
   - Increase `MOUTH_STATUS_DEBOUNCE_MS` to 300-400ms

2. **Check Ears modification**: Ensure the pause check is in the right place (before buffering)

## Performance Impact

- **Coordinator CPU**: <0.1% (polls small file 10x/second)
- **Ears CPU**: <0.01% (one file existence check per segment)
- **Latency**: <200ms from Mouth speaking to Ears paused
- **Memory**: Negligible (no buffers, just file checks)

## Benefits of Standalone Architecture

1. **No coupling**: Ears and Mouth don't need to know about each other
2. **Easy to disable**: Stop coordinator = no integration
3. **Testable**: Each component works independently
4. **Maintainable**: Integration logic in one place
5. **Flexible**: Can add features (bidirectional pause, metrics) without touching Ears/Mouth
6. **Production-ready**: Proper logging, error handling, graceful degradation

## Future Enhancements

Possible improvements to the coordinator:

1. **Bidirectional pause**: Pause Mouth when Ears is transcribing
2. **Metrics**: Track pause/resume cycles, timing
3. **Web UI**: Visual status dashboard
4. **Socket-based**: Replace file signals with IPC sockets (lower latency)
5. **Multi-agent**: Support multiple Ears/Mouth instances

## Summary

The standalone integration coordinator provides a clean, simple way to prevent echo between OpenClaw Ears and OpenClaw Mouth:

- ✅ **Minimal changes to Ears**: One line added to existing check
- ✅ **No changes to Mouth**: Already writes status file
- ✅ **Independent service**: Can start/stop/configure separately
- ✅ **File-based**: Simple, reliable, no complex IPC
- ✅ **Production-ready**: Logging, error handling, configurability

For questions or issues, see the main [README.md](README.md) or open an issue.
