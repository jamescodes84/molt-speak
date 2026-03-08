# OpenClaw Ears - Voice Input for AI Agents

Real-time voice transcription system for OpenClaw agents. Listens to your microphone, transcribes speech using Whisper, and outputs text that your agent can monitor.

## Quick Start

### 1. Install
```bash
cd /path/to/openclaw-ears
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Voice System
```bash
./start_voice_system.sh
```

### 3. Use with OpenClaw Agent
The system automatically types voice commands directly into your OpenClaw TUI:
- Speech is transcribed
- Text is typed into the active terminal window
- Enter is pressed automatically

Just keep your OpenClaw agent TUI focused and speak!

## How It Works

```
You speak → Microphone → Whisper AI → Types into TUI → Presses Enter → Agent receives input
```

**Example:**
1. You say: "Hello agent, what's the weather?"
2. System types into TUI: `Hello agent, what's the weather?`
3. System presses Enter automatically
4. Agent receives it as keyboard input and responds

## Features

- **Real-time transcription** - 1-2 second latency using Whisper
- **MPS acceleration** - Fast on Apple Silicon Macs
- **Silence detection** - Only transcribes actual speech
- **Embedded visualization** - See audio waveforms and status inline in your terminal
- **Multiple models** - tiny, base, small, medium (tiny is fastest)
- **Simple integration** - Types directly into your TUI, no code changes needed

## Configuration

### Command Line Options
```bash
# Use better model for accuracy
python main.py --model base

# Adjust microphone sensitivity (lower = more sensitive)
python main.py --threshold 300

# Faster response time
python main.py --duration 1.0

# Enable text-to-speech
python main.py --tts

# Debug mode
python main.py --log-level DEBUG
```

### Environment Variables
Create `.env` file:
```bash
WHISPER_MODEL=tiny              # Model size
SPEECH_THRESHOLD=500            # Mic sensitivity
SEGMENT_DURATION=1.5            # Seconds per segment
ENABLE_TTS=false                # Text-to-speech
LOG_LEVEL=INFO                  # Logging level
```

## Performance

On Apple Silicon (M1/M2/M3):

| Model | Load Time | Transcription | Accuracy |
|-------|-----------|---------------|----------|
| tiny  | 1-2s      | 1-2s          | Good     |
| base  | 2-3s      | 2-3s          | Better   |
| small | 3-5s      | 4-6s          | Great    |

**Recommended:** `tiny` for speed, `base` for accuracy

## Troubleshooting

**No transcription appearing?**
- Check microphone is working: `python -c "import sounddevice as sd; print(sd.query_devices())"`
- Speak louder or closer to mic
- Lower threshold: `--threshold 200`

**Poor transcription quality?**
- Use better model: `--model base`
- Reduce background noise
- Speak more clearly

**System too slow?**
- Use `tiny` model (default)
- Reduce segment duration: `--duration 1.0`
- Check MPS is enabled (logs show "Loaded whisper tiny on mps")

## Project Structure

```
├── main.py                         # Main entry point
├── start_voice_system.sh           # Easy startup script
├── AGENT_INSTRUCTIONS.txt          # Agent integration guide
├── requirements.txt                # Python dependencies
└── src/
    ├── core/
    │   ├── voice_pipeline.py       # Main voice pipeline
    │   ├── terminal_visualizer.py  # Embedded terminal visualization
    │   ├── audio_capture.py        # Audio capture
    │   └── state_manager.py        # State management
    ├── services/
    │   ├── transcription_service.py # Whisper integration
    │   ├── tts_service.py          # Text-to-speech
    │   └── vad_service.py          # Voice activity detection
    ├── config/
    │   └── settings.py             # Configuration
    └── plugins/
        └── openclaw_ears_plugin.py # Plugin interface
```

## Dependencies

- Python 3.9+
- PyAudio / SoundDevice (audio capture)
- OpenAI Whisper (speech-to-text)
- PyTorch with MPS support (Apple Silicon)
- NumPy, SciPy (signal processing)
- WebRTC VAD (voice detection)
- Edge TTS (text-to-speech, optional)

## Technical Details

### Audio Pipeline
1. **Capture** - Continuous 16kHz mono audio from microphone
2. **Detection** - VAD filters out silence
3. **Buffering** - Collects 1.5s segments
4. **Transcription** - Whisper processes audio
5. **Visualization** - Live waveforms and status in terminal
6. **Output** - Types text into active window

### Output Method
The system types transcribed text directly into the active terminal window and presses Enter.

**Technical:** Uses pyautogui to simulate keyboard input directly into the OpenClaw TUI.

## For OpenClaw Agents

Your agent automatically receives voice commands as keyboard input!

**Setup:**
1. Run your OpenClaw agent in a terminal
2. Start voice system: `./start_voice_system.sh`
3. Focus your agent's terminal window (click it)
4. Speak - commands are typed into your agent automatically!

See **[AGENT_INSTRUCTIONS.txt](AGENT_INSTRUCTIONS.txt)** for details.

**IMPORTANT FOR AI AGENTS:** The voice system is complete and working. DO NOT modify the Python code. Just run `./start_voice_system.sh` and receive voice commands as keyboard input. No code changes needed in your agent!

## License

Part of the OpenClaw ecosystem.

## Credits

- Part of the OpenClaw ecosystem
- Uses OpenAI's Whisper for transcription
- WebRTC for voice activity detection
