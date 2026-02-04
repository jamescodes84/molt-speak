# Open Ears Voice System - Integration Guide

## Overview

Open Ears (also known as "open_mouth" or "openclaw-ears") is an ultra-fast voice input system designed for AI agents. It provides real-time speech-to-text transcription and automatically delivers voice commands to your agent's interface.

**Key Features:**
- ✨ Real-time voice transcription using Whisper AI
- 🎯 Smart window targeting (sends commands to specific applications)
- 🔇 Echo prevention (mutes microphone during TTS output)
- ⚡ Optimized for speed (INT8 quantization, in-memory processing)
- 📊 Live audio visualization in terminal
- 🔊 Optional TTS response support

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Voice Pipeline Flow                      │
└─────────────────────────────────────────────────────────────┘

 User speaks
     ↓
 [Audio Capture] ← sounddevice (16kHz, mono)
     ↓
 [Voice Activity Detection] ← Amplitude threshold
     ↓
 [Audio Buffering] ← Segments of 1.5-3s
     ↓
 [Whisper Transcription] ← faster-whisper + INT8
     ↓
 [Text Delivery] ← AppleScript (macOS) or pyautogui
     ↓
 → VSCode/Terminal input field
     ↓
 → Your AI Agent receives the command!
```

### Core Components

#### 1. **UltraFastVoicePipeline** (`src/core/voice_pipeline.py`)
The main pipeline orchestrator. Manages:
- Audio capture threads
- Transcription workers
- Display updates
- TTS output (optional)

#### 2. **WhisperTranscriberOptimized** (`src/services/transcription_service.py`)
Fast speech-to-text using:
- faster-whisper library (4x faster than OpenAI Whisper)
- INT8 quantization (2x speedup)
- In-memory processing (no file I/O)

#### 3. **TerminalVisualizer** (`src/core/terminal_visualizer.py`)
Real-time audio visualization showing:
- Audio levels
- Speech detection status
- Latest transcription
- Waveform visualization

#### 4. **Window Targeting System**
Intelligent command delivery:
- **Primary**: AppleScript targeting VSCode/Terminal on macOS
- **Fallback**: pyautogui typing to focused window
- **No window switching required** - sends keystrokes directly to target process

## How It Works

### Voice Input Flow

1. **Audio Capture** (16kHz mono PCM)
   - Continuous audio streaming via sounddevice
   - 50ms chunks buffered in memory
   - Real-time amplitude monitoring

2. **Speech Detection**
   - Amplitude threshold: 500 (configurable)
   - Segments captured when threshold exceeded
   - Duration: 1.5-3 seconds (configurable)

3. **Transcription**
   - Audio normalized to 16-bit PCM
   - Passed directly to Whisper (no file I/O)
   - Language: English (pre-specified for speed)
   - Typical latency: 0.5-1.5 seconds

4. **Text Delivery**
   ```applescript
   tell application "System Events"
       if (name of processes) contains "Code" then
           tell process "Code"
               keystroke "transcribed text here"
               keystroke return
           end tell
       end if
   end tell
   ```

5. **Agent Receives Input**
   - Text appears in your agent's input field
   - Enter is pressed automatically
   - Agent processes it as normal typed input

### Echo Prevention

When TTS is enabled, the system prevents feedback loops:

```python
# During TTS playback
self.is_speaking_tts = True  # Flag set

# In capture loop
if self.is_speaking_tts:
    with self.buffer_lock:
        self.audio_buffer = []  # Clear buffer
    continue  # Skip transcription
```

**Result**: Microphone is effectively muted during agent speech output.

## Integration Steps

### Step 1: Understand the Flow

Your agent doesn't need to "integrate" in the traditional sense. The voice system **types commands directly into your interface** as if the user typed them.

```
User says: "What's the weather in Paris?"
    ↓
Voice system transcribes: "What's the weather in Paris?"
    ↓
System types it into your input field
    ↓
System presses Enter
    ↓
Your agent receives: "What's the weather in Paris?"
    ↓
Your agent responds normally!
```

### Step 2: No Code Changes Required

If your agent runs in VSCode or Terminal, **no integration code needed**. Just:

1. Start your agent (Claude Code, custom TUI, etc.)
2. Run the voice system: `./start_voice_system.sh`
3. Speak commands - they appear automatically!

### Step 3: Optional - Advanced Integration

For custom integrations, you can:

#### Option A: File-based Queue (Recommended for custom agents)

```python
from pathlib import Path
import json

queue_file = Path("~/.openclaw/voice/agent_queue.jsonl").expanduser()

# Monitor the queue file
with open(queue_file, 'r') as f:
    for line in f:
        entry = json.loads(line)
        command = entry['text']
        timestamp = entry['timestamp']

        # Process the voice command
        process_command(command)
```

#### Option B: Direct Python Integration

```python
from src.core.voice_pipeline import UltraFastVoicePipeline

# Custom callback for transcriptions
def on_transcription(text):
    # Your agent receives the command here
    your_agent.process_input(text)

# Create pipeline
pipeline = UltraFastVoicePipeline(
    model_size='tiny',
    segment_duration=1.5,
    speech_threshold=500
)

# Override the send method
pipeline._send_to_openclaw_tui = on_transcription

# Start listening
pipeline.start()
```

#### Option C: Socket/IPC (For production systems)

Create a socket server in your agent:

```python
import socket

server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind("/tmp/agent_voice.sock")
server.listen(1)

while True:
    conn, addr = server.accept()
    data = conn.recv(1024).decode()
    your_agent.process_input(data)
    conn.close()
```

Then modify voice pipeline to send via socket instead of keystrokes.

## Configuration

### Command-line Options

```bash
./start_voice_system.sh [OPTIONS]

Options:
  --model SIZE        Whisper model (tiny, base, small, medium)
                      Default: tiny (fastest)

  --duration SECONDS  Segment duration before transcription
                      Default: 3.0
                      Recommendation: 1.5-3.0 (lower = faster response)

  --threshold VALUE   Speech detection threshold
                      Default: 500
                      Range: 100-2000 (lower = more sensitive)

  --tts              Enable text-to-speech responses
                     Default: disabled
```

### Performance Tuning

**For Maximum Speed:**
```bash
python main.py --model tiny --duration 1.5 --threshold 500
```
- Latency: ~0.5-1.0s
- Accuracy: Good for clear speech

**For Maximum Accuracy:**
```bash
python main.py --model base --duration 3.0 --threshold 300
```
- Latency: ~1.5-2.5s
- Accuracy: Excellent

**For Balanced Performance:**
```bash
python main.py --model tiny --duration 2.0 --threshold 500
```
- Latency: ~1.0-1.5s (default configuration)
- Accuracy: Very good

## TTS Integration (Optional)

If your agent generates text responses, you can enable TTS:

### Enable TTS Mode

```bash
./start_voice_system.sh --tts
```

### In Your Agent Code

```python
# When your agent generates a response
response_text = "The weather in Paris is sunny, 22 degrees."

# Queue for TTS (if using direct integration)
pipeline.tts_queue.put(response_text)

# Or write to TTS file
with open("~/.openclaw/voice/tts_output.txt", "w") as f:
    f.write(response_text)
```

The voice system will:
1. Generate speech audio (edge-tts)
2. Set `is_speaking_tts = True` (mutes mic)
3. Play the audio
4. Set `is_speaking_tts = False` (unmutes mic)

## Window Targeting

### How It Works (macOS)

The system uses AppleScript to send keystrokes to specific processes:

```applescript
-- Priority 1: VSCode (most common for Claude Code)
if (name of processes) contains "Code" then
    keystroke "command text"
    keystroke return
end if

-- Priority 2: Terminal
if (name of processes) contains "Terminal" then
    keystroke "command text"
    keystroke return
end if
```

**Benefits:**
- ✅ No window switching required
- ✅ Works while user is in other apps
- ✅ Fast (~100ms delivery)
- ✅ Reliable targeting

**Requirements:**
- macOS Accessibility permissions
- VSCode or Terminal running
- Target app has an input field ready

### Fallback Behavior

If AppleScript fails (non-macOS, permissions issue):
```python
import pyautogui

# Types into currently focused window
pyautogui.write(text, interval=0)
pyautogui.press('enter')
```

## Troubleshooting

### Issue: Commands not appearing

**Check:**
1. Is VSCode/Terminal running? `ps aux | grep -i "code\|terminal"`
2. Accessibility permissions granted? System Preferences → Security → Privacy → Accessibility
3. Is the voice system running? Look for the audio visualizer

**Fix:**
```bash
# Check if voice system is running
ps aux | grep "main.py"

# Restart voice system
./start_voice_system.sh
```

### Issue: Commands going to wrong window

**Cause:** AppleScript can't find target process

**Fix:**
- Ensure VSCode is running: `open -a "Visual Studio Code"`
- Or use fallback mode: Click on your agent's window before speaking

### Issue: Slow transcription

**Causes:**
- Large model selected (`base`, `small`)
- Long segment duration (>3s)
- CPU-only mode (no GPU acceleration)

**Fix:**
```bash
# Use fastest configuration
python main.py --model tiny --duration 1.5
```

### Issue: Echo/feedback loop

**Cause:** TTS enabled but speaking flag not working

**Fix:**
- Update to latest version (has echo prevention)
- Or disable TTS temporarily: `python main.py` (without --tts)

### Issue: Poor transcription accuracy

**Causes:**
- Background noise
- Threshold too high (missing speech)
- Model too small

**Fix:**
```bash
# Use better model + lower threshold
python main.py --model base --threshold 300
```

## Performance Benchmarks

Tested on Apple M1 Max:

| Model | Segment | Latency | Accuracy | Use Case |
|-------|---------|---------|----------|----------|
| tiny  | 1.5s    | 0.5-1.0s | 85-90% | Fast commands |
| tiny  | 3.0s    | 1.0-1.5s | 90-95% | Default |
| base  | 3.0s    | 1.5-2.5s | 95-98% | High accuracy |
| small | 3.0s    | 3.0-4.0s | 98-99% | Production |

**Recommendation:** Start with `tiny` + `1.5s`. Upgrade to `base` if accuracy issues occur.

## API Reference

### UltraFastVoicePipeline

```python
class UltraFastVoicePipeline:
    def __init__(
        self,
        output_dir='~/.openclaw/voice',
        model_size='tiny',
        segment_duration=1.5,
        speech_threshold=500,
        sample_rate=16000,
        enable_tts=False
    ):
        """
        Initialize voice pipeline

        Args:
            output_dir: Directory for logs and TTS files
            model_size: Whisper model (tiny, base, small, medium)
            segment_duration: Seconds to capture before transcribing
            speech_threshold: Amplitude threshold (100-2000)
            sample_rate: Audio sample rate (16000 recommended)
            enable_tts: Enable text-to-speech output
        """

    def start(self):
        """Start the voice pipeline (blocking)"""

    def stop(self):
        """Stop the voice pipeline"""
```

### Key Attributes

```python
pipeline.is_speaking_tts      # Bool: TTS currently active
pipeline.current_amplitude    # Float: Current audio level
pipeline.transcription_count  # Int: Total transcriptions
pipeline.segment_duration     # Float: Segment length in seconds
```

## Security Considerations

### Permissions Required (macOS)

1. **Microphone Access**
   - Required for audio capture
   - Requested on first run

2. **Accessibility Permissions**
   - Required for AppleScript keystroke injection
   - Must be granted manually in System Preferences

### Privacy

- All transcription happens **locally** (no cloud API calls)
- Audio is processed in memory (not saved to disk by default)
- Transcription logs stored in `~/.openclaw/voice/` (optional)

### Sensitive Data

⚠️ **Important:** The voice system types commands into your agent. If your agent logs input:
- Voice commands will be logged
- Consider PII/sensitive data in voice commands
- Review your agent's logging configuration

## Best Practices

### For Agent Developers

1. **Handle fragmented input gracefully**
   - Voice transcription isn't perfect
   - Implement fuzzy matching for commands
   - Provide helpful error messages

2. **Provide feedback**
   - Acknowledge receipt of commands
   - Use TTS for confirmation (if enabled)
   - Visual indicators in your UI

3. **Command design**
   - Use clear, distinct command phrases
   - Avoid ambiguous words (e.g., "to/two/too")
   - Support variations (e.g., "stop" = "halt" = "quit")

4. **Testing**
   ```python
   # Test with mock input instead of live voice
   test_commands = [
       "show me the logs",
       "restart the service",
       "what's the status"
   ]

   for cmd in test_commands:
       agent.process_input(cmd)
   ```

### For Users

1. **Speak clearly** - Enunciate commands
2. **Wait for silence** - System captures segments of speech
3. **Check visualizer** - Green = speech detected
4. **Short phrases work best** - 3-10 words per command

## Example Integration

Here's a complete example of integrating Open Ears with a custom agent:

```python
#!/usr/bin/env python3
"""
Example: Custom agent with Open Ears integration
"""

from src.core.voice_pipeline import UltraFastVoicePipeline
import queue
import threading

class MyAgent:
    def __init__(self):
        self.command_queue = queue.Queue()
        self.running = False

    def process_command(self, command):
        """Process a voice command"""
        print(f"🎤 Received: {command}")

        # Your agent logic here
        if "weather" in command.lower():
            response = "The weather is sunny!"
        elif "time" in command.lower():
            response = "It's 3 PM"
        else:
            response = f"I heard: {command}"

        print(f"🤖 Response: {response}")
        return response

    def start_voice_integration(self):
        """Start listening for voice commands"""

        def custom_input_handler(text):
            """Called when voice system transcribes text"""
            self.command_queue.put(text)

        # Create voice pipeline
        pipeline = UltraFastVoicePipeline(
            model_size='tiny',
            segment_duration=1.5,
            enable_tts=True
        )

        # Override the default keystroke behavior
        pipeline._send_to_openclaw_tui = custom_input_handler

        # Start voice system in separate thread
        voice_thread = threading.Thread(
            target=pipeline.start,
            daemon=True
        )
        voice_thread.start()

        # Process commands from queue
        print("✅ Voice integration active!")
        while self.running:
            try:
                command = self.command_queue.get(timeout=0.5)
                response = self.process_command(command)

                # Queue response for TTS
                if pipeline.enable_tts:
                    pipeline.tts_queue.put(response)

            except queue.Empty:
                continue

# Usage
agent = MyAgent()
agent.running = True
agent.start_voice_integration()
```

## Conclusion

Open Ears provides a complete voice input solution for AI agents with:
- ✅ Zero-configuration integration for VSCode/Terminal agents
- ✅ Flexible APIs for custom integrations
- ✅ Optimized performance (sub-second latency)
- ✅ Echo prevention for TTS-enabled agents
- ✅ Local processing (privacy-friendly)

**Next Steps:**
1. Run `./start_voice_system.sh` to test
2. Speak commands to your agent
3. Customize configuration as needed
4. (Optional) Implement custom integration for advanced features

For issues or questions, see the troubleshooting section or open an issue on GitHub.

---

**Version:** 1.0.0
**Last Updated:** 2025-02-01
**Compatibility:** macOS (primary), Linux/Windows (fallback mode)
