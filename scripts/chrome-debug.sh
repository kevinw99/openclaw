#!/bin/bash
# Restart Chrome with remote debugging enabled
# Chrome 145+ blocks remote debugging on the default data directory,
# so we create a wrapper dir that symlinks to the real profile.
#
# Usage:
#   ./scripts/chrome-debug.sh          # restart Chrome with debugging on port 9222
#   ./scripts/chrome-debug.sh stop     # quit debug Chrome, relaunch normal Chrome

PORT=9222
DEBUG_DIR="/tmp/chrome-debug-profile"
CHROME_USER_DATA="$HOME/Library/Application Support/Google/Chrome"

if [ "${1:-}" = "stop" ]; then
    echo "Stopping debug Chrome..."
    pkill -9 "Google Chrome" 2>/dev/null
    sleep 2
    rm -rf "$DEBUG_DIR"
    rm -f "$CHROME_USER_DATA/SingletonLock" 2>/dev/null
    echo "Starting normal Chrome..."
    open -a "Google Chrome"
    echo "Done."
    exit 0
fi

# Check if already in debug mode
if curl -s "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
    echo "Chrome is already running with debugging on port $PORT"
    curl -s "http://127.0.0.1:$PORT/json/version" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Browser: {d.get(\"Browser\",\"?\")}'); print(f'  WS: {d.get(\"webSocketDebuggerUrl\",\"?\")}')"
    exit 0
fi

echo "Stopping Chrome..."
pkill -9 "Google Chrome" 2>/dev/null
sleep 3
rm -f "$CHROME_USER_DATA/SingletonLock" 2>/dev/null

# Create wrapper data-dir with symlinked profile (Chrome 145+ workaround)
rm -rf "$DEBUG_DIR"
mkdir -p "$DEBUG_DIR"
ln -sf "$CHROME_USER_DATA/Default" "$DEBUG_DIR/Default"
ln -sf "$CHROME_USER_DATA/Local State" "$DEBUG_DIR/Local State"

echo "Launching Chrome with debugging on port $PORT..."
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=$PORT \
    --user-data-dir="$DEBUG_DIR" 2>/dev/null &

for i in $(seq 1 15); do
    if curl -s "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
        echo "Chrome ready! Debugging active on port $PORT"
        echo ""
        echo "Now run:"
        echo "  node scripts/extract_grok.mjs"
        echo "  node scripts/extract_doubao.mjs"
        echo ""
        echo "When done:"
        echo "  ./scripts/chrome-debug.sh stop"
        exit 0
    fi
    sleep 1
done

echo "Timeout. Check if Chrome started correctly."
