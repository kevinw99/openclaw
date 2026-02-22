# Design: Personal Data Backup & Storage Strategy

## Approach

Three-layer backup strategy: **local versioning** + **encrypted cloud backup** + **git safety net**.

## Architecture

```
知识库/conversations/          ← Source of truth (local)
  wechat/*.jsonl (537 files, 60MB)
  grok/*.jsonl (275 files, 4.3MB)
  doubao/*.jsonl (154 files, 10MB)
  chatgpt/*.jsonl (future)
  gmail/*.jsonl (future)
  gdocs/*.jsonl (future)
          │
          ├──→ Layer 1: Local Snapshots
          │    ~/.openclaw/backups/
          │      YYYY-MM-DD_HH-MM.tar.age  (encrypted, incremental)
          │      latest → symlink
          │      manifest.json (what's in each backup)
          │
          ├──→ Layer 2: Cloud Sync (Encrypted)
          │    ~/Library/Mobile Documents/com~apple~CloudDocs/
          │      openclaw-backups/
          │        (same .tar.age files, auto-synced by iCloud)
          │
          └──→ Layer 3: Git Safety
               .gitignore (blocks *.jsonl)
               pre-commit hook (rejects JSONL additions)
               .gitattributes (marks JSONL as binary, prevents diff)
```

## Layer 1: Local Encrypted Snapshots

### Tool: `age` (modern encryption)

Why `age` over `gpg`:
- Simpler (no key management ceremony)
- Passphrase-based encryption (`age -p`)
- Fast (ChaCha20-Poly1305)
- Single binary, easy to install (`brew install age`)

### Backup Script: `scripts/backup-knowledge.sh`

```bash
#!/bin/bash
# Backup personal knowledge base data (encrypted)

KNOWLEDGE_DIR="$HOME/AI/openclaw/知识库"
BACKUP_DIR="$HOME/.openclaw/backups"
CLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/openclaw-backups"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M)
ARCHIVE="pkb-${TIMESTAMP}.tar.age"

mkdir -p "$BACKUP_DIR" "$CLOUD_DIR"

# Create tar of all JSONL + state + index files
tar cf - -C "$KNOWLEDGE_DIR" \
  --include='*.jsonl' \
  --include='*/index.json' \
  --include='*/state.json' \
  . | age -p -o "$BACKUP_DIR/$ARCHIVE"

# Copy to iCloud
cp "$BACKUP_DIR/$ARCHIVE" "$CLOUD_DIR/"

# Update latest symlink
ln -sf "$ARCHIVE" "$BACKUP_DIR/latest"

# Update manifest
python3 -c "
import json, os, glob
manifest_path = '$BACKUP_DIR/manifest.json'
try:
    manifest = json.load(open(manifest_path))
except:
    manifest = []
manifest.append({
    'file': '$ARCHIVE',
    'timestamp': '$TIMESTAMP',
    'size_bytes': os.path.getsize('$BACKUP_DIR/$ARCHIVE'),
    'source_files': len(glob.glob('$KNOWLEDGE_DIR/**/*.jsonl', recursive=True)),
})
# Keep last 30 entries
manifest = manifest[-30:]
json.dump(manifest, open(manifest_path, 'w'), indent=2)
"

echo "Backup complete: $ARCHIVE"
echo "  Local: $BACKUP_DIR/$ARCHIVE"
echo "  Cloud: $CLOUD_DIR/$ARCHIVE"
```

### Restore Script: `scripts/restore-knowledge.sh`

```bash
#!/bin/bash
# Restore personal knowledge base from backup

KNOWLEDGE_DIR="$HOME/AI/openclaw/知识库"
BACKUP_DIR="$HOME/.openclaw/backups"
CLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/openclaw-backups"

# Find latest backup (local first, then cloud)
LATEST="${1:-$(readlink "$BACKUP_DIR/latest" 2>/dev/null)}"
BACKUP_FILE="$BACKUP_DIR/$LATEST"
if [ ! -f "$BACKUP_FILE" ]; then
    BACKUP_FILE="$CLOUD_DIR/$LATEST"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "No backup found. Available:"
    ls -la "$BACKUP_DIR"/*.age "$CLOUD_DIR"/*.age 2>/dev/null
    exit 1
fi

echo "Restoring from: $BACKUP_FILE"
echo "Target: $KNOWLEDGE_DIR"
read -p "Continue? [y/N] " confirm
[ "$confirm" = "y" ] || exit 0

# Decrypt and extract
age -d "$BACKUP_FILE" | tar xf - -C "$KNOWLEDGE_DIR"

echo "Restore complete. File count:"
find "$KNOWLEDGE_DIR" -name "*.jsonl" | wc -l
```

### Schedule: macOS launchd

```xml
<!-- ~/Library/LaunchAgents/com.openclaw.backup-knowledge.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.backup-knowledge</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/kweng/AI/openclaw/scripts/backup-knowledge.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/openclaw-backup.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/openclaw-backup.log</string>
</dict>
</plist>
```

Runs daily at 3:00 AM.

## Layer 2: Cloud Sync via iCloud

- Backup files land in `~/Library/Mobile Documents/com~apple~CloudDocs/openclaw-backups/`
- iCloud auto-syncs to cloud — no extra tools needed
- Files are `.age` encrypted — unreadable without passphrase even if iCloud is compromised
- **Retention**: Keep last 30 daily backups (~30 x 74MB = ~2.2GB, well within iCloud limits)
- **Cleanup**: Backup script prunes backups older than 30 days

### Alternative Cloud Targets

| Target | Pros | Cons | When to Use |
|--------|------|------|-------------|
| **iCloud Drive** | Already available, zero setup | Apple ecosystem only | Primary (recommended) |
| **Google Drive** | 15GB free, cross-platform | Requires rclone/gdrive CLI | If iCloud unavailable |
| **Private GitHub repo** | Versioning built-in, free 1GB | Slow for large files, LFS needed | For version-controlled backup |
| **S3 / Backblaze B2** | Cheap, durable, scriptable | Requires AWS account, more setup | For enterprise/team scenario |
| **Syncthing** | P2P, no cloud, encrypted | Requires second machine online | For multi-machine sync |

## Layer 3: Git Safety Net

### Pre-commit Hook

Prevents accidentally staging JSONL files:

```bash
#!/bin/bash
# .git/hooks/pre-commit — prevent private data from being committed

# Check for JSONL files in staged changes
JSONL_FILES=$(git diff --cached --name-only | grep '\.jsonl$')
if [ -n "$JSONL_FILES" ]; then
    echo "ERROR: JSONL files detected in commit!"
    echo "These contain personal conversation data and must not be pushed."
    echo ""
    echo "Files:"
    echo "$JSONL_FILES"
    echo ""
    echo "To unstage: git reset HEAD <file>"
    exit 1
fi
```

### .gitattributes

```
# Prevent accidental diff of binary/private data
知识库/conversations/**/*.jsonl binary
```

### Additional .gitignore Hardening

```gitignore
# Personal data - extracted conversations (privacy)
知识库/conversations/**/*.jsonl
知识库/conversations/**/state.json

# Backup files (should never be in repo)
*.age
*.tar.age

# Decryption keys
.wechat_db_key
```

## Passphrase Management

### Option A: macOS Keychain (Recommended)

```bash
# Store passphrase
security add-generic-password -a "openclaw" -s "pkb-backup" -w "THE_PASSPHRASE"

# Retrieve in scripts
PASSPHRASE=$(security find-generic-password -a "openclaw" -s "pkb-backup" -w)
echo "$PASSPHRASE" | age -p -o backup.age < data.tar
```

### Option B: Environment Variable

```bash
export OPENCLAW_BACKUP_PASSPHRASE="..."
# Set in ~/.zshrc or ~/.bash_profile
```

### Option C: age Identity File

```bash
age-keygen -o ~/.openclaw/backup.key
# Encrypt: age -r $(cat ~/.openclaw/backup.key.pub) -o backup.age < data.tar
# Decrypt: age -d -i ~/.openclaw/backup.key backup.age > data.tar
```

**Recommendation**: Option A (Keychain) for single-machine, Option C (identity file) if syncing across machines.

## Key Decisions

- **`age` over `gpg`**: Simpler, no key management ceremony, modern cipher, single binary
- **iCloud over dedicated backup service**: Zero setup, already paid for, sufficient for ~2GB of encrypted backups
- **Tar archive over rsync**: Simpler to encrypt as a single unit; incremental handled by daily rotation
- **30-day retention**: Balances storage (~2.2GB) with recovery window
- **Pre-commit hook over git-secrets**: Simpler, no external dependency, specific to our use case
- **JSONL-only backup**: Embeddings (ChromaDB) are regeneratable from JSONL; no need to back up derived data

## Alternative Approaches

### Alternative 1: Private Git Repo for Personal Data
- **Pros**: Built-in versioning, diff history, easy to clone on new machine
- **Cons**: GitHub LFS needed for large files, 1GB free limit, not truly encrypted at rest
- **Verdict**: Good for versioning, but doesn't solve encryption. Could complement Layer 2.

### Alternative 2: git-crypt for In-Repo Encryption
- **Pros**: Personal data stays in same repo, encrypted transparently
- **Cons**: Requires GPG, complex key management, all collaborators need keys, can't use with public upstream
- **Verdict**: Not suitable — openclaw has a public upstream and multiple remotes.

### Alternative 3: Time Machine Only
- **Pros**: Zero setup, already running
- **Cons**: Only covers local backups, no off-site, no encryption, no selective restore
- **Verdict**: Good as a last resort, but not sufficient alone.

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Passphrase forgotten | Store in macOS Keychain + write down in physical safe location |
| iCloud sync fails silently | Backup script checks file exists in cloud dir after copy |
| Backup corrupted | Restore test as part of initial setup; periodic verification |
| Machine stolen with local backups | Local backups are encrypted; disk also has FileVault |
| Accidental JSONL commit to public repo | Pre-commit hook + .gitignore + .gitattributes triple protection |
| Backup grows too large (future Gmail/Docs) | Monitor size in manifest; switch to incremental (rsync) if >5GB |
