# Speaking Signal - OpenClaw Mouth to Ears Coordination

## Overview

OpenClaw Mouth provides a real-time signal file that indicates when the agent is speaking. This allows OpenClaw Ears (or any other listening component) to pause audio input while the agent is speaking, preventing the system from picking up its own voice.

## Signal File Location

```
~/.openclaw/mouth_status.txt
```

This file is automatically created and managed by the OpenClaw Mouth system.

## File Format

The status file contains a single line with pipe-delimited fields:

```
<timestamp>|<status>|<details>
```

### Fields

1. **Timestamp** (ISO 8601 format): When the status was last updated
   - Example: `2026-02-01T12:15:22.152594`

2. **Status** (string): Current system status
   - `IDLE`: System is idle, not speaking
   - `SPEAKING`: Agent is currently speaking
   - `QUEUED`: Speech is queued but not yet playing
   - `ERROR`: An error occurred

3. **Details** (string, optional): Additional context
   - For `SPEAKING`: Preview of text being spoken (first 50 characters)
   - For `QUEUED`: Number of items in queue (e.g., "3 items")
   - For `ERROR`: Error message
   - For `IDLE`: Empty

### Example Status Lines

```
2026-02-01T12:15:22.152594|IDLE|
2026-02-01T12:15:23.157809|QUEUED|3 items
2026-02-01T12:15:24.161586|SPEAKING|Hello, this is a test message
2026-02-01T12:15:25.167795|IDLE|
```

## Visual Indicators

When the agent is speaking, the terminal UI shows prominent visual cues:

### Full Display Mode
- **Green double-line border** (═) instead of regular border (─)
- **Prominent banner**: "🔊 AGENT SPEAKING - EARS SHOULD PAUSE 🔊"
- **Status icon**: 📢 with green highlighting

### Compact Display Mode
- **Bold indicator**: "🔊 AGENT SPEAKING" at the start of the line
- **Green highlighting** on all speaking-related text

## Integration Guide for OpenClaw Ears

### Simple Polling Approach

```python
import time
from pathlib import Path

def should_pause_listening() -> bool:
    """Check if agent is speaking and listening should pause."""
    status_file = Path.home() / ".openclaw" / "mouth_status.txt"

    if not status_file.exists():
        return False  # Mouth not running, safe to listen

    try:
        with open(status_file, "r") as f:
            content = f.read().strip()

        # Parse format: timestamp|status|details
        parts = content.split("|")
        if len(parts) >= 2:
            status = parts[1]
            return status == "SPEAKING"
    except:
        return False

    return False

# Usage in your listening loop
while listening:
    if should_pause_listening():
        # Pause audio input
        print("Agent speaking - pausing microphone")
        pause_microphone()
    else:
        # Resume listening
        process_audio_input()

    time.sleep(0.1)  # Check every 100ms
```

### Event-Driven Approach with File Watching

```python
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class MouthStatusWatcher(FileSystemEventHandler):
    def __init__(self, on_speaking_change):
        self.status_file = Path.home() / ".openclaw" / "mouth_status.txt"
        self.on_speaking_change = on_speaking_change
        self.last_status = None

    def on_modified(self, event):
        if event.src_path == str(self.status_file):
            self.check_status()

    def check_status(self):
        try:
            with open(self.status_file, "r") as f:
                content = f.read().strip()

            parts = content.split("|")
            if len(parts) >= 2:
                status = parts[1]

                if status != self.last_status:
                    self.last_status = status
                    is_speaking = (status == "SPEAKING")
                    self.on_speaking_change(is_speaking)
        except:
            pass

def on_speaking_change(is_speaking: bool):
    if is_speaking:
        print("🔊 Agent started speaking - PAUSE listening")
        pause_microphone()
    else:
        print("✅ Agent stopped speaking - RESUME listening")
        resume_microphone()

# Setup watcher
watcher = MouthStatusWatcher(on_speaking_change)
observer = Observer()
observer.schedule(watcher, str(Path.home() / ".openclaw"), recursive=False)
observer.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
```

## Testing the Signal

### Monitor the Signal File

Use the included monitoring script to watch the signal file in real-time:

```bash
./monitor_speaking_status.py
```

This script will display status changes as they occur, showing you exactly when the agent starts and stops speaking.

### Manual Testing

1. Start OpenClaw Mouth:
   ```bash
   ./start_speech_system.sh
   ```

2. In another terminal, watch the status file:
   ```bash
   watch -n 0.1 cat ~/.openclaw/mouth_status.txt
   ```

3. Send text to be spoken:
   ```bash
   echo "Hello world" >> ~/.openclaw/speech_output.txt
   ```

4. Observe the status file changing:
   - `IDLE` → `QUEUED` → `SPEAKING` → `IDLE`

## Implementation Details

### OpenClawNotifier Class

The signal mechanism is implemented in [src/utils/openclaw_notifier.py](src/utils/openclaw_notifier.py):

```python
from src.utils.openclaw_notifier import OpenClawNotifier

# Create notifier
notifier = OpenClawNotifier()

# Update status
notifier.notify_speaking("Text being spoken")
notifier.notify_idle()
notifier.notify_queued(3)  # 3 items in queue
notifier.notify_error("Error message")

# Cleanup on shutdown
notifier.cleanup()
```

### Automatic Updates

The MouthPipeline automatically updates the status file:

- **QUEUED**: When text is added to the queue
- **SPEAKING**: When audio playback starts
- **IDLE**: When playback completes and queue is empty
- **ERROR**: When an error occurs

See [src/core/mouth_pipeline.py](src/core/mouth_pipeline.py) for implementation details.

## Timing Considerations

### Update Frequency

- Status file is updated immediately when state changes
- No polling delay within OpenClaw Mouth
- File writes are atomic (single write operation)

### Recommended Polling Interval

For OpenClaw Ears integration:
- **100ms (0.1s)**: Good balance of responsiveness and CPU usage
- **50ms (0.05s)**: More responsive, slightly higher CPU usage
- **200ms (0.2s)**: Lower CPU usage, may have slight delay

### Latency

Typical latency from speech start to status file update:
- **< 10ms**: Status file write
- **100ms**: Default polling interval (if using polling)
- **0ms**: If using file watching (inotify/FSEvents)

## Best Practices

### For OpenClaw Ears Integration

1. **Check file existence**: The status file is deleted on shutdown
2. **Handle errors gracefully**: File may be temporarily unavailable
3. **Use file watching**: More efficient than polling for real-time updates
4. **Add debouncing**: Avoid rapid pause/resume cycles
5. **Default to safe**: If unsure, assume NOT speaking (allow listening)

### Debouncing Example

```python
import time

class SpeakingDebouncer:
    def __init__(self, debounce_ms: int = 100):
        self.debounce_ms = debounce_ms
        self.last_speaking_time = 0
        self.last_idle_time = 0

    def is_speaking(self, current_status: str) -> bool:
        now = time.time() * 1000  # Convert to ms

        if current_status == "SPEAKING":
            self.last_speaking_time = now
            return True
        else:
            self.last_idle_time = now
            # Keep "speaking" state for debounce_ms after seeing IDLE
            time_since_speaking = now - self.last_speaking_time
            return time_since_speaking < self.debounce_ms
```

## Troubleshooting

### Status file not found

**Cause**: OpenClaw Mouth is not running

**Solution**: Start the speech system with `./start_speech_system.sh`

### Status stuck on SPEAKING

**Cause**: System crashed during playback

**Solution**:
1. Restart OpenClaw Mouth
2. The file is automatically cleaned up on proper shutdown
3. Manually delete `~/.openclaw/mouth_status.txt` if needed

### Rapid status changes

**Cause**: Multiple short utterances being spoken quickly

**Solution**: Implement debouncing in your listener (see example above)

## Future Enhancements

Potential improvements to the signaling mechanism:

- [ ] Add audio output device lock file
- [ ] Include estimated speaking duration
- [ ] Add speaking start/end timestamps
- [ ] Support for multiple speech streams
- [ ] JSON format option for structured data
- [ ] WebSocket-based real-time updates

## Related Files

- [src/utils/openclaw_notifier.py](src/utils/openclaw_notifier.py) - Signal implementation
- [src/core/mouth_pipeline.py](src/core/mouth_pipeline.py) - Pipeline using signals
- [src/core/terminal_visualizer.py](src/core/terminal_visualizer.py) - Visual indicators
- [monitor_speaking_status.py](monitor_speaking_status.py) - Monitoring tool
- [test_signal.py](test_signal.py) - Signal testing script

## Questions?

For issues or questions about the speaking signal mechanism:
1. Check the logs in the OpenClaw Mouth terminal
2. Run `./monitor_speaking_status.py` to debug signal updates
3. Verify `~/.openclaw/mouth_status.txt` exists and is readable
4. See [README.md](README.md) for general system documentation
