#!/bin/bash
echo "=== cmux Auto-Respond Uninstaller ==="

PLIST_LABEL="com.cmux-auto-respond"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

# Stop daemon
echo "Stopping daemon..."
launchctl unload "$LAUNCH_AGENTS/${PLIST_LABEL}.plist" 2>/dev/null || true

# Remove files
echo "Removing files..."
rm -f "$HOME/.local/bin/cmux-auto-respond.sh"
rm -f "$HOME/.local/bin/cmux-monitor-gui.py"
rm -f "$HOME/.local/bin/cmux-auto-tuner.py"
rm -f "$HOME/.local/bin/cmux-monitor-config.json"
rm -f "$LAUNCH_AGENTS/${PLIST_LABEL}.plist"
rm -rf "$HOME/Applications/cmux Monitor.app"

# Clean temp files
rm -f /tmp/cmux-auto-respond*

echo ""
echo "Uninstalled. Project source in $(pwd) is untouched."
