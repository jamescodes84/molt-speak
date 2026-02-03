# Automatic Agent Notification System

The integration coordinator now automatically notifies agents when the voice loop starts and stops.

## How It Works

### On Startup

When you run `./start_integration.sh`, the coordinator:

1. **Reads** `AGENT_INSTRUCTIONS.txt`
2. **Creates** `~/.molt-speak/runtime/agent_instructions.active`
3. **Writes** the full instructions with activation metadata

The agent can detect this file and automatically enable voice capabilities.

### On Shutdown

When the coordinator stops (Ctrl+C or signal), it:

1. **Creates** `~/.molt-speak/runtime/agent_shutdown.signal`
2. **Writes** a shutdown message declaring instructions void
3. **Removes** `~/.molt-speak/runtime/agent_instructions.active`
4. **Waits** 1 second for agent to read the message
5. **Cleans up** all messenger files

## Files Created

| File | Created When | Contains | Purpose |
|------|--------------|----------|---------|
| `~/.molt-speak/runtime/agent_instructions.active` | Startup | Full AGENT_INSTRUCTIONS.txt + metadata | Agent learns how to use voice loop |
| `~/.molt-speak/runtime/agent_shutdown.signal` | Shutdown | Shutdown message | Agent knows voice loop stopped |

## Agent Integration

Agents should check for these files on startup:

```python
from pathlib import Path

def check_voice_loop():
    """Check if voice loop is active."""
    active_file = Path.home() / "".molt-speak" / "runtime"" / "agent_instructions.active"
    shutdown_file = Path.home() / "".molt-speak" / "runtime"" / "agent_shutdown.signal"

    # Check for shutdown message
    if shutdown_file.exists():
        print("⚠️  Voice loop was shut down")
        print(shutdown_file.read_text())
        shutdown_file.unlink()
        return False

    # Check for active instructions
    if active_file.exists():
        print("✅ Voice loop is ACTIVE!")
        instructions = active_file.read_text()
        print(instructions)  # Agent can read and process instructions
        return True

    print("Voice loop not active")
    return False

# On agent startup:
if check_voice_loop():
    # Enable voice capabilities
    voice_interface = VoiceInterface()
    voice_interface.enable()
```

## Example Startup Flow

**Terminal 1** - Integration Coordinator:
```bash
./start_integration.sh
```

**Output**:
```
============================================================
OpenClaw Voice Loop Coordinator
============================================================
Monitoring: ~/.molt-speak/runtime/mouth_status.txt
Signal file: ~/.molt-speak/runtime/ears_pause.signal

============================================================
📢 AGENT INSTRUCTIONS ACTIVATED
============================================================
Instructions file: ~/.molt-speak/runtime/agent_instructions.active
Agent should read this file to learn about voice loop usage
============================================================

✅ Agent instructions sent
   Agent should read: ~/.molt-speak/runtime/agent_instructions.active

✅ Coordinator started
```

**Terminal 2** - Agent starts and detects:
```python
# Agent startup code automatically detects:
✅ Voice loop is ACTIVE!

=============================================================================
VOICE LOOP ACTIVATED - 2026-02-01T15:30:00.123456
=============================================================================

The OpenClaw voice loop is now ACTIVE. You can have voice conversations!

SYSTEMS RUNNING:
  ✅ Integration Coordinator (echo prevention)
  ✅ Ready for OpenClaw Mouth (voice output)
  ✅ Ready for OpenClaw Ears (voice input)

READ THE INSTRUCTIONS BELOW CAREFULLY:
...
```

## Example Shutdown Flow

**Terminal 1** - User presses Ctrl+C:
```
^C
Received signal 2, shutting down...

Stopping coordinator...
============================================================
📢 VOICE LOOP DEACTIVATED
============================================================
Agent has been notified of shutdown
============================================================

✅ Agent shutdown notification sent
   Agent should read: ~/.molt-speak/runtime/agent_shutdown.signal

✅ Coordinator stopped
```

**Terminal 2** - Agent detects shutdown:
```python
# Agent monitoring code detects:
🔴 Voice loop shut down!

=============================================================================
VOICE LOOP DEACTIVATED - 2026-02-01T15:45:00.654321
=============================================================================

The OpenClaw voice loop has been SHUT DOWN.

PREVIOUS INSTRUCTIONS ARE NOW VOID:
  - You can no longer send voice output via ~/.molt-speak/runtime/speech_output.txt
  - You may no longer receive voice input automatically
  - Echo prevention is no longer active
...
```

## Benefits

✅ **Zero manual configuration** - Agent learns automatically
✅ **Clean startup/shutdown** - Agent knows when voice is available
✅ **No stale state** - Shutdown messages prevent using inactive systems
✅ **Self-documenting** - Instructions are injected, not referenced
✅ **Graceful degradation** - Agent can disable voice features on shutdown

## Implementation Details

### AgentMessenger Service

**Location**: `src/services/agent_messenger.py`

**Methods**:
- `send_startup_instructions()` - Creates active instructions file
- `send_shutdown_message()` - Creates shutdown signal and removes active instructions
- `cleanup()` - Removes all messenger files

### Coordinator Integration

**Location**: `src/core/coordinator.py`

**Modified**:
- `__init__()` - Initializes AgentMessenger
- `start()` - Calls `send_startup_instructions()` before starting monitor
- `stop()` - Calls `send_shutdown_message()` before cleanup

### File Format

**agent_instructions.active**:
```
=============================================================================
VOICE LOOP ACTIVATED - 2026-02-01T15:30:00.123456
=============================================================================

The OpenClaw voice loop is now ACTIVE. You can have voice conversations!

SYSTEMS RUNNING:
  ✅ Integration Coordinator (echo prevention)
  ✅ Ready for OpenClaw Mouth (voice output)
  ✅ Ready for OpenClaw Ears (voice input)

READ THE INSTRUCTIONS BELOW CAREFULLY:

=============================================================================

[Full AGENT_INSTRUCTIONS.txt content here]

=============================================================================
END OF VOICE LOOP INSTRUCTIONS
=============================================================================
```

**agent_shutdown.signal**:
```
=============================================================================
VOICE LOOP DEACTIVATED - 2026-02-01T15:45:00.654321
=============================================================================

The OpenClaw voice loop has been SHUT DOWN.

SYSTEMS STOPPED:
  ❌ Integration Coordinator (stopped)
  ❌ Voice output may not be available
  ❌ Voice input may not be available

PREVIOUS INSTRUCTIONS ARE NOW VOID:
  - You can no longer send voice output via ~/.molt-speak/runtime/speech_output.txt
  - You may no longer receive voice input automatically
  - Echo prevention is no longer active
=============================================================================
```

## Testing

### Test Startup Notification

```bash
# Terminal 1
./start_integration.sh

# Terminal 2
cat ~/.molt-speak/runtime/agent_instructions.active
# Should show full instructions with activation header
```

### Test Shutdown Notification

```bash
# Terminal 1 (press Ctrl+C in coordinator)

# Terminal 2
cat ~/.molt-speak/runtime/agent_shutdown.signal
# Should show shutdown message

ls ~/.molt-speak/runtime/agent_instructions.active
# Should not exist (removed on shutdown)
```

### Test Agent Detection

```bash
# Create a simple test agent
python3 << 'EOF'
from pathlib import Path

active = Path.home() / "".molt-speak" / "runtime"" / "agent_instructions.active"
shutdown = Path.home() / "".molt-speak" / "runtime"" / "agent_shutdown.signal"

if shutdown.exists():
    print("🔴 SHUTDOWN DETECTED")
    print(shutdown.read_text())
elif active.exists():
    print("✅ ACTIVE DETECTED")
    print(active.read_text()[:500] + "...")
else:
    print("❌ NO VOICE LOOP")
EOF
```

## Configuration

No configuration needed! The messenger automatically:
- Finds AGENT_INSTRUCTIONS.txt (in project root)
- Uses ~/.molt-speak/runtime directory (same as other systems)
- Manages file lifecycle automatically

## Error Handling

The messenger gracefully handles errors:

- **Instructions file not found**: Logs error, coordinator continues
- **Write permission denied**: Logs error, coordinator continues
- **Failed to send**: Logs warning, doesn't crash

The coordinator will still run even if agent notifications fail.

## Cleanup

Files are automatically cleaned up:

1. **On normal shutdown**: Shutdown message sent, then all files removed after 1s
2. **On crash**: Files remain (agent can detect stale state)
3. **On restart**: New files overwrite old ones

## Summary

The automatic agent notification system makes voice loop integration seamless:

- ✅ **Agent learns automatically** when voice loop starts
- ✅ **Agent is notified** when voice loop stops
- ✅ **No manual configuration** needed
- ✅ **Clean state management** via file lifecycle
- ✅ **Production-ready** with proper error handling

Agents just need to check for `~/.molt-speak/runtime/agent_instructions.active` on startup!
