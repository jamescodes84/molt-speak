# OpenClaw Mouth - Menu Bar Voice Control Guide

## Overview

The OpenClaw Mouth system now includes a native macOS menu bar application for easy voice control without restarting the system.

## Features

- ✅ **Runtime Voice Switching**: Change voices on-the-fly without restarting
- ✅ **Local & Cloud Voices**: Support for both macOS `say` voices and Edge-TTS cloud voices
- ✅ **Favorites**: Mark your favorite voices for quick access
- ✅ **Voice Persistence**: Your last used voice is saved and restored
- ✅ **Real-time Status**: See when the system is speaking or idle
- ✅ **Voice Search**: Quickly find voices by name
- ✅ **Auto-reconnect**: Gracefully handles connection loss

## Installation

1. Install dependencies:
```bash
cd /Users/albus/Documents/Coding\ Workspace/open_mouth/open_mouth
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### 1. Start OpenClaw Mouth with Control Server

Start the main TTS system with the `--enable-control` flag:

```bash
./start_speech_system.sh --enable-control --local
```

Or with cloud TTS:

```bash
./start_speech_system.sh --enable-control
```

### 2. Launch the Menu Bar App

In a separate terminal:

```bash
cd /Users/albus/Documents/Coding\ Workspace/open_mouth/open_mouth
source venv/bin/activate
python scripts/launch_menu_bar.py
```

The menu bar icon (🎙️) will appear in your macOS menu bar.

### 3. Using the Menu Bar

Click the 🎙️ icon to access:

- **Current Voice**: Shows the currently active voice
- **Status**: Shows if the system is IDLE, SPEAKING, or QUEUED
- **⚡ Local Voices**: macOS voices (Alex, Samantha, etc.)
- **☁️ Cloud Voices**: Edge-TTS voices (Aria, Christopher, etc.)
- **★ Favorites**: Your favorite voices for quick access
- **Add to Favorites**: Save the current voice
- **🔄 Refresh Voices**: Update the voice list from system/cloud

## Menu Bar Icon States

- 🎙️ - Idle/Ready
- 🎙️ 🔊 - Currently speaking
- 🎙️ ⚠️ - Not connected to OpenClaw Mouth

## Testing

### Quick Test

1. Start OpenClaw Mouth:
```bash
./start_speech_system.sh --enable-control --local
```

2. Launch menu bar app:
```bash
python scripts/launch_menu_bar.py
```

3. Select a voice from the menu (e.g., "Samantha")

4. Test speech:
```bash
python claude_speak.py "Hello, I am testing the new voice"
```

5. Verify the speech uses the new voice!

### Manual Socket Test

You can test the control server directly:

```bash
# Ping test
echo "PING" | nc -U ~/.openclaw/mouth_control.sock
# Should return: OK:PONG

# Get status
echo "GET_STATUS" | nc -U ~/.openclaw/mouth_control.sock
# Should return: OK:IDLE|VoiceName|mode|

# Change voice
echo "CHANGE_VOICE:Samantha,local" | nc -U ~/.openclaw/mouth_control.sock
# Should return: OK:Voice changed to Samantha
```

## Configuration Files

### Voice Preferences
`~/.openclaw/voice_preferences.json`

Stores:
- Last used voice and mode
- Favorite voices
- Recent voices
- Speech rate and volume preferences

### Voice Cache
`~/.openclaw/voice_cache.json`

Caches:
- Local voice list (refreshed every 24 hours)
- Cloud voice list (refreshed every 24 hours)

## Architecture

```
┌─────────────────┐
│   Menu Bar App  │
│      (rumps)    │
└────────┬────────┘
         │
         ├─ VoiceManager (lists voices)
         ├─ ControlClient (sends commands)
         └─ VoiceConfig (saves preferences)
         │
         ▼
┌─────────────────┐
│  Unix Socket    │
│ ~/.openclaw/    │
│ mouth_control   │
│     .sock       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MouthPipeline  │
│ ControlServer   │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   TTS Service   │
│ (Local/Cloud)   │
└─────────────────┘
```

## Command Protocol

### Available Commands

- `PING` - Health check
- `GET_STATUS` - Get current status, voice, mode
- `CHANGE_VOICE:voice[,mode]` - Change voice
- `CHANGE_RATE:float` - Change speech rate
- `CHANGE_VOLUME:float` - Change volume

### Response Format

```
OK:message    - Success
ERROR:message - Failure
```

## Troubleshooting

### Menu Bar App Won't Connect

1. Ensure OpenClaw Mouth is running with `--enable-control`:
```bash
./start_speech_system.sh --enable-control --local
```

2. Check socket exists:
```bash
ls -la ~/.openclaw/mouth_control.sock
```

3. Test socket manually:
```bash
echo "PING" | nc -U ~/.openclaw/mouth_control.sock
```

### Voice Change Not Working

1. Check logs for errors
2. Verify voice name is correct:
```bash
say -v "?" | grep -i samantha  # For local voices
```

3. Test voice manually:
```bash
say -v Samantha "Hello"  # For local voices
```

### Menu Bar Icon Not Appearing

1. Ensure rumps is installed:
```bash
pip install rumps pyobjc-framework-Cocoa
```

2. Check for macOS permission issues:
- System Settings > Privacy & Security > Accessibility

## Tips

1. **Use Local Voices for Speed**: Local voices (--local flag) have near-instant playback
2. **Use Cloud Voices for Quality**: Cloud voices offer more natural speech but require internet
3. **Create Favorites**: Add your most-used voices to favorites for quick access
4. **Keyboard Shortcuts**: Consider creating macOS keyboard shortcuts to launch the menu bar app

## Future Enhancements

Potential features for future versions:
- Voice preview (test a voice before switching)
- Speech rate slider in menu
- Volume control in menu
- Voice search/filter
- Voice categories (by language, gender, etc.)
- Auto-start on login (launchd)
- Standalone .app bundle

## Files Added

### Control Protocol
- `src/control/__init__.py`
- `src/control/command_protocol.py`
- `src/control/control_server.py`

### GUI Components
- `src/gui/__init__.py`
- `src/gui/menu_bar_app.py`
- `src/gui/voice_manager.py`
- `src/gui/control_client.py`

### Configuration
- `src/config/voice_config.py`

### Scripts
- `scripts/launch_menu_bar.py`

### Documentation
- `MENU_BAR_GUIDE.md` (this file)

## Support

For issues or questions, check:
- Console logs from OpenClaw Mouth
- Console logs from menu bar app
- Socket connection with `nc` commands above
