# Molt Speak 🦞🤖

Introducing Molt Speak, the free app designed to allow Moltys (Clawd Bots) to actually speak to their Humans.

Stop typing. Start talking. Molt Speak 🦞🤖

NEW FEATURES RELEASED 2/6/26: og users run "molt-speak update" for the latest enhancements

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.9+
- An AI agent running in Terminal (e.g., OpenClaw TUI, Claude Code)

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/jamescodes84/molt-speak/main/install.sh | bash
```

> **Note:** You may see "OpenSpeak" in installer output — this is the same product as Molt Speak.

## Usage

1. **Start your AI agent** in a Terminal window
2. **Launch Molt Speak**:
   ```bash
   moltspeak start
   ```
3. **Start talking** — your voice is transcribed and sent to the agent
4. **Listen** — the agent's responses are spoken aloud

### Commands

| Command | Description |
|---------|-------------|
| `moltspeak start` | Open menu bar app and start voice loop |
| `moltspeak stop` | Stop the voice loop (menu bar stays open) |
| `moltspeak quit` | Quit everything |
| `moltspeak status` | Check if voice loop is running |
| `moltspeak logs` | View logs (`moltspeak logs audio` or `moltspeak logs integration`) |
| `moltspeak update` | Update to latest version |
| `moltspeak elapi` | Set ElevenLabs API key |
| `moltspeak kill` | Force-kill all processes (use if stuck) |

## Menu Bar App

Once running, you'll see a lobster icon in your menu bar:

- **🔴🦞** = Voice loop stopped
- **🟢🦞** = Voice loop active

Click to access:
- Start/Stop voice loop
- Select TTS provider (Edge-TTS free / ElevenLabs premium)
- Change voice (24+ Edge-TTS voices across 6 English accents)
- Adjust microphone sensitivity (Low / Medium / High / Max)
- Adjust barge-in sensitivity (Off / Low / Medium / High)
- Set honorific (Sir / Madam / Custom text)
- Check for updates
- View logs

## Voices & TTS Providers

### Edge-TTS (Default, Free)

No API key required. Default voice: `en-US-ChristopherNeural`.

| Region | Voices |
|--------|--------|
| American | ChristopherNeural, AriaNeural, JennyNeural, GuyNeural, DavisNeural, AmberNeural, AnaNeural, BrandonNeural, CoraNeural, EricNeural |
| British | RyanNeural, SoniaNeural, LibbyNeural, ThomasNeural, MaisieNeural |
| Australian | NatashaNeural, WilliamNeural |
| Irish | EmilyNeural, ConnorNeural |
| South African | LeahNeural, LukeNeural |
| Indian | NeerjaNeural, PrabhatNeural |

### ElevenLabs (Premium)

High-quality AI voices. Requires an API key:

```bash
moltspeak elapi
```

Uses the `eleven_turbo_v2_5` model for low latency. Voice list is loaded dynamically from your ElevenLabs account.

### Local macOS (Developer/Fallback)

Uses the macOS `say` command (Alex, Samantha, Daniel, etc.). Available when running the Mouth component directly for development.

## Configuration

### Runtime Config

Most settings are accessible from the menu bar. They are stored in `runtime/molt_speak_config.json`:

```json
{
  "preferred_voice": "en-US-ChristopherNeural",
  "user_title": "sir",
  "tts_provider": "edge-tts",
  "elevenlabs_api_key": null,
  "elevenlabs_voice_id": "21m00Tcm4TlvDq8ikWAM",
  "elevenlabs_model": "eleven_turbo_v2_5",
  "mic_sensitivity": "medium",
  "barge_sensitivity": "medium"
}
```

### Environment Variables

Create a `.env` file in the install directory to customize advanced behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_INTEGRATION` | `true` | Enable echo prevention coordinator |
| `ENABLE_BIDIRECTIONAL` | `false` | Pause Mouth when Ears is transcribing (experimental) |
| `MOUTH_STATUS_POLL_INTERVAL` | `0.1` | Poll frequency in seconds |
| `MOUTH_STATUS_DEBOUNCE_MS` | `200` | Debounce delay after speech stops |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FILE` | _(none)_ | Optional log file path |
| `MAX_QUEUE_SIZE` | `10` | Transcription queue size |
| `PROCESSING_TIMEOUT` | `30.0` | Processing timeout in seconds |
| `POSTHOG_DISABLED` | `false` | Set to `true` to disable analytics |

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
| `molt_speak_config.json` | User preferences (voice, provider, sensitivity) |

## Agent Integration

For your AI agent to speak, it writes to the speech output file:

```bash
echo "Hello! How can I help you?" >> ~/openclaw-workspace/molt-speak/app/runtime/speech_output.txt
```

Or in Python:
```python
from pathlib import Path

speech_file = Path.home() / "openclaw-workspace/molt-speak/app/runtime/speech_output.txt"
with open(speech_file, "a") as f:
    f.write("Hello! How can I help you?\n")
```

## Troubleshooting

### Voice loop won't start

1. Make sure your AI agent is running in Terminal first
2. Check that Terminal has microphone permissions (System Settings → Privacy & Security → Microphone)

### Can't hear speech

1. Check your system volume
2. Verify the speech file exists: `ls ~/openclaw-workspace/molt-speak/app/runtime/speech_output.txt`

### Update stuck on old version

If `moltspeak update` doesn't pick up the latest version, do a clean reinstall:
```bash
moltspeak kill
rm -rf ~/openclaw-workspace/molt-speak
curl -fsSL https://raw.githubusercontent.com/jamescodes84/molt-speak/main/install.sh | bash
```
Your runtime config (voice, provider, sensitivity) will be preserved automatically.

### Permission denied errors

Run a clean reinstall:
```bash
moltspeak quit
rm -rf ~/openclaw-workspace/molt-speak/app
moltspeak update
moltspeak start
```

### Echo/feedback issues

The system should automatically pause your mic when the agent speaks. If you hear echo:
1. Stop and restart: `moltspeak stop && moltspeak start`
2. Check logs: Click menu bar → View Logs

### Processes stuck / won't quit

If the voice loop won't stop normally:
```bash
moltspeak kill
```

## Uninstall

```bash
moltspeak quit
rm -rf ~/openclaw-workspace/molt-speak/app
sudo rm /usr/local/bin/moltspeak
# Optional: Remove analytics data
rm -rf ~/Library/Application\ Support/molt-speak/
```

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 0.1.0 | 2026-02-06 | Initial foundation — Whisper STT, Edge-TTS, echo prevention coordinator, macOS menu bar app, PostHog analytics |
| 0.5.0 | 2026-02-06 | Stability & polish — Persistent analytics across uninstalls, daily active user heartbeat, voice selection fixes, async/sync corrections |
| 0.9.0 | 2026-02-06 | Command rename `molt-speak` → `moltspeak`, ElevenLabs premium TTS, CodeRabbit CI integration, lint & error handling fixes |
| 1.0.0 | 2026-02-06 | Public release — Custom honorific text input, privacy section, mic & barge-in sensitivity tuning, 24+ Edge-TTS voices, full documentation |
| 1.0.5 | 2026-02-10 | Update fix — Fixed update dialog crash (NSWindow threading), hardened install script with fresh-clone fallback, fixed PostHog analytics (flush before exit, correct identify API, explicit API key passthrough) |

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
| Mouth | `open_mouth/` | Text-to-speech using Edge-TTS / ElevenLabs |
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
cd open_mouth && python main.py
```

**Terminal 3 - Ears**:
```bash
cd open_ears && python main.py
```

### Signal File Format

**mouth_status.txt**:
```
2026-02-01T12:15:24.161586|SPEAKING|Hello, this is a test
2026-02-01T12:15:25.167795|IDLE|
```

**ears_pause.signal**: Unix timestamp (file existence = pause mic)

---

## Privacy & Analytics

### What We Track

Molt Speak uses PostHog analytics to understand usage patterns and improve the product. We track:

- **Installation & Updates** — When you install or update the app
- **Session Duration** — How long you use the app
- **Feature Usage** — Which features you use (voice input, output, etc.)
- **Performance Metrics** — Transcription times, synthesis times
- **Anonymous User ID** — A randomly generated UUID (not linked to your identity)

Analytics state (anonymous ID, session counts) persists in `~/Library/Application Support/molt-speak/` and survives reinstalls. Remove this directory to fully clear analytics data.

### What We DON'T Track

- No transcribed speech content
- No text-to-speech content
- No personal information (name, email, etc.)
- No file contents or system information beyond platform type
- No IP addresses (PostHog anonymizes these)

### Opting Out

To disable analytics entirely, edit your `.env` file:

```bash
POSTHOG_DISABLED=true
```

Restart Molt Speak after changing this setting. The app functions identically with analytics disabled.

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

---

## Appendix A: Legacy Commands

Prior versions of Molt Speak used the hyphenated command `molt-speak`. The current command is `moltspeak` (no hyphen). If you have an older installation, the legacy command may still work.

| Legacy Command | Current Command |
|----------------|-----------------|
| `molt-speak start` | `moltspeak start` |
| `molt-speak stop` | `moltspeak stop` |
| `molt-speak quit` | `moltspeak quit` |
| `molt-speak status` | `moltspeak status` |
| `molt-speak update` | `moltspeak update` |

To ensure you're using the latest command, run `moltspeak update`.
