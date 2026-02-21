#!/bin/bash
# WeChat WCDB Key Extractor (macOS ARM64)
# Requires: SIP disabled, sudo access

set -e

KEY_FILE="$HOME/.wechat_db_key"
WECHAT_BIN="/Applications/WeChat.app/Contents/MacOS/WeChat"
LLDB_CMD_FILE=$(mktemp /tmp/wechat_lldb.XXXXXX)

if ! csrutil status 2>&1 | grep -q "disabled"; then
    echo "ERROR: SIP is not disabled"
    exit 1
fi

echo "============================================================"
echo "WeChat WCDB Key Extractor"
echo "============================================================"

# Launch WeChat in background
echo "Launching WeChat..."
open -a WeChat
sleep 2

WECHAT_PID=$(pgrep -x WeChat || true)
if [ -z "$WECHAT_PID" ]; then
    echo "ERROR: WeChat failed to start"
    exit 1
fi
echo "WeChat PID: $WECHAT_PID"

# Write LLDB commands
# When breakpoint hits sqlite3_key:
#   x1 = pointer to key bytes (ARM64 2nd arg)
#   Read 32 bytes and write hex to file
cat > "$LLDB_CMD_FILE" << 'LLDB_EOF'
breakpoint set -n sqlite3_key
breakpoint command add 1
script
import lldb
target = lldb.debugger.GetSelectedTarget()
process = target.GetProcess()
thread = process.GetSelectedThread()
frame = thread.GetSelectedFrame()
x1 = frame.FindRegister("x1").GetValueAsUnsigned()
x2 = frame.FindRegister("x2").GetValueAsUnsigned()
key_len = x2 if 0 < x2 <= 64 else 32
error = lldb.SBError()
key_bytes = process.ReadMemory(x1, key_len, error)
if error.Success() and key_bytes:
    hex_key = key_bytes.hex()
    print("\n============================================================")
    print("WECHAT KEY: " + hex_key)
    print("============================================================")
    with open("KEY_FILE_PLACEHOLDER", "w") as f:
        f.write(hex_key + "\n")
    print("Saved to KEY_FILE_PLACEHOLDER")
process.Detach()
lldb.debugger.HandleCommand("quit")
DONE
continue
LLDB_EOF

# Replace placeholder with actual path
sed -i '' "s|KEY_FILE_PLACEHOLDER|$KEY_FILE|g" "$LLDB_CMD_FILE"

echo ""
echo "Attaching LLDB with sudo (you may be prompted for password)..."
echo "After attaching, LOG IN to WeChat if not already logged in."
echo "The key will be captured when WeChat opens its database."
echo ""

# Attach to WeChat with sudo and run commands
sudo lldb -p "$WECHAT_PID" -s "$LLDB_CMD_FILE"

# Check result
if [ -f "$KEY_FILE" ]; then
    KEY=$(cat "$KEY_FILE" | tr -d '[:space:]')
    if [ -n "$KEY" ]; then
        echo ""
        echo "============================================================"
        echo "SUCCESS! Key: $KEY"
        echo "Saved to: $KEY_FILE"
        echo "============================================================"
        echo ""
        echo "Next steps:"
        echo "  1. Re-enable SIP (Recovery → csrutil enable → reboot)"
        echo "  2. Extract chats:"
        echo "     cd $(pwd) && python3 -m knowledge_harvester extract-wechat --key $KEY"
        exit 0
    fi
fi

echo ""
echo "Key not captured. WeChat may not have opened a DB."
echo "Try: quit WeChat, run this script again, then log in."
rm -f "$LLDB_CMD_FILE"
