# Molt Speak Installation

## Quick Install

### Install from Main (Stable)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/jamescodes84/molt-speak/main/install.sh)
```

### Install from Develop (Latest Features)

Install the develop branch for testing latest features including ElevenLabs integration:

```bash
BRANCH=develop bash <(curl -fsSL https://raw.githubusercontent.com/jamescodes84/molt-speak/main/install.sh)
```

## What Gets Installed

- Molt Speak voice loop system at `~/open-claw-workspace/molt-speak/app`
- `molt-speak` command-line tool
- All Python dependencies in a virtual environment
- Required system dependencies (ffmpeg, portaudio)

## Post-Installation

After installation, you can use these commands:

```bash
# Start the menu bar app (recommended)
molt-speak start

# Configure ElevenLabs TTS (premium voices)
molt-speak elo

# Stop the voice loop
molt-speak stop

# Check status
molt-speak status

# Update to latest version
molt-speak update

# View logs
molt-speak logs audio
molt-speak logs integration

# Quit everything
molt-speak quit
```

## Branch Differences

| Branch | Status | Description |
|--------|--------|-------------|
| `main` | Stable | Production-ready release with Edge-TTS (free) |
| `develop` | Testing | Latest features including ElevenLabs integration |

## ElevenLabs Setup (Develop Branch Only)

After installing from develop branch:

1. Get an API key from [elevenlabs.io](https://elevenlabs.io)
2. Run: `molt-speak elo`
3. Follow the interactive setup wizard
4. Select your preferred voice and model
5. Test the voice before saving

The system will automatically switch between Edge-TTS (free) and ElevenLabs (premium) based on your configuration.

## Requirements

- macOS (10.15 or later)
- Python 3.8+
- Homebrew (will be installed if missing)
- OpenClaw TUI (must be running separately)

## Uninstall

```bash
# Remove installed files
rm -rf ~/open-claw-workspace/molt-speak/app
sudo rm /usr/local/bin/molt-speak
```
