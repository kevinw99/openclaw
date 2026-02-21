#!/bin/bash
# Incremental WeChat message sync
# Run manually or via launchd for periodic extraction
#
# Usage:
#   ./scripts/sync-wechat.sh            # incremental sync
#   ./scripts/sync-wechat.sh --full     # full re-extraction
#
# Setup as daily cron:
#   crontab -e
#   0 2 * * * /Users/kweng/AI/openclaw/scripts/sync-wechat.sh >> /tmp/wechat-sync.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KEY_FILE="$HOME/.wechat_db_key"
LOG_FILE="/tmp/wechat-sync.log"

if [ ! -f "$KEY_FILE" ]; then
    echo "$(date): ERROR - Key file not found: $KEY_FILE" >> "$LOG_FILE"
    echo "Run scripts/extract_wechat_key.py first to extract the master key."
    exit 1
fi

INCREMENTAL="--incremental"
if [ "${1:-}" = "--full" ]; then
    INCREMENTAL=""
    echo "$(date): Starting full WeChat extraction..."
else
    echo "$(date): Starting incremental WeChat sync..."
fi

cd "$PROJECT_ROOT/src"
python3 -m knowledge_harvester extract-wechat --key-file "$KEY_FILE" $INCREMENTAL 2>&1

echo "$(date): Sync complete."
python3 -m knowledge_harvester stats
