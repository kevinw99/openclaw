# Tasks: Personal Knowledge Extraction

## Phase 1: ChatGPT Export Parser ✅
- [x] 1.1 - Build ChatGPT `conversations.json` parser (map to unified schema)
- [x] 1.2 - Handle edge cases: code blocks, DALL-E images, plugin outputs, system messages
- [x] 1.3 - Write JSONL output with deduplication
- [x] 1.4 - CLI: `python3 -m knowledge_harvester import-chatgpt <path>`
- [x] 1.5 - Test with fixture data (8 tests)

## Phase 2: Grok Web Extraction ✅
- [x] 2.1 - Build OpenClaw browser HTTP client (`browser_client.py`)
- [x] 2.2 - Build Grok adapter: list conversations from sidebar via JS evaluate
- [x] 2.3 - Build Grok adapter: extract messages with role detection, scroll handling
- [x] 2.4 - Human-like delays and rate limiting
- [x] 2.5 - CLI: `python3 -m knowledge_harvester scrape-grok`
- [ ] 2.6 - Test with real account (requires OpenClaw gateway + Chrome extension)

## Phase 3: Doubao Web Extraction ✅
- [x] 3.1 - Build Doubao adapter using browser client (same pattern as Grok)
- [x] 3.2 - Extended delays for Bytedance anti-bot measures
- [x] 3.3 - Chinese UI element detection via multiple selector strategies
- [x] 3.4 - CLI: `python3 -m knowledge_harvester scrape-doubao`
- [ ] 3.5 - Test with real account (requires OpenClaw gateway + Chrome extension)

## Phase 4: WeChat Extraction ✅
- [x] 4.1 - Research macOS WeChat DB location and encryption
- [x] 4.2 - Build adapter: SQLCipher decryption with user-provided key
- [x] 4.3 - Build adapter: unencrypted DB fallback (old format + new MSG table)
- [x] 4.4 - Handle message types: text, image, voice, video, system
- [x] 4.5 - CLI: `python3 -m knowledge_harvester extract-wechat --key <key>`
- [x] 4.6 - Tests with mock SQLite DB (8 tests)
- [ ] 4.7 - Test with real WeChat DB
- [ ] 4.8 - macOS Accessibility API fallback (deferred — needs pyobjc)

## Phase 5: Knowledge Base Integration ✅
- [x] 5.1 - Build full-text search engine over JSONL (`search.py`)
- [x] 5.2 - Multi-keyword search with scoring
- [x] 5.3 - Platform filtering, role filtering, result limiting
- [x] 5.4 - Stats aggregation across all platforms
- [x] 5.5 - CLI: `python3 -m knowledge_harvester search <query>`
- [x] 5.6 - Tests (8 search tests)
- [ ] 5.7 - Vector DB / semantic search integration (future)

## Phase 6: Polish & Maintenance
- [x] 6.1 - Incremental extraction (only new conversations since last run)
- [x] 6.2 - Adapter version detection (warn when UI changes detected)
- [x] 6.3 - `/extract-history <platform>` OpenClaw skill
- [x] 6.4 - Privacy audit: verify no data leaves local machine
- [x] 6.5 - End-to-end testing framework (10 e2e tests, env-gated)

## Notes
- Phases 1-5 core implementation complete + Phase 6.1 incremental extraction — 45 unit tests
- Browser adapters (Grok, Doubao) need live testing with real accounts
- WeChat macOS key extraction is blocked by SIP — user must provide key from elsewhere
- WeChat 4.x path support added: `xwechat_files/{wxid}_{hash}/db_storage/message/`
- Search is keyword-based; semantic/vector search is a future enhancement
- All CLI commands support `--incremental` / `-i` flag for incremental extraction
