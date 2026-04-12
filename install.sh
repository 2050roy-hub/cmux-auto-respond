#!/bin/bash
set -e

echo "=== cmux Auto-Respond Installer ==="
echo ""

# Detect paths
INSTALL_DIR="$HOME/.local/bin"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
APP_DIR="$HOME/Applications"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_LABEL="com.cmux-auto-respond"

# Check cmux
if ! command -v cmux &>/dev/null; then
    echo "ERROR: cmux not found. Install cmux first."
    exit 1
fi

# Check Python + tkinter
if ! python3 -c "import tkinter" &>/dev/null; then
    echo "ERROR: Python 3 with tkinter required."
    exit 1
fi

# Find Python.app path for GUI (needed on macOS for tkinter windows)
PYTHON_APP=$(python3 -c "import sys; print(sys.executable)" 2>/dev/null)
# Try to find the Python.app version
PYTHON_FRAMEWORK=$(python3 -c "
import sys, os
base = sys.base_prefix
app = os.path.join(base, 'Resources', 'Python.app', 'Contents', 'MacOS', 'Python')
if os.path.exists(app):
    print(app)
else:
    print(sys.executable)
" 2>/dev/null)

echo "Install directory: $INSTALL_DIR"
echo "Python GUI binary: $PYTHON_FRAMEWORK"
echo ""

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$LAUNCH_AGENTS"
mkdir -p "$APP_DIR"

# Copy source files
echo "[1/5] Installing scripts..."
cp "$SCRIPT_DIR/src/daemon.sh" "$INSTALL_DIR/cmux-auto-respond.sh"
cp "$SCRIPT_DIR/src/gui.py" "$INSTALL_DIR/cmux-monitor-gui.py"
cp "$SCRIPT_DIR/src/tuner.py" "$INSTALL_DIR/cmux-auto-tuner.py"
chmod +x "$INSTALL_DIR/cmux-auto-respond.sh"

# Update daemon to point to correct tuner path
sed -i '' "s|TUNER=.*|TUNER=\"${INSTALL_DIR}/cmux-auto-tuner.py\"|" "$INSTALL_DIR/cmux-auto-respond.sh"

# Generate and install launchd plist
echo "[2/5] Installing launchd service..."
sed "s|__INSTALL_DIR__|${INSTALL_DIR}|g" "$SCRIPT_DIR/src/launchd.plist.template" > "$LAUNCH_AGENTS/${PLIST_LABEL}.plist"

# Create .app bundle
echo "[3/5] Creating app bundle..."
APP_PATH="$APP_DIR/cmux Monitor.app"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

cat > "$APP_PATH/Contents/MacOS/launch" << LAUNCHER
#!/bin/bash
${PYTHON_FRAMEWORK} ${INSTALL_DIR}/cmux-monitor-gui.py
LAUNCHER
chmod +x "$APP_PATH/Contents/MacOS/launch"

cat > "$APP_PATH/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launch</string>
    <key>CFBundleName</key>
    <string>cmux Monitor</string>
    <key>CFBundleIdentifier</key>
    <string>com.cmux-auto-respond.gui</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
</dict>
</plist>
PLIST

# Copy icon if available
if [ -f "$SCRIPT_DIR/assets/AppIcon.icns" ]; then
    cp "$SCRIPT_DIR/assets/AppIcon.icns" "$APP_PATH/Contents/Resources/"
fi

# Register with LaunchServices
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true

# Start daemon
echo "[4/5] Starting daemon..."
launchctl unload "$LAUNCH_AGENTS/${PLIST_LABEL}.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS/${PLIST_LABEL}.plist"

# Init state files
echo "[5/5] Initializing..."
echo "0" > /tmp/cmux-auto-respond-cooldown
echo "normal" > /tmp/cmux-auto-respond-state
echo "0" > /tmp/cmux-auto-respond-actions

echo ""
echo "=== Installation Complete ==="
echo ""
echo "  Daemon:  Running (every 10 seconds)"
echo "  App:     $APP_PATH"
echo "  Log:     /tmp/cmux-auto-respond.log"
echo ""
echo "  Open the app:  open '$APP_PATH'"
echo "  View log:      cat /tmp/cmux-auto-respond.log"
echo ""
echo "  NOTE: Edit src/daemon.sh lines 10-11 to set your"
echo "        target surface and workspace, then re-run install.sh"
echo ""
