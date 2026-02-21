#!/usr/bin/env python3
"""WeChat macOS WCDB Master Password Extractor via LLDB

Extracts the PBKDF2 master password from WeChat's memory by intercepting
CCKeyDerivationPBKDF calls with 256,000 rounds (SQLCipher pattern).

The master password is used with per-DB salt derivation:
  raw_key = PBKDF2-HMAC-SHA512(master_password, db_first_16_bytes, 256000, 32)
  PRAGMA key = "x'<raw_key>'"

Requirements:
  - macOS Apple Silicon with SIP disabled (one-time operation)
  - WeChat installed
  - LLDB + codesign with debug entitlement

Usage:
  1. Disable SIP: Recovery Mode → csrutil disable → reboot
  2. Quit WeChat
  3. python3 scripts/extract_wechat_key.py
  4. Log in to WeChat when it opens
  5. Key will be captured and saved to ~/.wechat_db_key
  6. Re-enable SIP: Recovery Mode → csrutil enable → reboot
  7. Extract chats: PYTHONPATH=src python3 -m knowledge_harvester extract-wechat --key-file ~/.wechat_db_key
"""

import os
import re
import subprocess
import sys
import tempfile

KEY_OUTPUT = os.path.expanduser("~/.wechat_db_key")
LOG_OUTPUT = os.path.expanduser("~/.wechat_pbkdf_calls.log")
WECHAT_BIN = "/Applications/WeChat.app/Contents/MacOS/WeChat"
WECHAT_BACKUP = "/tmp/WeChat_backup2"


def _write_lldb_python(tmpdir: str) -> str:
    """Write the LLDB Python breakpoint handler script."""
    script = os.path.join(tmpdir, "extract_key.py")
    with open(script, "w") as f:
        f.write(f'''\
import lldb
import os

OUTPUT = "{LOG_OUTPUT}"
KEY_OUTPUT = "{KEY_OUTPUT}"
call_count = 0

def pbkdf_handler(frame, bp_loc, dict):
    """Intercept CCKeyDerivationPBKDF and capture master password.

    CCKeyDerivationPBKDF(algorithm, password, passwordLen, salt, saltLen, prf, rounds, derivedKey, derivedKeyLen)
    ARM64: x0=algorithm, x1=password, x2=passwordLen, x3=salt, x4=saltLen, x5=prf, x6=rounds, x7=derivedKey
    """
    global call_count
    call_count += 1

    process = frame.GetThread().GetProcess()
    x2 = frame.FindRegister("x2").GetValueAsUnsigned()  # passwordLen
    x6 = frame.FindRegister("x6").GetValueAsUnsigned()  # rounds

    # Only capture the first 256K-round call (SQLCipher master key derivation)
    if x6 != 256000 or x2 != 32:
        return False

    x1 = frame.FindRegister("x1").GetValueAsUnsigned()  # password ptr

    error = lldb.SBError()
    pw_bytes = process.ReadMemory(x1, 32, error)
    if not error.Success() or not pw_bytes:
        return False

    pw_hex = pw_bytes.hex()
    print(f"\\n*** WECHAT MASTER PASSWORD CAPTURED (call #{call_count}, rounds={x6}) ***")
    print(f"*** KEY: {{pw_hex}} ***\\n")

    with open(KEY_OUTPUT, "w") as kf:
        kf.write(pw_hex + "\\n")
    with open(OUTPUT, "a") as lf:
        lf.write(f"Call #{{call_count}}: rounds={{x6}}, pwLen={{x2}}, password_hex={{pw_hex}}\\n")

    # Detach so WeChat continues running normally
    process.Detach()
    lldb.debugger.HandleCommand("quit")
    return False
''')
    return script


def _write_debug_entitlements(tmpdir: str) -> str:
    """Write debug entitlements plist."""
    plist = os.path.join(tmpdir, "debug.plist")
    with open(plist, "w") as f:
        f.write('''\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>com.apple.security.get-task-allow</key><true/>
<key>com.apple.security.cs.allow-jit</key><true/>
<key>com.apple.security.cs.disable-library-validation</key><true/>
<key>com.apple.security.app-sandbox</key><true/>
<key>com.apple.security.network.client</key><true/>
<key>com.apple.security.network.server</key><true/>
<key>com.apple.security.files.downloads.read-write</key><true/>
<key>com.apple.security.files.user-selected.read-write</key><true/>
<key>com.apple.security.device.camera</key><true/>
<key>com.apple.security.device.audio-input</key><true/>
<key>com.apple.application-identifier</key><string>5A4RE8SF68.com.tencent.xinWeChat</string>
<key>com.apple.security.application-groups</key><array><string>5A4RE8SF68.com.tencent.xinWeChat</string></array>
</dict></plist>
''')
    return plist


def main():
    # Check SIP
    r = subprocess.run(["csrutil", "status"], capture_output=True, text=True)
    if "disabled" not in r.stdout.lower():
        print("ERROR: SIP is not disabled.")
        print("  1. Restart Mac → hold Power button → Recovery Mode")
        print("  2. Terminal → csrutil disable → reboot")
        sys.exit(1)

    if not os.path.exists(WECHAT_BIN):
        print(f"WeChat not found at {WECHAT_BIN}")
        sys.exit(1)

    # Check if WeChat is running
    r = subprocess.run(["pgrep", "-x", "WeChat"], capture_output=True, text=True)
    if r.returncode == 0:
        print("Killing running WeChat...")
        subprocess.run(["pkill", "-x", "WeChat"])
        import time; time.sleep(2)

    tmpdir = tempfile.mkdtemp(prefix="wechat_key_")

    # Backup and re-sign WeChat binary with debug entitlements
    print("Re-signing WeChat with debug entitlements...")
    if not os.path.exists(WECHAT_BACKUP):
        subprocess.run(["cp", WECHAT_BIN, WECHAT_BACKUP], check=True)
    plist = _write_debug_entitlements(tmpdir)
    subprocess.run([
        "codesign", "--force", "-s", "-",
        "--entitlements", plist, WECHAT_BIN
    ], check=True)

    # Write LLDB Python handler and command file
    py_script = _write_lldb_python(tmpdir)
    module_name = os.path.splitext(os.path.basename(py_script))[0]
    lldb_file = os.path.join(tmpdir, "extract.lldb")
    with open(lldb_file, "w") as f:
        f.write(f'''\
target create "{WECHAT_BIN}"
command script import {py_script}
breakpoint set -n CCKeyDerivationPBKDF
breakpoint command add -F {module_name}.pbkdf_handler 1
breakpoint modify 1 --auto-continue true
run
''')

    print()
    print("=" * 60)
    print("Launching WeChat under LLDB...")
    print("LOG IN to WeChat when it opens.")
    print("The master password will be captured automatically.")
    print("=" * 60)
    print()

    # Clear old log
    open(LOG_OUTPUT, "w").close()

    try:
        result = subprocess.run(
            ["lldb", "-b", "-s", lldb_file],
            timeout=300
        )
    except subprocess.TimeoutExpired:
        print("Timed out after 5 minutes.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)

    # Check result
    if os.path.exists(KEY_OUTPUT):
        with open(KEY_OUTPUT) as f:
            hex_key = f.read().strip()
        if hex_key and len(hex_key) == 64:
            print()
            print("=" * 60)
            print(f"MASTER PASSWORD: {hex_key}")
            print(f"Saved to: {KEY_OUTPUT}")
            print("=" * 60)
            print()
            print("Next steps:")
            print("  1. Re-enable SIP (Recovery Mode → csrutil enable → reboot)")
            print("  2. Extract chats:")
            print(f"     PYTHONPATH=src python3 -m knowledge_harvester extract-wechat --key-file {KEY_OUTPUT}")
            return

    print()
    print("Failed to capture the key.")
    print("Check log:", LOG_OUTPUT)


if __name__ == "__main__":
    main()
