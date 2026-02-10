# OpenClaw Voice Loop - Menu Bar Control

A unified macOS menu bar application for controlling all three OpenClaw systems from a single interface.

## Features

### 🎯 Quick Setup (New!)
- **One-Click Command Copy** - Copy terminal title command to clipboard instantly
- **No Manual Typing** - Just click "Copy Terminal Title Command" and paste
- **Setup Steps Guide** - Built-in quick start instructions
- **Pattern Configuration** - Easy access to window targeting settings

### System Control
- **Start/Stop Complete Voice Loop** - Launch all three systems with one click
- **Individual System Control** - Start/stop Integration, Mouth, or Ears independently
- **Real-time Status Monitoring** - See which systems are running at a glance
- **Visual Status Indicators** - Menu bar icon changes based on system state

### Log Viewing
- **View Individual Logs** - Open logs for Integration, Mouth, or Ears in Terminal
- **Combined Log View** - Open all three logs simultaneously in separate tabs
- **Live Updates** - Logs open with `tail -f` for real-time monitoring

### Configuration
- **Quick Config Access** - Open ~/.openclaw directory
- **View Agent Instructions** - See current active instructions
- **Window Targeting Help** - Access window targeting configuration
- **Project Folder Access** - Open project directory

### Setup Instructions
- **Copy Terminal Title Command** - Copy the echo command to clipboard with one click
- **Show Setup Steps** - Quick guide for getting started
- **Configure Window Pattern** - View and modify window targeting pattern

### Help & Documentation
- **Quick Start Guide** - View QUICK_START.md
- **Window Targeting Docs** - Read detailed targeting documentation
- **Troubleshooting** - Common issues and solutions

## Installation

### Requirements

The menu bar app requires the `rumps` library:

```bash
pip install rumps
```

Or install automatically when you first run it.

### Running

```bash
./start_menu_bar.sh
```

The menu bar icon (🎙️) will appear in your macOS status bar.

## Menu Structure

```
🎙️
├── ✅ Voice Loop Active / ⚪ Voice Loop Inactive
├── ──────────────
├── System Status
│   ├── ✅/⚪ Integration Coordinator
│   ├── ✅/⚪ OpenClaw Mouth
│   └── ✅/⚪ OpenClaw Ears
├── ──────────────
├── ▶️  Start Voice Loop / ⏹️  Stop Voice Loop
├── ──────────────
├── Individual Controls
│   ├── Start/Stop Integration
│   ├── Start/Stop Mouth
│   └── Start/Stop Ears
├── ──────────────
├── 📋 View Logs
│   ├── Integration Log
│   ├── Mouth Log
│   ├── Ears Log
│   ├── ──────────────
│   └── All Logs (Combined)
├── ⚙️  Configuration
│   ├── Open Config Directory
│   ├── View Agent Instructions
│   └── Window Targeting Settings
├── ──────────────
├── 📁 Open Project Folder
├── 🔄 Refresh Status
├── ──────────────
├── 📝 Setup Instructions
│   ├── Copy Terminal Title Command
│   ├── Show Setup Steps
│   ├── ──────────────
│   └── Configure Window Pattern
├── ❓ Help
│   ├── Quick Start Guide
│   ├── Window Targeting Docs
│   └── Troubleshooting
├── ──────────────
└── Quit Menu Bar App
```

## Status Icons

### Menu Bar Icon
- **🔴🎙️** - Voice loop inactive (systems not running)
- **🟢🎙️** - Voice loop active (all three systems running)

### System Status Indicators
- **✅** - System is running
- **⚪** - System is not running

## Usage Examples

### Start Everything
1. Click menu bar icon (🔴🎙️)
2. Click "▶️  Start Voice Loop"
3. All three systems launch automatically
4. Icon changes to 🟢🎙️ (green = active!)

### Stop Everything
1. Click menu bar icon (🟢🎙️)
2. Click "⏹️  Stop Voice Loop"
3. All systems shut down gracefully
4. Icon changes to 🔴🎙️ (red = inactive)

### View Logs
1. Click menu bar icon
2. Hover over "📋 View Logs"
3. Select which log to view
4. New Terminal window opens with live log

### Individual Control
1. Click menu bar icon
2. Hover over "Individual Controls"
3. Start/stop specific systems

### Set Up Terminal Title (Easy Way!)
1. Click menu bar icon
2. Click "📝 Setup Instructions"
3. Click "Copy Terminal Title Command"
4. Command is copied to clipboard automatically
5. Paste into your OpenClaw agent's terminal
6. Done! OpenClaw Ears can now find your terminal

## Quitting the Menu Bar App

When you quit the menu bar app, you'll be asked:

**"Do you want to stop the voice loop first?"**

- **Just Quit** - Quit menu bar app, leave systems running
- **Stop & Quit** - Stop all systems, then quit app
- **Cancel** - Don't quit

This prevents accidentally leaving systems running when you meant to shut everything down.

## Integration with Voice Loop

The menu bar app works seamlessly with manual control:

- **Starting via menu bar** - Same as running `./start_voice_loop.sh`
- **Stopping via menu bar** - Same as running `./stop_voice_loop.sh`
- **Status monitoring** - Checks PID files in `~/.openclaw/`
- **Log viewing** - Opens logs from `~/.openclaw/logs/`

## Automatic Updates

The menu bar app updates every 2 seconds:

- Checks which systems are running
- Updates menu icon
- Rebuilds menu if status changed

## Keyboard-Free Operation

Everything can be done with mouse only:

1. Click menu bar icon
2. Navigate to desired action
3. Click to execute

Perfect for quick controls while working on other tasks.

## Tips

### Keep It Running
- Start the menu bar app when you begin working
- Leave it running in the background
- Quick access to all voice loop controls

### Monitor Status
- Glance at icon to see if voice loop is active
- Check "System Status" to see which components are running
- No need to check terminal windows

### Quick Log Access
- View logs without navigating to ~/.openclaw
- See all logs at once with "All Logs (Combined)"
- Real-time updates with tail -f

### Fast Restarts
- Stop voice loop
- Make changes
- Start voice loop again
- All from menu bar

## Troubleshooting

### Menu bar icon doesn't appear
- Make sure rumps is installed: `pip install rumps`
- Run from Terminal to see error messages
- Check macOS permissions for the app

### Systems won't start
- Check that scripts are executable
- Verify Python environments are set up
- View individual logs to see errors

### Status not updating
- Try "🔄 Refresh Status"
- Restart the menu bar app
- Check if PID files exist in ~/.openclaw/

### Can't view logs
- Ensure systems have been started at least once
- Check ~/.openclaw/logs/ directory exists
- Verify log files have content

## Advanced

### Running at Login

To start menu bar app automatically on login:

1. System Preferences → Users & Groups
2. Login Items
3. Add: `/path/to/start_menu_bar.sh`

### Custom Configuration

The menu bar app respects all voice loop configurations:

- Window targeting patterns
- Voice selections (for Mouth)
- Integration coordinator settings

### Background Operation

The menu bar app is lightweight:
- Minimal CPU usage (~0.1%)
- Small memory footprint (~20MB)
- Updates only when status changes

## Development

### Project Structure

```
open_speak/
├── unified_menu_bar.py      # Main menu bar application
├── start_menu_bar.sh         # Launcher script
└── MENU_BAR_APP.md          # This file
```

### Dependencies

- **rumps** - macOS menu bar framework
- **Python 3.8+** - Required for Path and type hints

### Extending

The menu bar app can be extended to add:
- Voice configuration (already in open_mouth menu bar)
- Quick actions (test voice, configure settings)
- Status notifications
- System health monitoring

## Summary

The unified menu bar app provides:

✅ **One-click control** of entire voice loop
✅ **Real-time status** monitoring
✅ **Quick log access** for debugging
✅ **Configuration shortcuts** for common tasks
✅ **Help & documentation** built-in
✅ **Keyboard-free** operation
✅ **Lightweight** background process
✅ **Graceful shutdown** options

Perfect for managing the OpenClaw Voice Loop during development and daily use!
