# Status: Personal Knowledge Extraction

## Current Status

**Overall**: Complete — All 6 phases implemented (61 unit + 10 e2e tests). WeChat live extraction verified.
**Started**: 2026-02-20
**Last Updated**: 2026-02-22

## Implementation

Source code: `src/knowledge_harvester/`
Task tracking: see `tasks.md` in this directory

## Completed Work

- 2026-02-20: Spec created with requirements, design, and task breakdown
- 2026-02-20: Phase 1 — ChatGPT export parser (ZIP/JSON → JSONL)
- 2026-02-20: Phase 2 — Grok browser scraper (via OpenClaw browser HTTP API)
- 2026-02-20: Phase 3 — Doubao browser scraper (with anti-detection delays)
- 2026-02-20: Phase 4 — WeChat extraction (SQLite DB decryption + unencrypted fallback)
- 2026-02-20: Phase 5 — Cross-platform search engine (keyword search over all JSONL)
- 2026-02-20: Consolidated — removed duplicate `tasks/01_personal-knowledge-extraction/`
- 2026-02-20: Phase 6 — Polish & maintenance:
  - Incremental extraction with `--incremental` flag and state tracking
  - Updated WeChat adapter for 4.x path structure + WCDB key extraction research
  - Adapter version detection (`check_compatibility()`) for Grok, Doubao, WeChat
  - `/extract-history` OpenClaw skill
  - Privacy audit: all operations local-only, no external data leakage
  - End-to-end test framework (10 tests, env-gated with `KH_E2E=1`)
- 2026-02-22: WeChat media metadata parsing + tiered context strategy:
  - `_parse_type49_xml()`: parse XML from type=49 appmsg messages (files, links, mini-programs, references, chat history, transfers)
  - `MediaRef` extended with `description` and `summary` fields, sparse serialization
  - Tier 0 inline labels: `[文件: name.pdf (2.3MB)]`, `[链接: title]`, `[小程序: name]`, `[引用: ...]`
  - MediaRef created for image/audio/video types (3/34/43) for structural tracking
  - Search engine now matches against media filename and description fields
  - `view --media` flag for Tier 1 metadata display (URL, description, file size)
  - `/search-knowledge` skill updated with tiered retrieval instructions
  - 16 new tests (13 wechat XML parsing + 3 model serialization)

## Architecture Notes

- **Browser adapters** (Grok, Doubao) use OpenClaw's built-in browser HTTP API (port 18791) + Chrome extension relay for session reuse. No separate Playwright Python dependency needed.
- **WeChat** on macOS: LLDB-based key extraction (`scripts/extract_wechat_key.py`) captures the PBKDF2 master password from WeChat process memory. Each DB uses SQLCipher 4 with per-file salt (first 16 bytes) + 256K rounds PBKDF2-HMAC-SHA512. Master key stored at `~/.wechat_db_key`. WeChat 4.x path structure: `xwechat_files/{wxid}_{hash}/db_storage/message/`.
- **Search** is keyword-based full-text search over JSONL files. No vector DB yet.
- **Incremental extraction**: `state.json` per platform tracks known conversation IDs and last message times. Use `--incremental` / `-i` on any extraction command.
- **Version detection**: `check_compatibility()` on browser adapters checks DOM structure before extraction.

## Remaining Work (Future)

- [x] Phase 1: ChatGPT export parser
- [x] Phase 2: Grok web extraction
- [x] Phase 3: Doubao web extraction
- [x] Phase 4: WeChat extraction
- [x] Phase 5: Knowledge base search
- [x] Phase 6: Polish & maintenance
- [ ] Future: Live testing with real Grok/Doubao accounts
- [x] Live: WeChat DB decryption verified — 431 conversations, 41,814 messages extracted
- [ ] Future: Vector DB integration for semantic search
- [ ] Future: Incremental sync automation (cron/launchd)
- [ ] Future: Cross-AI-tool accessibility (MCP server / RAG)

## Verification

```bash
# Unit tests (45 passed, 10 e2e skipped)
cd src && python3 -m pytest knowledge_harvester/tests/ -v

# E2E tests (requires real data)
KH_E2E=1 KH_CHATGPT_EXPORT=~/export.zip python3 -m pytest knowledge_harvester/tests/test_e2e.py -v

# CLI
python3 -m knowledge_harvester import-chatgpt <export.zip>
python3 -m knowledge_harvester import-chatgpt <export.zip> -i  # incremental
python3 -m knowledge_harvester scrape-grok
python3 -m knowledge_harvester scrape-doubao
python3 -m knowledge_harvester extract-wechat --key <key>
python3 -m knowledge_harvester search "query"
python3 -m knowledge_harvester stats
```
