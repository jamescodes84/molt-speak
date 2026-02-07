# Intelligent Window Targeting

OpenClaw Ears now includes sophisticated window targeting to automatically find and type into the correct Terminal window/tab where your OpenClaw agent is running.

## How It Works

Instead of typing into whichever window happens to be focused, OpenClaw Ears:

1. **Searches all Terminal windows and tabs** for one matching your configuration
2. **Activates that specific window/tab** (if configured to do so)
3. **Types the transcribed text** into the correct terminal
4. **Presses Enter** to execute the command

## Configuration

Configure window targeting via environment variables:

### TARGET_WINDOW_PATTERN

The pattern to search for in Terminal window titles (case-insensitive).

```bash
export TARGET_WINDOW_PATTERN="openclaw"
```

**How it works:**
- OpenClaw Ears searches all Terminal windows/tabs
- Finds the first tab whose title contains this pattern (case-insensitive)
- Types into that specific tab

**Examples:**
- `"openclaw"` - Finds terminal with "openclaw" or "OpenClaw" in title
- `"agent"` - Finds terminal with "agent" in title
- `"claude"` - Finds terminal with "claude" in title
- `""` (empty) - Uses frontmost Terminal window (fallback behavior)

### ACTIVATE_TARGET_WINDOW

Whether to bring the target window to the front before typing.

```bash
export ACTIVATE_TARGET_WINDOW="true"  # Default
```

**Options:**
- `"true"` - Activates Terminal and brings window to front
- `"false"` - Types without switching focus (background typing)

## Usage Example

### 1. Set up your environment

Create a `.env` file in the `open_ears` directory:

```bash
# .env
TARGET_WINDOW_PATTERN=openclaw
ACTIVATE_TARGET_WINDOW=true
```

### 2. Name your Terminal window

When running your OpenClaw agent, make sure the Terminal tab has an identifiable name. You can:

**Option A:** Set terminal title in your shell:
```bash
# In your OpenClaw agent terminal
echo -n -e "\033]0;OpenClaw Agent\007"
```

**Option B:** Terminal.app automatically uses running command:
- If your agent is called `openclaw`, the window title will contain "openclaw"

**Option C:** Manually rename the tab:
- Terminal.app: Window → Inspector → Tab Name

### 3. Start OpenClaw Ears

```bash
cd open_ears
./start_voice_system.sh
```

OpenClaw Ears will now automatically find and type into the correct Terminal tab!

## Fallback Behavior

If no matching window is found:
1. Uses the frontmost Terminal window
2. If that fails, falls back to pyautogui (types into any focused window)

## How to Identify Your Terminal

The window targeting searches Terminal tab names. To see what your tab names are:

1. Open Terminal Inspector: Window → Inspector
2. Look at the "Tab Name" field
3. Use part of that name as your `TARGET_WINDOW_PATTERN`

**Example tab names:**
- `bash — 80×24` (default terminal)
- `python main.py — 80×24` (running python)
- `openclaw-agent` (custom renamed tab)

## Troubleshooting

### Voice input not appearing in my terminal

**Check:**
1. Is your terminal tab name visible and contains your pattern?
   ```bash
   # In your agent's terminal, run:
   echo -n -e "\033]0;OpenClaw Agent\007"
   ```

2. Is the pattern configured correctly?
   ```bash
   # Check your .env file
   cat .env | grep TARGET_WINDOW_PATTERN
   ```

3. Try using an empty pattern (uses frontmost window):
   ```bash
   export TARGET_WINDOW_PATTERN=""
   ```

### Window keeps popping to front

If you don't want Terminal to activate every time:

```bash
export ACTIVATE_TARGET_WINDOW="false"
```

This will type in the background without switching focus.

### Multiple terminals match the pattern

OpenClaw Ears uses the **first match** it finds. To be more specific:
- Use a more unique pattern
- Rename your agent's terminal tab to something distinctive

## Advanced: Custom AppleScript

The window targeting uses AppleScript under the hood. The script:

1. Iterates through all Terminal windows
2. Checks each tab's name against the pattern (case-insensitive)
3. Activates the matching window and tab
4. Uses `do script` to type the text and press Enter

If you need even more sophisticated targeting, you can modify the AppleScript in:
`src/core/voice_pipeline.py` → `_send_to_openclaw_tui()` method

## Performance

**Latency:** ~50-200ms overhead for window searching
**Impact:** Minimal - caching could reduce this to <50ms
**Trade-off:** Reliability vs. speed (worth it for correct targeting)

## Comparison: Old vs New

**Old Behavior (focus-based):**
- ❌ Types into whatever window is focused
- ❌ Unreliable ("doesn't work half the time")
- ❌ User must manually focus correct window before speaking
- ✅ Fast (<10ms)

**New Behavior (intelligent search):**
- ✅ Finds correct window automatically
- ✅ Reliable (works even if window is hidden/unfocused)
- ✅ No manual window switching needed
- ✅ Configurable patterns
- ⚠️ Slightly slower (~50-200ms)

## Example Complete Workflow

```bash
# Terminal 1: OpenClaw Agent
echo -n -e "\033]0;OpenClaw Agent\007"  # Set tab title
python openclaw_agent.py

# Terminal 2: OpenClaw Ears
cd open_ears
export TARGET_WINDOW_PATTERN="openclaw"
export ACTIVATE_TARGET_WINDOW="true"
./start_voice_system.sh

# Terminal 3: OpenClaw Mouth
cd open_mouth
./start_speech_system.sh

# Now speak! Text appears in Terminal 1 automatically
# No need to focus Terminal 1 - it finds it automatically
```

## Summary

The new intelligent window targeting makes OpenClaw Ears much more reliable by:

1. **Automatically finding** the correct terminal
2. **Activating it** (optional)
3. **Typing commands** in the right place
4. **Pressing Enter** to execute

Configure via `TARGET_WINDOW_PATTERN` and enjoy hands-free voice input without manual window management!
