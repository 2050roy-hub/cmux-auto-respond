# cmux Auto-Respond

Automate Claude Code interactions inside [cmux](https://cmux.dev) terminals. The daemon monitors Claude Code sessions and automatically responds to prompts, rotates sessions when context gets too large, and self-tunes the rotation threshold to minimize token usage.

## Features

- **Auto-respond** — Automatically press `1` on file creation prompts, answer "繼續" to continue prompts, and send custom responses to idle sessions
- **Session rotation** — When context usage exceeds a threshold, automatically saves memory → exits → starts a new Claude → continues work
- **Self-tuning** — Tracks token usage across sessions and automatically adjusts the rotation threshold to minimize cost
- **GUI control panel** — macOS native app to toggle the daemon, configure rules, and monitor activity
- **launchd integration** — Runs as a macOS background service, survives reboots, auto-restarts

## How It Works

```
┌─────────────┐    every 10s    ┌──────────────┐
│   launchd   │ ──────────────► │  daemon.sh   │
└─────────────┘                 └──────┬───────┘
                                       │
                          cmux read-screen / send
                                       │
                                ┌──────▼───────┐
                                │ Claude Code  │
                                │  (surface)   │
                                └──────────────┘

Session Rotation Flow:
Context ≥ 30% → "記到 memory" → /exit → claude → "繼續之前的動作"
      ▲                                                    │
      └──── tuner.py analyzes & adjusts threshold ◄────────┘
```

## Requirements

- macOS
- [cmux](https://cmux.dev)
- Python 3 with tkinter (included with macOS Python)
- Claude Code CLI (`claude`)

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/cmux-auto-respond.git
cd cmux-auto-respond
./install.sh
```

## Configuration

### Target Surface

Edit `src/daemon.sh` lines 10-11 to set your target:

```bash
SURF="surface:9"    # cmux surface to monitor
WS="workspace:1"    # cmux workspace
```

Find your surface with:
```bash
cmux tree --all
```

### GUI Control Panel

Open the app from `~/Applications/cmux Monitor.app` or:

```bash
open ~/Applications/cmux\ Monitor.app
```

The control panel lets you:
- Start/stop the daemon
- Adjust check interval (default: 10 seconds)
- Enable/disable individual rules
- Edit response text for each rule
- Customize session rotation prompts
- View auto-tuner statistics
- Monitor activity log

### Auto-Respond Rules

| Trigger | Default Response | Editable |
|---------|-----------------|----------|
| `Do you want to create/edit?` | `1` (Yes) | ✓ |
| 繼續嗎 / 要不要 / 是否 | `繼續` | ✓ |
| Other questions (？/嗎/呢) | `繼續去爬文進化` | ✓ |
| Rating prompt | `3` (Good) | ✓ |
| Idle (nothing to do) | `去爬文進化` | ✓ |
| Context ≥ threshold | Session rotation | ✓ |

### Auto-Tuner

The tuner tracks token consumption across sessions and explores different thresholds (20%–60%) to find the most efficient rotation point. It adjusts automatically after every 3 rotations.

View tuner stats:
```bash
python3 ~/.local/bin/cmux-auto-tuner.py status
```

## File Structure

```
cmux-auto-respond/
├── README.md
├── install.sh              # One-command installer
├── uninstall.sh            # Clean uninstaller
├── src/
│   ├── daemon.sh           # Main monitoring daemon (runs via launchd)
│   ├── gui.py              # tkinter control panel
│   ├── tuner.py            # Auto-tuning engine
│   └── launchd.plist.template
├── assets/
│   └── AppIcon.icns        # App icon
└── scripts/                # (future utility scripts)
```

## Management

```bash
# View log
cat /tmp/cmux-auto-respond.log

# Check daemon status
launchctl list | grep cmux-auto-respond

# Manual stop/start
launchctl unload ~/Library/LaunchAgents/com.cmux-auto-respond.plist
launchctl load ~/Library/LaunchAgents/com.cmux-auto-respond.plist

# Uninstall
./uninstall.sh
```

## How Session Rotation Works

1. Daemon detects context usage ≥ threshold (default 30%)
2. Sends "save progress to memory" to Claude
3. Waits for Claude to finish saving
4. Sends `/exit` to quit the session
5. Waits for shell prompt
6. Starts new `claude` session
7. Sends "continue previous work"
8. Tuner records token stats and may adjust threshold

The entire process is automatic and takes ~30-60 seconds.

## License

MIT
