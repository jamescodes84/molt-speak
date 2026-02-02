# OpenClaw Mouth 🎙️

**Text-to-Speech Output System for AI Agents**

OpenClaw Mouth is the speech OUTPUT companion to OpenClaw Ears (voice INPUT). It converts text written by AI agents into natural-sounding speech, completing the voice interaction loop.

## Overview

```
Agent writes text → File monitoring → Edge-TTS synthesis → Speaker output
```

OpenClaw Mouth monitors a text file (`~/.openclaw/speech_output.txt`) for new content and automatically converts it to speech using Microsoft Edge's high-quality Text-to-Speech engine.

## Features

- **Real-time TTS** - <1 second latency from text to speech
- **High-quality voices** - Multiple natural-sounding voices via Edge-TTS
- **Terminal visualization** - Embedded display showing speaking status
- **Speaking signal** - Notifies OpenClaw Ears when agent is speaking to avoid echo
- **Queue management** - Handles rapid message streams
- **Simple integration** - Just write to a file, no code changes needed
- **Zero configuration** - Works out of the box with sensible defaults
- **Companion to Ears** - Runs alongside OpenClaw Ears for full voice conversation

## Quick Start

### 1. Install

```bash
git clone https://github.com/jamescodes84/open_mouth.git
cd open_mouth
./start_speech_system.sh
```

The startup script will:
- Create a virtual environment
- Install all dependencies
- Create the input file
- Start the speech system

### 2. Test It

In another terminal:

```bash
echo "Hello! I am OpenClaw Mouth." >> ~/.openclaw/speech_output.txt
```

You should hear the text spoken through your speakers!

### 3. Integration

For AI agents, see [AGENT_INSTRUCTIONS.txt](AGENT_INSTRUCTIONS.txt) for detailed integration guide.

## Terminal Display

When running, you'll see a live visualization:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Status: 📢 SPEAKING                                                          │
│ Text: Hello! How can I help you today?                                      │
│ Progress: [████████████████████████████░░░░░░░░░░░░░░] 75%                  │
│ Voice: ChristopherNeural                                                     │
│ Queue: 2 item(s)                                                             │
│ Total spoken: 15                                                             │
│ Last update: 14:23:45                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Usage

### Basic Usage

```bash
# Start with defaults
./start_speech_system.sh

# Use a different voice
./start_speech_system.sh --voice en-US-AriaNeural

# Adjust speech speed
./start_speech_system.sh --rate 1.2

# Use custom input file
./start_speech_system.sh --input /path/to/custom/file.txt

# Compact display mode (single line)
./start_speech_system.sh --compact

# Debug mode
./start_speech_system.sh --log-level DEBUG
```

### Available Voices

List all available voices:

```bash
python3 main.py --list-voices
```

Common voices:
- `en-US-ChristopherNeural` (male, default)
- `en-US-AriaNeural` (female)
- `en-US-JennyNeural` (female)
- `en-US-GuyNeural` (male)
- `en-US-DavisNeural` (male)
- `en-US-AmberNeural` (female)

### Writing Text for Speech

From command line:

```bash
echo "Your text here" >> ~/.openclaw/speech_output.txt
```

From Python:

```python
from pathlib import Path

def speak(text: str) -> None:
    """Send text to OpenClaw Mouth."""
    speech_file = Path.home() / ".openclaw" / "speech_output.txt"
    with open(speech_file, "a") as f:
        f.write(f"{text}\n")

speak("Hello from Python!")
```

From Bash script:

```bash
#!/bin/bash
SPEECH_FILE="$HOME/.openclaw/speech_output.txt"

speak() {
    echo "$1" >> "$SPEECH_FILE"
}

speak "Starting the process"
speak "Processing complete"
```

## Configuration

### Environment Variables

Create a `.env` file (optional):

```bash
# Voice Configuration
TTS_VOICE=en-US-ChristopherNeural
TTS_RATE=1.0                    # 0.5 to 2.0 (1.0 = normal speed)
TTS_VOLUME=1.0                  # 0.0 to 1.0
TTS_PITCH=0.0                   # -100 to +100 Hz

# Input Configuration
INPUT_FILE=~/.openclaw/speech_output.txt
MONITOR_INTERVAL=0.1            # How often to check file (seconds)

# Queue Configuration
MAX_QUEUE_SIZE=10               # Maximum queued messages

# Logging
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=                       # Optional: path to log file

# Display
DISPLAY_UPDATE_RATE=0.05        # 20Hz refresh rate
ENABLE_COLORS=true
```

### Command-Line Options

All environment variables can be overridden via command-line:

```bash
python3 main.py --help
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenClaw Mouth Pipeline                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Thread 1: Text Monitor                                     │
│    └─> Watches ~/.openclaw/speech_output.txt                │
│        Detects new lines → Queue for synthesis              │
│                                                              │
│  Thread 2: Synthesis Worker                                 │
│    └─> Takes text from queue                                │
│        Synthesizes with Edge-TTS → Audio queue              │
│                                                              │
│  Thread 3: Audio Playback                                   │
│    └─> Takes audio from queue                               │
│        Plays through speakers                               │
│                                                              │
│  Thread 4: Terminal Display                                 │
│    └─> Updates visualization at 20Hz                        │
│        Shows status, progress, queue                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
open_mouth/
├── main.py                      # Entry point
├── start_speech_system.sh       # One-command startup
├── AGENT_INSTRUCTIONS.txt       # Integration guide for AI agents
├── SPEAKING_SIGNAL.md           # Speaking signal documentation
├── monitor_speaking_status.py   # Monitor tool for signal file
├── test_signal.py               # Signal file testing script
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env.example                 # Configuration template
└── src/
    ├── core/
    │   ├── mouth_pipeline.py    # Main orchestration
    │   ├── terminal_visualizer.py  # Display rendering
    │   └── state_manager.py     # State management
    ├── services/
    │   ├── tts_service.py       # Edge-TTS integration
    │   ├── audio_playback.py    # Speaker output
    │   └── text_monitor.py      # File monitoring
    ├── config/
    │   └── settings.py          # Configuration
    └── utils/
        ├── logging_utils.py     # Logging helpers
        └── openclaw_notifier.py # Speaking signal implementation
```

## Integration with OpenClaw Ears

For full voice conversation, run both systems:

**Terminal 1 - Voice Output:**
```bash
cd /path/to/open_mouth
./start_speech_system.sh
```

**Terminal 2 - Voice Input:**
```bash
cd /path/to/open_ears
./start_voice_system.sh
```

**Terminal 3 - Your Agent:**
```bash
# Run your agent that:
# - Reads voice input from OpenClaw Ears
# - Writes voice output to OpenClaw Mouth
```

Now you have a complete voice conversation loop:
```
User speaks → Ears → Agent → Mouth → User hears
```

### Speaking Signal for Coordination

OpenClaw Mouth automatically creates a signal file at `~/.openclaw/mouth_status.txt` that indicates when the agent is speaking. OpenClaw Ears can monitor this file to pause listening while the agent speaks, preventing the system from hearing its own voice.

**Visual Indicators:**
- When speaking, the terminal shows a **prominent green banner**: "🔊 AGENT SPEAKING - EARS SHOULD PAUSE 🔊"
- The border changes to a bright green double-line style (═)
- Compact mode shows a bold "🔊 AGENT SPEAKING" indicator

**For Integration:**
See [SPEAKING_SIGNAL.md](SPEAKING_SIGNAL.md) for complete documentation on:
- Signal file format
- How to monitor the speaking status
- Code examples for integration
- Best practices and troubleshooting

**Quick Monitor:**
Watch the speaking signal in real-time:
```bash
./monitor_speaking_status.py
```

## Requirements

- Python 3.10+
- macOS (uses `afplay` for audio)
  - Linux: Install `mpg123` or modify [audio_playback.py](src/services/audio_playback.py)
  - Windows: Install `mpg123` or use Windows Media Player
- Internet connection (Edge-TTS is cloud-based)

## Dependencies

All dependencies are installed automatically by the startup script:

- `edge-tts` - Text-to-speech synthesis
- `sounddevice` - Audio playback (optional, alternative backend)
- `watchdog` - File system monitoring
- `python-dotenv` - Environment configuration

See [requirements.txt](requirements.txt) for full list.

## Troubleshooting

### No audio output

1. Check system volume is not muted
2. Verify `afplay` works: `afplay /System/Library/Sounds/Ping.aiff`
3. Check terminal for error messages

### Text not being spoken

1. Verify file path: `ls -la ~/.openclaw/speech_output.txt`
2. Check you're using append (`>>`) not overwrite (`>`)
3. Ensure speech system is running (terminal window open)

### Slow performance

1. Check your internet connection (Edge-TTS requires network)
2. Reduce speech rate: `--rate 0.8`
3. Check queue size in terminal display

### Voice not found

1. List available voices: `python3 main.py --list-voices`
2. Verify voice ID is correct (case-sensitive)
3. Internet connection required to fetch voices

## Performance

- **Latency**: <1 second from text write to audio start
- **CPU (idle)**: <5%
- **CPU (active)**: 15-30% (synthesis + playback)
- **Memory**: ~100-200MB
- **Network**: ~50-100KB per utterance (Edge-TTS API calls)

## For OpenClaw Agents

**IMPORTANT:** This speech system is complete and production-ready.

✅ **DO:** Use it by writing to `~/.openclaw/speech_output.txt`

❌ **DO NOT:** Modify the Python code or try to "improve" it

See [AGENT_INSTRUCTIONS.txt](AGENT_INSTRUCTIONS.txt) for complete integration guide.

## License

MIT License - See LICENSE file

## Related Projects

- [OpenClaw Ears](https://github.com/jamescodes84/open_ears) - Voice input system (companion project)
- [OpenClaw](https://github.com/jamescodes84/openclaw) - Full AI agent framework

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- Issues: [GitHub Issues](https://github.com/jamescodes84/open_mouth/issues)
- Discussions: [GitHub Discussions](https://github.com/jamescodes84/open_mouth/discussions)

## Acknowledgments

- Microsoft Edge TTS team for the excellent TTS API
- OpenClaw Ears project for the architectural inspiration
- The open-source community for dependencies

---

Made with ❤️ for the OpenClaw ecosystem
