# Molt Speak

Voice integration for AI agents on macOS. Talk to your AI, hear it respond.

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.9+
- An AI agent running in Terminal (e.g., OpenClaw TUI, Claude Code)

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/jamescodes84/molt-speak/main/install.sh | bash
```

## Usage

1. **Start your AI agent** in a Terminal window
2. **Launch Molt Speak**:
   ```bash
   molt-speak start
   ```
3. **Start talking** - your voice is transcribed and sent to the agent
4. **Listen** - the agent's responses are spoken aloud

### Commands

| Command | Description |
|---------|-------------|
| `molt-speak start` | Open menu bar app and start voice loop |
| `molt-speak stop` | Stop the voice loop (menu bar stays open) |
| `molt-speak quit` | Quit everything |
| `molt-speak status` | Check if voice loop is running |
| `molt-speak update` | Update to latest version |

## Menu Bar App

Once running, you'll see a lobster icon in your menu bar:

- **🔴🦞** = Voice loop stopped
- **🟢🦞** = Voice loop active

Click to access:
- Start/Stop voice loop
- Change voice (Samantha, Daniel, etc.)
- Toggle honorific (Sir/Madam)
- View logs

## How It Works

```
You speak → Ears transcribes → Types into agent terminal
                                      ↓
You hear ← Mouth speaks ← Agent writes response
```

**Echo Prevention**: When the agent speaks, your microphone automatically pauses to prevent feedback loops.

## File Locations

All runtime files are stored in `~/openclaw-workspace/molt-speak/app/runtime/`:

| File | Purpose |
|------|---------|
| `speech_output.txt` | Agent writes here to speak |
| `mouth_status.txt` | Tracks speaking state |
| `ears_pause.signal` | Pauses mic during playback |

## Agent Integration

For your AI agent to speak, it writes to the speech output file:

```bash
echo "Hello! How can I help you?" >> /tmp/speak.txt
```

Or in Python:
```python
with open("/tmp/speak.txt", "a") as f:
    f.write("Hello! How can I help you?\n")
```

## Troubleshooting

### Voice loop won't start

1. Make sure your AI agent is running in Terminal first
2. Check that Terminal has microphone permissions (System Settings → Privacy & Security → Microphone)

### Can't hear speech

1. Check your system volume
2. Verify the speech file exists: `ls ~/openclaw-workspace/molt-speak/app/runtime/speech_output.txt`

### Permission denied errors

Run a clean reinstall:
```bash
molt-speak quit
rm -rf ~/openclaw-workspace/molt-speak/app
molt-speak update
molt-speak start
```

### Echo/feedback issues

The system should automatically pause your mic when the agent speaks. If you hear echo:
1. Stop and restart: `molt-speak stop && molt-speak start`
2. Check logs: Click menu bar → View Logs

## Uninstall

```bash
molt-speak quit
rm -rf ~/openclaw-workspace/molt-speak/app
sudo rm /usr/local/bin/molt-speak
```

---

## Developer Information

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Molt Speak System                   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │  Ears    │    │  Mouth   │    │ Coordinator  │  │
│  │  (STT)   │    │  (TTS)   │    │ (Echo Prev)  │  │
│  └──────────┘    └──────────┘    └──────────────┘  │
│       ↓               ↑                ↕            │
│  Transcribes     Speaks text      Monitors &       │
│  your voice      from file        signals pause    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Components

| Component | Directory | Purpose |
|-----------|-----------|---------|
| Ears | `open_ears/` | Speech-to-text using Whisper |
| Mouth | `open_mouth/` | Text-to-speech using macOS voices |
| Coordinator | `src/` | Echo prevention coordination |
| Menu Bar | `unified_menu_bar.py` | GUI control interface |

### Running Components Separately

For development, you can run each component in its own terminal:

**Terminal 1 - Coordinator**:
```bash
python main.py
```

**Terminal 2 - Mouth**:
```bash
cd open_mouth && python main.py --local --voice Samantha
```

**Terminal 3 - Ears**:
```bash
cd open_ears && python main.py
```

### Configuration

Create a `.env` file to customize behavior:

```bash
# Integration
ENABLE_INTEGRATION=true

# Monitoring
MOUTH_STATUS_POLL_INTERVAL=0.1    # Poll every 100ms
MOUTH_STATUS_DEBOUNCE_MS=200      # 200ms debounce after speaking

# Logging
LOG_LEVEL=INFO
```

### Signal File Format

**mouth_status.txt**:
```
2026-02-01T12:15:24.161586|SPEAKING|Hello, this is a test
2026-02-01T12:15:25.167795|IDLE|
```

**ears_pause.signal**: Unix timestamp (file existence = pause mic)

---

## Terms & Conditions

**USE AT YOUR OWN RISK**

This software is provided "as is", without warranty of any kind, express or implied. By using Molt Speak, you acknowledge and agree that:

- The software may have bugs, errors, or unexpected behavior
- Voice recognition and text-to-speech accuracy is not guaranteed
- The developers are not responsible for any damages, data loss, or issues arising from use of this software
- You are solely responsible for ensuring the software meets your needs
- Audio recording features require appropriate permissions and should be used in compliance with applicable laws
- This software is not intended for use in critical, medical, or safety-related applications

Use of this software constitutes acceptance of these terms.

---

## License

MIT License

## Contributing

Issues and PRs welcome at [github.com/jamescodes84/molt-speak](https://github.com/jamescodes84/molt-speak)
