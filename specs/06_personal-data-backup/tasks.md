# Tasks: Personal Data Backup & Storage Strategy

## Phase 1: Git Safety (Immediate)

**Goal**: Prevent accidental exposure of personal data.

- [ ] Task 1.1 - Install pre-commit hook that rejects `*.jsonl` files
- [ ] Task 1.2 - Add `.gitattributes` marking JSONL as binary
- [ ] Task 1.3 - Harden `.gitignore` (add `*.age`, `.wechat_db_key`)
- [ ] Task 1.4 - Remove `debug-screenshot.png` and `debug.png` from tracked grok files
- [ ] Task 1.5 - Verify: run `git ls-files | grep jsonl` returns empty

## Phase 2: Backup Infrastructure

**Goal**: Encrypted backup script with local + iCloud targets.

- [ ] Task 2.1 - Install `age` encryption tool (`brew install age`)
- [ ] Task 2.2 - Store backup passphrase in macOS Keychain
- [ ] Task 2.3 - Write `scripts/backup-knowledge.sh` (tar + age encrypt + copy to iCloud)
- [ ] Task 2.4 - Write `scripts/restore-knowledge.sh` (decrypt + extract + verify)
- [ ] Task 2.5 - Create backup manifest tracking (`~/.openclaw/backups/manifest.json`)
- [ ] Task 2.6 - Test: run backup, delete local JSONL, restore from backup, verify file count + content

## Phase 3: Automation

**Goal**: Daily unattended backups.

- [ ] Task 3.1 - Create launchd plist for daily 3AM backup
- [ ] Task 3.2 - Install plist (`launchctl load`)
- [ ] Task 3.3 - Add backup-on-extraction hook: auto-backup after `knowledge_harvester extract-*` completes
- [ ] Task 3.4 - Add retention cleanup: prune backups older than 30 days
- [ ] Task 3.5 - Test: verify backup ran overnight, check `/tmp/openclaw-backup.log`

## Phase 4: Verification & Documentation

**Goal**: Documented disaster recovery, tested end-to-end.

- [ ] Task 4.1 - Write disaster recovery runbook (fresh machine → full restore)
- [ ] Task 4.2 - Test full restore on a clean directory (simulate new machine)
- [ ] Task 4.3 - Document backup status in a `/backup-status` skill (shows last backup time, file count, size)
- [ ] Task 4.4 - Add backup size monitoring (alert if >5GB, consider switching to incremental)

## Notes

- Phase 1 should be done immediately (prevents data leakage)
- Phase 2-3 can be done together in one session
- Phase 4 is verification — do after a few days of automated backups running
- Current data is 74MB; projected to grow to 500MB+ after Gmail/Docs extraction (Spec 05)
- Time Machine provides an additional safety net but is not a substitute for encrypted off-site backup
- The backup-on-extraction hook (Task 3.3) integrates with Spec 04 (continuous WeChat sync)
