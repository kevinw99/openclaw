# Requirements: Personal Data Backup & Storage Strategy

## Overview

All personal conversation data (WeChat, Grok, Doubao, future ChatGPT/Gmail/Docs) is gitignored for privacy and exists only on the local machine. This spec establishes a backup strategy, encryption, versioning, and disaster recovery plan.

## Objectives

1. **Zero data loss** — Personal knowledge base must survive machine failure, disk corruption, or OS reinstall
2. **Privacy by default** — Personal data never reaches public repos; backups are encrypted at rest
3. **Incremental backup** — Only new/changed data is backed up; not full copies each time
4. **Verifiable recovery** — Can restore the full knowledge base on a fresh machine from backup alone
5. **Multi-machine access** (future) — Optionally sync personal knowledge base across machines

## Scope

### In Scope

- Backup of all `知识库/conversations/**/*.jsonl` files
- Backup of extraction state files (`state.json`, index files)
- Backup of WeChat DB decryption key (`~/.wechat_db_key`)
- Encryption of backups at rest
- Automated backup schedule
- Disaster recovery procedure (documented, tested)
- Protection against accidental push of private data to public repos

### Out of Scope

- Backing up the WeChat desktop database itself (WeChat manages this; we extract from it)
- Backing up the openclaw source code (already on GitHub)
- Real-time sync (addressed by Spec 04)
- Cloud-hosted knowledge base service (Spec 05 territory)

## Success Criteria

- [ ] Automated backup runs on schedule without user intervention
- [ ] Backup is encrypted; cannot be read without passphrase
- [ ] Full restore tested: fresh machine → working knowledge base with all conversations
- [ ] Accidental `git add` protection: pre-commit hook prevents JSONL files from being committed
- [ ] Backup size is manageable (incremental, not full copies)
- [ ] Backup works for current 74MB and scales to projected 500MB+ (after Gmail/Docs)

## Constraints & Assumptions

- User is on macOS (Apple Silicon)
- User has iCloud Drive available (200GB+ plan)
- User has access to at least one cloud storage (iCloud, Google Drive, or S3)
- Backup passphrase must be memorizable or stored in system keychain
- No paid backup services required (prefer built-in or open-source tools)
- Must not require running a server or daemon beyond macOS launchd

## Dependencies

- Spec 03: Knowledge harvester (produces the JSONL files to be backed up)
- Spec 04: Continuous sync (produces ongoing new data that must be backed up)
- Spec 05: PKB (will add more data sources — ChatGPT, Gmail, Docs)
- macOS keychain (for passphrase storage)
- `gpg` or `age` (for encryption)

## Questions & Clarifications

- **Q1**: Should backup include embeddings/vector DB (Spec 05 ChromaDB), or just raw JSONL? Embeddings can be regenerated from JSONL.
  - **Proposed**: Only back up JSONL + index files. Embeddings are regeneratable.
- **Q2**: Is iCloud the preferred cloud storage, or should we support multiple targets?
  - **Proposed**: iCloud as primary (already available), with option to add others.
- **Q3**: Should we use a separate private Git repo for personal data (encrypted)?
  - **Proposed**: Evaluate as an option — provides versioning + remote backup in one.
- **Q4**: How often should backups run?
  - **Proposed**: Daily for automated backup; on-demand after each extraction run.
