# Design: WeChat Continuous Message Sync

## Track A: Local DB Polling — Detailed Design

### How It Works

WeChat desktop stores messages in encrypted SQLite (WCDB) files at:

```
~/Library/Containers/com.tencent.xinWeChat/Data/Documents/
  xwechat_files/{wxid}_{hash}/db_storage/message/
```

The existing `knowledge_harvester` WeChat adapter already handles:

- WCDB v4 detection (`Msg_<hash>` tables)
- Legacy format fallback (`MSG` table)
- SQLCipher decryption (PBKDF2-HMAC-SHA512)
- Contact name mapping via `contact.db`
- Normalized JSONL output

What's missing: **automation** — running this periodically and tracking what's new.

### Component: wechat-sync daemon

A lightweight poller that wraps the existing adapter.

```
wechat-sync
├── poll()          # Check DB for new messages since last sync
├── schedule()      # Register with macOS launchd
├── on_change()     # Triggered by fswatch on DB files
└── report()        # Show sync stats
```

#### State Tracking

File: `~/.openclaw/knowledge/extractions/wechat/sync-state.json`

```json
{
  "last_sync": "2026-02-21T08:00:00Z",
  "last_local_id": 54321,
  "conversations_synced": 431,
  "total_messages": 41814,
  "sync_history": [
    { "timestamp": "2026-02-21T08:00:00Z", "new_messages": 127, "new_conversations": 2 }
  ]
}
```

The WeChat WCDB uses auto-incrementing `local_id` as primary key. We track the highest `local_id` seen and query `WHERE local_id > last_local_id` for incremental sync.

#### Schedule Options

**Option 1: launchd (recommended for macOS)**

```xml
<!-- ~/Library/LaunchAgents/com.openclaw.wechat-sync.plist -->
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.openclaw.wechat-sync</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>-m</string>
    <string>knowledge_harvester</string>
    <string>extract-wechat</string>
    <string>--key-file</string>
    <string>~/.wechat_db_key</string>
    <string>-i</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/kweng/AI/openclaw/src</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>/Users/kweng/AI/openclaw/src</string>
  </dict>
  <key>StartInterval</key>
  <integer>21600</integer>  <!-- Every 6 hours -->
  <key>StandardOutPath</key>
  <string>/tmp/wechat-sync.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/wechat-sync-error.log</string>
</dict>
</plist>
```

**Option 2: fswatch (event-driven)**

Watch for DB file changes and trigger extraction:

```bash
fswatch -o ~/Library/Containers/com.tencent.xinWeChat/ \
  --include '\.db$' --exclude '.*' \
  | xargs -n1 -I{} python3 -m knowledge_harvester extract-wechat --key-file ~/.wechat_db_key -i
```

**Recommendation**: Use launchd as primary (reliable, survives reboots), fswatch as optional supplement for faster detection.

### Incremental Extraction Logic

```python
def extract_incremental(db_path, key_file, state):
    """Extract only new messages since last sync"""

    last_id = state.get("last_local_id", 0)

    # Query all message tables for new rows
    for table in discover_message_tables(db_path):
        rows = query(f"""
            SELECT * FROM {table}
            WHERE local_id > ?
            ORDER BY local_id ASC
        """, [last_id])

        for row in rows:
            yield normalize_message(row)
            last_id = max(last_id, row["local_id"])

    state["last_local_id"] = last_id
    state["last_sync"] = now()
```

---

## Track B: Phone Sync Workflow

### Step-by-Step Procedure

1. **On iPhone**: Open WeChat → Me → Settings → General → Chat Log Migration and Backup
2. Select "Migrate to Another Device" → "Transfer to Computer"
3. Choose conversations to sync (or "Select All")
4. Ensure iPhone and Mac are on the same WiFi network
5. Desktop WeChat will show a QR code — scan it from phone
6. Wait for transfer (5-30 min depending on volume)
7. After completion, run extraction:
   ```bash
   cd /Users/kweng/AI/openclaw/src
   PYTHONPATH=. python3 -m knowledge_harvester extract-wechat --key-file ~/.wechat_db_key -i
   ```

### `/sync-wechat` Skill Design

```
User: /sync-wechat

Claude: Starting WeChat sync workflow.

Step 1: Please sync your phone messages to desktop WeChat:
  - iPhone: Settings → General → Chat Log Migration → Transfer to Computer
  - Wait for transfer to complete

Step 2: Once done, tell me "done" and I'll extract the new messages.

User: done

Claude: [runs extract-wechat -i]
  → Found 1,247 new messages across 89 conversations
  → Knowledge base updated: ~/.openclaw/knowledge/extractions/wechat/
  → Total: 43,061 messages (was 41,814)
```

---

## Track C: Real-Time Alternatives — Evaluation Matrix

**Evaluate only. Do not build until Track A+B are working.**

### WeChatFerry

```
Approach:     Windows PC hook (inject DLL into WeChat.exe)
Platform:     Windows only (VM/Docker+Wine possible on Mac)
Risk:         High — hook injection is detectable
Status:       Active (org fork: github.com/wechatferry/wechatferry)
License:      MIT
Cost:         Free
Languages:    Python, NodeJS, C#, Rust SDKs
Capabilities: Full — send/receive, contacts, groups, files
```

**Evaluation path**:

1. Set up Windows VM with pinned WeChat version
2. Install WeChatFerry with a secondary/test WeChat account
3. Run for 2 weeks, monitor for ban/restrictions
4. If stable, build adapter using Python SDK

### AstrBot + WeChatPadPro

```
Approach:     Pad protocol (similar to PadLocal, actively maintained)
Platform:     Cross-platform (Docker)
Risk:         Medium — same category as PadLocal but actively maintained
Status:       Very active (17k stars, daily commits)
License:      AGPL-3.0
Cost:         WeChatPadPro token required (paid, pricing varies)
Capabilities: Full messaging, no Moments
```

**Evaluation path**:

1. Purchase WeChatPadPro token (cheapest tier)
2. Deploy AstrBot via Docker
3. Test with secondary account for 2 weeks
4. If stable, either use AstrBot directly or build openclaw adapter

### Decision Criteria

| Criterion              | Weight | WeChatFerry            | AstrBot+PadPro         |
| ---------------------- | ------ | ---------------------- | ---------------------- |
| Ban risk               | 30%    | High (hook)            | Medium (pad)           |
| Maintenance likelihood | 25%    | Good (OSS, org-backed) | Good (large community) |
| Platform compatibility | 20%    | Poor (Windows only)    | Good (Docker)          |
| Cost                   | 15%    | Free                   | Paid token             |
| Feature completeness   | 10%    | Full                   | Full minus Moments     |

---

## Track D: Media & Compressed Content Extraction

### Current Gap (Updated 2026-02-22)

**Resolved:**
- `[压缩文本]` — **FIXED**: 225K messages recovered via Zstandard decompression
- `[链接/文件]` — **FIXED**: Type-49 XML parsing extracts filename, URL, size, description
- Media file paths — **FIXED**: 3,909 files/videos linked to messages via `MediaRef.path`

**Still placeholders:**
- `[图片]` — images (msg_type 3) — .dat files use proprietary format (NOT simple XOR on macOS)
- `[语音]` — voice messages (msg_type 34) — unknown format
- `[视频]` — videos (msg_type 43) — files exist unencrypted, path resolved to directory level

### WeChat Media Storage Map

```
~/Library/Containers/com.tencent.xinWeChat/Data/Documents/
  xwechat_files/{wxid}_{hash}/
  │
  ├── msg/
  │   ├── attach/<md5_contact>/YYYY-MM/
  │   │   ├── Img/         ← Images (.dat, XOR encrypted)
  │   │   ├── Rec/         ← Voice messages (.dat, encrypted)
  │   │   └── Thumb/       ← Thumbnails
  │   ├── file/YYYY-MM/    ← PDFs, DOCX, XLSX (READABLE as-is)
  │   └── video/YYYY-MM/   ← MP4/M4V files (READABLE as-is)
  │
  ├── cache/YYYY-MM/Message/<md5_contact>/
  │   └── Thumb/{msg_id}_timestamp_thumb.jpg  ← Thumbnails (READABLE)
  │
  └── db_storage/message/
      ├── message_*.db     ← Message content + compressed text
      └── media_0.db       ← Media metadata index
```

### What's Extractable

| Content                 | Location                 | Encryption             | Difficulty | Priority |
| ----------------------- | ------------------------ | ---------------------- | ---------- | -------- |
| **Videos**              | `msg/video/`             | None (plain MP4)       | Easy       | P1       |
| **Files (PDF/DOC/XLS)** | `msg/file/`              | None (original format) | Easy       | P1       |
| **Image thumbnails**    | `cache/*/Thumb/`         | None (JPEG)            | Easy       | P1       |
| **Images (full)**       | `msg/attach/*/Img/*.dat` | Proprietary (NOT XOR on macOS) | Hard | P3 |
| **Compressed text**     | DB `message_content`     | ~~zlib~~ **Zstandard** | ~~Medium~~ **Done** | ✅ |
| **Voice messages**      | `msg/attach/*/Rec/*.dat` | Unknown                | Hard       | P3       |
| **Link previews**       | DB (type 49, compressed) | protobuf               | Hard       | P3       |

### Phase D1: Files, Videos, Image Decryption (Easy Wins)

#### Video & File Extraction

Videos (`msg/video/`) and files (`msg/file/`) are stored **unencrypted** in their original formats. Simply copy and index them.

```python
def extract_media_files(wechat_root, output_dir):
    """Copy readable media files and build index"""

    # Videos: msg/video/YYYY-MM/*.mp4
    for video in glob(f"{wechat_root}/msg/video/**/*.mp4"):
        # Copy to knowledge base, index by date

    # Files: msg/file/YYYY-MM/*
    for doc in glob(f"{wechat_root}/msg/file/**/*"):
        # Copy PDFs, DOCX, etc. to knowledge base
```

#### Image .dat Format — macOS (Research Needed)

> **2026-02-22 Finding**: The widely-documented "single-byte XOR" approach applies to **Windows WeChat only**. macOS WeChat 4.x .dat files use a **different proprietary format**.

Investigation results:
- All .dat files share a fixed 10-byte header: `07 08 56 32 08 07 00 04 00 00`
- Data diverges from byte 10 (file-specific content)
- The header is per-user (same key `0x45` would produce "BM" BMP signature, but the decoded content is invalid)
- 60,054 image .dat files on disk, none decodable with simple XOR
- Windows tools (wx-image-decoder, wechat_decrypt, imgrecall) do NOT work on macOS .dat files

**Next steps for image decryption**:
1. Investigate if macOS uses AES or another block cipher
2. Check if `media_0.db` contains decryption keys or image metadata
3. Look for macOS-specific WeChat reverse engineering resources
4. Consider using cache thumbnails (JPEG, 160x160) as fallback for image content

#### Message-to-File Mapping

The cache directory contains thumbnails named `{message_id}_timestamp_thumb.jpg`, providing a direct mapping from messages to media. For files and videos, correlation is by:

1. Contact hash (MD5 of username) → directory
2. Timestamp from message DB → YYYY-MM directory
3. Filename patterns within that directory

### Context Management Strategy (Tiered Content)

To avoid flooding AI context windows with media metadata that isn't needed, content is organized into tiers:

| Tier                 | What                                 | Where                      | Loaded When         | Context Cost |
| -------------------- | ------------------------------------ | -------------------------- | ------------------- | ------------ |
| **0 — Inline label** | `[文件: AI计划.pdf (2.3MB)]`         | `Message.content`          | Always              | ~50 chars    |
| **1 — Metadata**     | filename, URL, size, description     | `Message.media[]` in JSONL | On `view --media`   | ~300 bytes   |
| **2 — Summary**      | AI-generated text summary of file    | `MediaRef.summary`         | On explicit request | ~200 words   |
| **3 — Full content** | Actual file bytes (PDF, image, etc.) | Filesystem `media/` dir    | Deep-dive only      | Variable     |

**Implementation status** (2026-02-22):

- Tier 0: Implemented — `_parse_type49_xml()` generates rich inline labels from appmsg XML
- Tier 1: Implemented — `MediaRef` stores filename, URL, size, description; `view --media` displays it
- Tier 2: Not yet implemented — requires AI summarization pipeline
- Tier 3: Partially implemented — `MediaRef.path` resolved for 3,909 files/videos; full image extraction blocked on .dat format research

**Search integration**: Search engine matches keywords against `media[].filename` and `media[].description`, so `search "AI计划"` finds messages containing `英联股份AI计划.pdf`.

### Phase D2: Compressed Text Recovery — COMPLETE ✅

**Implemented 2026-02-22.** 225,182 messages recovered (64% of all messages were compressed).

**Key finding**: Compression is **Zstandard** (NOT zlib). Magic bytes: `28 B5 2F FD`. WCDB_CT=4 indicates zstd.

Implementation in `src/knowledge_harvester/adapters/wechat.py`:
- SQL query returns `hex(message_content)` for rows with `WCDB_CT != 0`
- `_decompress_content()` detects zstd magic and decompresses via `zstandard` library
- 100% success rate — zero decompression failures observed
- **Dependency**: `pip install zstandard`

### Phase D3: Voice Messages (Research Required)

Voice `.dat` files in `msg/attach/*/Rec/` use an unknown encryption format. Needs investigation:

- May be same XOR as images
- May be SILK codec (WeChat's audio format) wrapped in XOR
- SILK → PCM conversion tools exist if we can decrypt

---

## Implementation Priority (Updated)

```
✅ DONE:   Track A  — launchd poller (every 6 hours, deployed 2026-02-22)
✅ DONE:   Track D2 — Compressed text recovery (225K messages, zstd)
✅ DONE:   Track D1 — Media path resolution (3,909 files/videos linked)
TODO:      Track B  — /sync-wechat skill + documentation
TODO:      Track D1 — Image .dat decryption (macOS format differs from Windows)
Later:     Track C  — Evaluate real-time alternatives
Later:     Track D3 — Voice message decryption
```

## Stats (2026-02-22)

```
Messages:      352,190 (537 conversations)
Compressed:    225,182 recovered (was [压缩文本], now full text)
Media refs:     47,228 total
  Resolved:      3,909 (files: 541, videos: 5,936 dir-level, thumbs: 3)
  Unresolved:   43,319 (images: 27,601 .dat, links: 13,582, voice: 1,261)
```

---

**Created**: 2026-02-21
**Updated**: 2026-02-22 — Track A deployed, D2 complete (zstd not zlib), D1 media paths resolved, macOS .dat format differs from Windows XOR
