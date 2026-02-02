# Claude Code Brief: Build OpenClaw Mouth

## Your Mission

Build a text-to-speech system called **OpenClaw Mouth** that is the inverse of the **OpenClaw Ears** voice input system you're looking at.

**Repository:** https://github.com/jamescodes84/open_mouth.git

---

## What You're Looking At Now: OpenClaw Ears

This is the **INPUT** side of voice interaction:

```
User speaks → Microphone → Whisper AI → Types into Agent TUI
```

**Key files to study:**
- [src/core/jarvis_ultra_fast.py](src/core/jarvis_ultra_fast.py) - Main pipeline
- [src/core/terminal_visualizer.py](src/core/terminal_visualizer.py) - Embedded terminal display
- [AGENT_INSTRUCTIONS.txt](AGENT_INSTRUCTIONS.txt) - How agents use it
- [README.md](README.md) - Project documentation
- [start_voice_system.sh](start_voice_system.sh) - Startup script

**Architecture to mirror:**
- Terminal-based visualization (not separate windows)
- Simple file-based integration
- Threading and queues for parallel processing
- Clear safeguards telling agents not to modify code
- Minimal dependencies
- Command-line configuration
- One-script startup

---

## What You Need to Build: OpenClaw Mouth

This is the **OUTPUT** side of voice interaction:

```
Agent writes text → File monitoring → Edge-TTS → Speakers
```

### Core Pipeline

```python
class MouthPipeline:
    """Main TTS pipeline - inverse of UltraFastJarvis"""

    def __init__(self):
        # Similar structure to jarvis_ultra_fast.py
        self.visualizer = TerminalVisualizer()  # Like Ears
        self.tts_service = EdgeTTSService()     # Instead of Whisper
        self.audio_player = AudioPlayer()       # Instead of AudioCapture
        self.text_monitor = TextMonitor()       # Watches for new text

    def start(self):
        """Start the speech system"""
        # Thread 1: Monitor for new text
        # Thread 2: Synthesize speech
        # Thread 3: Update terminal display
        # Thread 4: Play audio
```

### File Monitoring (Input)

Instead of monitoring microphone, monitor a text file:

```python
# Watch ~/.openclaw/speech_output.txt
# When agent writes new text:
#   1. Detect new line
#   2. Queue for synthesis
#   3. Generate speech with Edge-TTS
#   4. Play through speakers
#   5. Update visualization
```

### Terminal Visualizer

Create similar to `src/core/terminal_visualizer.py` but for speech:

```python
class TerminalVisualizer:
    """Show what's being spoken (inverse of audio waveform)"""

    def render_full(self):
        """Display current speech status"""
        # Status: 📢 SPEAKING / 🔇 IDLE / ⏳ QUEUED
        # Text: "Currently speaking this text..."
        # Progress: [████████░░░] 75%
        # Voice: en-US-ChristopherNeural
```

---

## Exact Files to Create

Mirror the Ears structure:

```
open_mouth/
├── main.py                      # Entry point (like Ears main.py)
├── start_speech_system.sh       # Startup script (like Ears start_voice_system.sh)
├── AGENT_INSTRUCTIONS.txt       # Agent guide (like Ears)
├── README.md                    # Documentation (like Ears)
├── requirements.txt             # Dependencies
├── .env.example                 # Config template
└── src/
    ├── core/
    │   ├── mouth_pipeline.py       # Main pipeline (inverse of jarvis_ultra_fast.py)
    │   ├── terminal_visualizer.py  # Display (copy and adapt from Ears)
    │   └── state_manager.py        # State (similar to Ears)
    ├── services/
    │   ├── tts_service.py          # Edge-TTS wrapper
    │   ├── audio_playback.py       # Speaker output
    │   └── text_monitor.py         # File monitoring
    ├── config/
    │   └── settings.py             # Configuration (like Ears)
    └── utils/
        ├── logging_utils.py        # Logging (like Ears)
        └── openclaw_notifier.py    # Integration (like Ears)
```

---

## Critical Requirements

### 1. Mirror the Ears Architecture

Study how Ears is structured and create the inverse:

| Component | Ears (Input) | Mouth (Output) |
|-----------|--------------|----------------|
| Main file | `jarvis_ultra_fast.py` | `mouth_pipeline.py` |
| Primary library | `openai-whisper` | `edge-tts` |
| Hardware | Microphone → capture | Speakers → playback |
| Processing | Audio → Text | Text → Audio |
| Visualization | Waveform + status | Text + progress |
| Integration | Types into TUI | Reads from file |

### 2. Use the Same Design Patterns

- **Threading model:** Same 3-4 thread architecture as Ears
- **Queue-based:** Use queues for text → synthesis → playback
- **Terminal display:** Update loop at ~20Hz (0.05s sleep)
- **Configuration:** CLI args + environment variables
- **Error handling:** Graceful failures, don't crash

### 3. Keep Compatibility

- **Run alongside Ears:** No conflicts, separate terminals
- **Same file structure:** Easy to understand if you know Ears
- **Same documentation style:** README + AGENT_INSTRUCTIONS
- **Same safeguards:** Warnings not to modify code

---

## Dependencies (requirements.txt)

```txt
# Core TTS
edge-tts>=6.1.0

# Audio playback
sounddevice>=0.4.6
numpy>=1.24.0
scipy>=1.10.0

# Monitoring and utilities
watchdog>=3.0.0  # For file monitoring
python-dotenv>=1.0.0

# Optional
pyaudio>=0.2.13  # Alternative to sounddevice
```

---

## Key Implementation Steps

### Step 1: Basic TTS Pipeline

Start with minimal working version:

```python
# main.py
import asyncio
import edge_tts

async def speak(text):
    """Basic TTS test"""
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save("output.mp3")
    # Play the audio file

# Test it works before building full pipeline
```

### Step 2: File Monitoring

Add text input monitoring:

```python
# src/services/text_monitor.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class TextMonitor:
    """Monitor ~/.openclaw/speech_output.txt for new text"""

    def __init__(self, file_path):
        self.file_path = file_path
        self.last_position = 0

    def start_monitoring(self):
        """Watch file and queue new lines"""
        # Similar to how Ears captures audio
        # But instead watch file for changes
```

### Step 3: Terminal Visualizer

Copy and adapt from Ears:

```bash
# Copy the visualizer from Ears as a starting point
cp "../Jarvis Sandbox/src/core/terminal_visualizer.py" "src/core/terminal_visualizer.py"

# Then modify for speech output:
# - Change waveform to progress bar
# - Change "SPEAKING/DETECTED/QUIET" to "SPEAKING/QUEUED/IDLE"
# - Add current text being spoken
# - Add voice indicator
```

### Step 4: Complete Pipeline

Combine everything into `mouth_pipeline.py`:

```python
class MouthPipeline:
    """Complete TTS pipeline"""

    def __init__(self, voice='en-US-ChristopherNeural', rate=1.0):
        self.voice = voice
        self.rate = rate
        self.visualizer = TerminalVisualizer()
        self.text_queue = queue.Queue()
        self.running = False

    def _monitor_loop(self):
        """Monitor for new text (Thread 1)"""
        # Similar to Ears _capture_loop

    def _synthesis_loop(self):
        """Synthesize queued text (Thread 2)"""
        # Similar to Ears _transcription_worker

    def _playback_loop(self):
        """Play synthesized audio (Thread 3)"""
        # New - plays the generated audio

    def _display_loop(self):
        """Update terminal display (Thread 4)"""
        # Exactly like Ears _display_loop

    def start(self):
        """Start all threads"""
        # Same pattern as Ears
```

### Step 5: Documentation

Create docs with **explicit safeguards**:

```markdown
# AGENT_INSTRUCTIONS.txt

⚠️  CRITICAL - READ THIS FIRST ⚠️
DO NOT MODIFY THE SPEECH SYSTEM CODE!

The speech system is already built and working.
✅ Use it as-is
✅ Write to ~/.openclaw/speech_output.txt
❌ DO NOT modify the Python code
❌ DO NOT try to "improve" it

[... rest of instructions ...]
```

---

## Testing Checklist

Before considering it done:

- [ ] Run `./start_speech_system.sh` - should start without errors
- [ ] Write to `~/.openclaw/speech_output.txt` - should hear speech within 1s
- [ ] Terminal shows current text being spoken
- [ ] Can run alongside Ears without conflicts
- [ ] Multiple voices work (`--voice en-US-AriaNeural`)
- [ ] Queue handles rapid messages correctly
- [ ] Clean shutdown (finishes speaking before exit)
- [ ] Documentation is clear and has safeguards
- [ ] No dependencies on Ears code (standalone project)

---

## What Success Looks Like

**User experience:**

```bash
# Terminal 1: Start speech output
cd /path/to/open_mouth
./start_speech_system.sh

# See terminal display:
# ┌─────────────────────────────────────────────┐
# │ 📢 SPEAKING                                 │
# │ Text: "Hello! How can I help you today?"   │
# │ Progress: [████████████░░░] 75%            │
# │ Voice: en-US-ChristopherNeural             │
# └─────────────────────────────────────────────┘

# Terminal 2: Test it
echo "Hello! How can I help you today?" >> ~/.openclaw/speech_output.txt

# Hear: "Hello! How can I help you today?" spoken aloud
```

**With full system:**

```bash
# Terminal 1: Voice input
cd /path/to/open_ears
./start_voice_system.sh

# Terminal 2: Voice output
cd /path/to/open_mouth
./start_speech_system.sh

# Terminal 3: OpenClaw agent
openclaw-agent

# User speaks → Agent hears → Agent responds → User hears response
# Complete voice conversation loop!
```

---

## Critical Don'ts

❌ Don't create a GUI application (terminal only, like Ears)
❌ Don't add features not in the spec (keep it simple)
❌ Don't use different architecture patterns (mirror Ears)
❌ Don't forget the safeguards in documentation
❌ Don't make it dependent on Ears (standalone project)

---

## Critical Do's

✅ Do study the Ears codebase first (understand the patterns)
✅ Do reuse the terminal visualizer concept (adapt it)
✅ Do use the same threading model (parallel processing)
✅ Do write clear documentation with warnings
✅ Do test with both Ears and Mouth running together
✅ Do keep it simple and focused

---

## Questions to Ask

Before you start building, consider:

1. **Should it read from stdout or file?** (File recommended for consistency)
2. **Default voice?** (Christopher is clear and professional)
3. **Should it interrupt when user speaks?** (Nice feature but not MVP)
4. **Text preprocessing?** (Remove markdown formatting, emojis?)
5. **Max queue size?** (Prevent memory issues with rapid messages)

---

## Reference Implementation

Study these Ears files as templates:

1. **Pipeline pattern:** `src/core/jarvis_ultra_fast.py`
   - Thread management
   - Queue handling
   - Error recovery

2. **Visualization:** `src/core/terminal_visualizer.py`
   - Terminal rendering
   - Color coding
   - Progress display

3. **Documentation:** `AGENT_INSTRUCTIONS.txt` and `README.md`
   - Structure
   - Safeguards
   - Examples

4. **Startup:** `start_voice_system.sh`
   - Virtual environment
   - Error checking
   - Clean output

---

## Timeline Suggestion

- **Day 1:** Study Ears architecture, set up project structure
- **Day 2:** Implement basic TTS pipeline (text → speech)
- **Day 3:** Add file monitoring and queueing
- **Day 4:** Implement terminal visualizer
- **Day 5:** Write documentation and test integration

---

## Final Note

This is not a greenfield project. You're creating the **inverse** of an existing system.

Every decision in Ears has a corresponding decision in Mouth:
- Ears captures audio → Mouth monitors text
- Ears transcribes → Mouth synthesizes
- Ears types output → Mouth speaks output
- Ears shows waveform → Mouth shows progress

**Keep it symmetrical. Keep it simple. Keep it compatible.**

---

*Provide this brief + [OPEN_MOUTH_DESIGN.md](OPEN_MOUTH_DESIGN.md) to Claude Code when starting the open_mouth project.*
