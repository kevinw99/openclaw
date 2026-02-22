# Spec 06: Personal Data Backup & Storage Strategy

> Secure backup and storage strategy for personal knowledge base data that is gitignored and lives only on local machine.

## Quick Links
- [Requirements](./requirements.md)
- [Design](./design.md)
- [Tasks](./tasks.md)

## Status: Planning

## Summary

The personal knowledge base contains 74MB of extracted conversations (966 JSONL files across WeChat, Grok, Doubao) plus future sources (ChatGPT, Gmail, Google Docs). This data is gitignored for privacy — it never goes to GitHub. Currently there is **zero backup**: if the machine dies, all personal data is lost.

This spec defines a backup strategy, storage organization, and disaster recovery plan for all personal data in the knowledge base.

## Problem Statement

1. **No backup** — 966 JSONL files (74MB) exist only on local machine (`~/AI/openclaw/知识库/`)
2. **Growing dataset** — Gmail, Google Docs, ChatGPT not yet extracted; will add significantly more data
3. **No versioning** — JSONL files are gitignored; no way to track changes or recover from bad extraction
4. **No encryption** — Personal conversations stored as plaintext on disk
5. **No multi-machine sync** — Cannot access personal knowledge base from other machines
6. **No separation of concerns** — Personal data lives inside the openclaw repo tree, coupling it to the project

## Current State

| Source | Files | Messages | Size | Status |
|--------|-------|----------|------|--------|
| WeChat | 537 | ~232,000 | 60MB | Extracted (desktop DB) |
| Grok | 275 | 1,940 | 4.3MB | Extracted (browser CDP) |
| Doubao | 154 | ~500 | 10MB | Extracted (browser) |
| ChatGPT | 0 | 0 | 0 | Not started |
| Gmail | 0 | 0 | 0 | Not started |
| Google Docs | 0 | 0 | 0 | Not started |
| **Total** | **966** | **~234K** | **74MB** | |

### Git Strategy (Current)

- **Tracked (public GitHub)**: `index.json` per source (metadata only — titles, IDs, message counts)
- **Gitignored (local-only)**: `*.jsonl` (conversation content), `state.json` (extraction state)
- **Rule**: `.gitignore` line 44: `知识库/conversations/**/*.jsonl`
- **Remote**: `origin` = `kevinw99/openclaw` (public fork); `upstream` = `openclaw/openclaw` (upstream open source)

### Risks

| Risk | Impact | Likelihood |
|------|--------|------------|
| Machine failure / disk corruption | Total data loss | Medium |
| Accidental `git add` of JSONL files | Private conversations pushed to public GitHub | Low but catastrophic |
| Bad extraction overwrites good data | Data corruption | Medium |
| macOS reinstall / migration | Data left behind | Medium |
