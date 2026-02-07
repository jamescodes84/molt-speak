# OpenClaw Mouth - Design Specification
## Text-to-Speech Output for AI Agents

---

## Project Overview

**Repository:** https://github.com/jamescodes84/open_mouth.git
**Purpose:** Real-time text-to-speech system for OpenClaw agents
**Relationship:** Companion project to OpenClaw Ears (voice input)

### The Complete Loop
```
User speaks → OpenClaw Ears → Agent TUI → Agent processes → OpenClaw Mouth → Speaker
```

---

## Design Principles

### 1. Mirror OpenClaw Ears Architecture

OpenClaw Mouth should be the **inverse** of OpenClaw Ears:

| OpenClaw Ears (Input) | OpenClaw Mouth (Output) |
|----------------------|-------------------------|
| Microphone → Text | Text → Speaker |
| Listens to user | Speaks to user |
| Types into TUI | Reads from TUI |
| Whisper transcription | Edge-TTS synthesis |
| Audio visualization | Text visualization |
| Embedded terminal display | Embedded terminal display |

### 2. Shared Design Qualities

Both projects MUST share these qualities:

- **Embedded visualization** - Terminal-based, not separate windows
- **Simple integration** - No code changes in agent required
- **Zero configuration** - Works out of the box
- **Apple Silicon optimized** - MPS acceleration where possible
- **Minimal dependencies** - Keep it lightweight
- **Clear documentation** - Agent instructions + README only
- **Safeguarded** - Explicit warnings not to modify

### 3. Compatibility Requirements

The two systems must work together seamlessly:

- **Independent operation** - Each can run standalone
- **Concurrent execution** - Both can run simultaneously
- **Non-interfering** - Won't conflict with each other
- **Shared state** (optional) - Can communicate if needed
- **Same terminal approach** - Both use TUI-friendly output

---

## Technical Specification

### Input Method: How to Receive Agent Text

**Recommended Approach:** Monitor agent's output in real-time

```python
# Option 1: Read from agent's stdout (most universal)
# - Intercept or tail the agent's terminal output
# - Parse text responses
# - Speak them aloud

# Option 2: Monitor a shared file
# - Agent writes responses to ~/.openclaw/speech_output.txt
# - OpenClaw Mouth monitors and speaks new content
# - Similar to how Ears writes, Mouth reads

# Option 3: Named pipe/FIFO
# - Agent writes to pipe
# - Mouth reads from pipe in real-time
```

**Preferred:** Option 2 (file monitoring) for consistency with Ears architecture.

### Core Pipeline

```
1. Monitor source (file/stdout/pipe)
2. Detect new text to speak
3. Queue for synthesis
4. Synthesize with Edge-TTS
5. Play audio through speakers
6. Update terminal visualization
```

### Technology Stack

**Must use:**
- **edge-tts** - Free, high-quality TTS (same as Ears uses optionally)
- **PyAudio or sounddevice** - Audio playback (same as Ears uses)
- **Terminal visualizer** - Show what's being spoken (like Ears waveform)

**Similar to Ears:**
- Threading for parallel processing
- Queue-based architecture
- Real-time terminal display updates
- Low latency pipeline

### Terminal Visualization

Create a companion to `terminal_visualizer.py`:

```
📢 SPEAKING
Text: "Hello, I can help you with that!"
Progress: [████████████░░░░░░░░] 60%
Voice: en-US-ChristopherNeural
```

**Features:**
- Show current text being spoken
- Progress bar for speech playback
- Voice selection indicator
- Speaking status (speaking/idle/queued)
- Color-coded states (green=speaking, gray=idle, yellow=queued)

---

## Project Structure

Mirror the Ears structure:

```
open_mouth/
├── main.py                         # Main entry point
├── start_speech_system.sh          # Easy startup script
├── AGENT_INSTRUCTIONS.txt          # Agent integration guide
├── README.md                       # Project documentation
├── requirements.txt                # Python dependencies
└── src/
    ├── core/
    │   ├── mouth_pipeline.py       # Main TTS pipeline
    │   ├── terminal_visualizer.py  # Embedded terminal visualization
    │   └── state_manager.py        # State management
    ├── services/
    │   ├── tts_service.py          # Edge-TTS integration
    │   ├── audio_playback.py       # Speaker output
    │   └── text_monitor.py         # Monitor agent output
    ├── config/
    │   └── settings.py             # Configuration
    └── utils/
        ├── logging_utils.py        # Logging
        └── openclaw_notifier.py    # Integration hooks
```

---

## Feature Requirements

### Core Features (Must Have)

1. ✅ Real-time TTS with <1 second latency
2. ✅ Multiple voice options (male/female, accents)
3. ✅ Queue-based processing (handle rapid messages)
4. ✅ Embedded terminal visualization
5. ✅ Simple file-based input (like Ears uses file output)
6. ✅ Low CPU usage when idle
7. ✅ Clean shutdown (finish speaking before exit)

### Advanced Features (Nice to Have)

1. ⭐ Voice emotion detection (speak differently based on sentiment)
2. ⭐ Speed control (faster for long responses)
3. ⭐ Interrupt capability (stop speaking when user talks)
4. ⭐ Text preprocessing (better pronunciation, remove emojis)
5. ⭐ Multi-language support

### Integration Features

1. ✅ Works with any OpenClaw agent
2. ✅ No agent code changes required
3. ✅ Auto-detect when agent writes output
4. ✅ Configurable via command-line args
5. ✅ Environment variable support

---

## Configuration

### Command-Line Arguments

Mirror the Ears interface:

```bash
# Voice selection
python main.py --voice en-US-ChristopherNeural

# Speed control
python main.py --rate 1.2  # 20% faster

# Volume
python main.py --volume 0.8  # 80% volume

# Input source
python main.py --input ~/.openclaw/speech_output.txt

# Debug mode
python main.py --log-level DEBUG
```

### Environment Variables

Create `.env` support:

```bash
TTS_VOICE=en-US-ChristopherNeural
TTS_RATE=1.0
TTS_VOLUME=1.0
INPUT_FILE=~/.openclaw/speech_output.txt
LOG_LEVEL=INFO
```

---

## Integration with OpenClaw Agents

### Agent Instructions Document

Create `AGENT_INSTRUCTIONS.txt` similar to Ears:

```
=============================================================================
AGENT SETUP INSTRUCTIONS - How to Speak to Your User
=============================================================================

⚠️  CRITICAL - READ THIS FIRST ⚠️
DO NOT MODIFY THE SPEECH SYSTEM CODE!
[... similar warnings to Ears ...]

HOW THE SPEECH SYSTEM WORKS
1. You write responses to ~/.openclaw/speech_output.txt
2. Speech system detects new text
3. Text is synthesized to speech using Edge-TTS
4. Speech plays through speakers
5. User hears your response!

STEP 1: START THE SPEECH SYSTEM
Terminal 1 (Speech System):
    cd "/path/to/open_mouth"
    ./start_speech_system.sh

STEP 2: WRITE RESPONSES TO FILE
When you want to speak, write to:
    ~/.openclaw/speech_output.txt

Example:
    echo "Hello! How can I help you?" >> ~/.openclaw/speech_output.txt

STEP 3: LISTEN
The speech system automatically speaks any new text you write!
```

### Integration Pattern

**File-based communication (recommended):**

```python
# In agent code (optional - for agents that want voice output)
import os
from pathlib import Path

def speak(text):
    """Send text to OpenClaw Mouth for TTS"""
    output_file = Path.home() / '.openclaw' / 'speech_output.txt'
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'a') as f:
        f.write(f"{text}\n")
```

---

## Compatibility Matrix

### Running Together

Both systems should coexist peacefully:

| Scenario | Ears | Mouth | Works? |
|----------|------|-------|--------|
| Ears only | ✅ | ❌ | ✅ Voice input only |
| Mouth only | ❌ | ✅ | ✅ Voice output only |
| Both running | ✅ | ✅ | ✅ Full conversation |
| Same terminal | ❌ | ❌ | ⚠️ Use separate terminals |

### Shared Resources

- **Audio devices:** Use different devices or channels
- **File paths:** Different files (input vs output)
- **Terminal display:** Run in separate terminals
- **CPU:** Both should be lightweight enough to run together

### Communication Protocol (Optional)

For advanced integration:

```
~/.openclaw/
├── voice/
│   ├── input.txt          # Ears writes here
│   └── transcriptions/    # Ears history
└── speech/
    ├── output.txt         # Mouth reads here
    └── utterances/        # Mouth history
```

---

## Performance Targets

Match or exceed Ears performance:

| Metric | Target | Notes |
|--------|--------|-------|
| Latency | <1s | From text received to audio start |
| CPU (idle) | <5% | When not speaking |
| CPU (active) | <30% | While synthesizing |
| Memory | <200MB | Loaded and ready |
| Startup time | <3s | From launch to ready |

---

## Testing Strategy

### Unit Tests

- TTS service initialization
- Text monitoring and detection
- Audio playback pipeline
- Terminal visualization rendering
- Configuration loading

### Integration Tests

- End-to-end: File write → Speech playback
- Concurrent operation with Ears
- Long-running stability (1+ hour)
- Error recovery (bad input, no audio device)

### User Testing

- Speak various message types (short, long, code, emojis)
- Test with actual OpenClaw agent
- Run both Ears and Mouth simultaneously
- Verify visualization updates correctly

---

## Safeguards and Warnings

### Agent Instructions Safeguards

**Include these warnings prominently:**

1. ⚠️ DO NOT modify the speech system code
2. ⚠️ DO NOT try to "improve" or add features
3. ⚠️ DO NOT refactor or optimize the pipeline
4. ✅ DO just write to the output file
5. ✅ DO report issues to the user

### README Warnings

```markdown
## For OpenClaw Agents

**IMPORTANT:** The speech system is complete and working.
DO NOT modify the Python code. Just write your responses to:
    ~/.openclaw/speech_output.txt

No code changes needed in your agent!
```

---

## Differences from Ears

While mirroring the architecture, these differences are expected:

| Aspect | Ears (Input) | Mouth (Output) |
|--------|--------------|----------------|
| Hardware | Microphone | Speakers |
| Primary library | openai-whisper | edge-tts |
| Data flow | Audio → Text | Text → Audio |
| Processing | Transcription | Synthesis |
| Visualization | Waveform | Text progress |
| Main challenge | Accurate transcription | Natural speech |
| Latency source | AI model | Network (edge-tts) |

---

## Implementation Priorities

### Phase 1: Core Functionality (MVP)

1. Basic TTS pipeline (text file → speech)
2. Edge-TTS integration
3. Simple terminal output (no fancy visualization yet)
4. Command-line configuration
5. Basic documentation

### Phase 2: Polish

1. Terminal visualizer (matching Ears style)
2. Multiple voice support
3. Queue management for rapid messages
4. Error handling and recovery
5. Complete documentation with safeguards

### Phase 3: Advanced Features

1. Voice emotion/tone variation
2. Interrupt capability
3. Integration with Ears (detect when user speaks, pause output)
4. Performance optimization
5. Extended testing

---

## Success Criteria

OpenClaw Mouth is ready when:

1. ✅ User can write text to file and hear it spoken within 1 second
2. ✅ Terminal visualization shows speaking status clearly
3. ✅ Works alongside OpenClaw Ears without conflicts
4. ✅ Documentation is clear and complete (README + AGENT_INSTRUCTIONS)
5. ✅ Agent safeguards are prominent and explicit
6. ✅ Startup script works out of the box
7. ✅ No code changes required in OpenClaw agent

---

## Example Usage

### Standalone

```bash
# Terminal 1: Start speech system
cd /path/to/open_mouth
./start_speech_system.sh

# Terminal 2: Send text to speak
echo "Hello, I am your AI assistant!" >> ~/.openclaw/speech_output.txt
```

### With OpenClaw Agent

```bash
# Terminal 1: Speech system
cd /path/to/open_mouth
./start_speech_system.sh

# Terminal 2: Voice input system
cd /path/to/open_ears
./start_voice_system.sh

# Terminal 3: OpenClaw agent
openclaw-agent --enable-voice

# Now have full voice conversation!
```

---

## Questions for Implementation

Before building, clarify:

1. **Voice preference:** Which default voice? (Christopher, Aria, Jenny?)
2. **Input method:** File monitoring, stdout capture, or pipe?
3. **Interrupt behavior:** Should it stop speaking when user talks?
4. **Message queuing:** FIFO or priority-based?
5. **Text preprocessing:** Remove markdown, code blocks, emojis?
6. **Rate limiting:** Max words per minute to prevent overwhelming?

---

## Deliverables

When complete, the open_mouth repository should have:

1. ✅ Working TTS pipeline with <1s latency
2. ✅ Terminal visualizer matching Ears style
3. ✅ `README.md` (similar to Ears)
4. ✅ `AGENT_INSTRUCTIONS.txt` (with safeguards)
5. ✅ `start_speech_system.sh` (one-command startup)
6. ✅ `requirements.txt` (minimal dependencies)
7. ✅ Clean project structure (matching Ears)
8. ✅ Configuration via CLI args and .env
9. ✅ Comprehensive error handling
10. ✅ Works standalone and with Ears

---

## Design Philosophy

**Keep it simple. Keep it compatible. Keep it consistent.**

Just as OpenClaw Ears lets agents "hear" their users without complexity,
OpenClaw Mouth should let agents "speak" to their users with equal simplicity.

The agent shouldn't need to understand TTS, audio codecs, or synthesis.
They just write text. The text is spoken. Done.

---

## References

- **OpenClaw Ears:** /path/to/molt-speak/open_ears
- **Edge-TTS:** https://github.com/rany2/edge-tts
- **OpenClaw Ecosystem:** Part of the broader OpenClaw agent framework

---

*This document serves as the complete specification for building OpenClaw Mouth.
Provide it to Claude Code to implement the project in the open_mouth repository.*
