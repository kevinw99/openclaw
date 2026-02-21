# Requirements: Personal Knowledge Extraction

## Overview

Users have valuable personal data scattered across multiple AI platforms with no unified way to access it. Each platform silos conversation history behind proprietary formats (or no export at all). We need a system that extracts, normalizes, and indexes this data locally.

## Objectives

- Extract conversation history from ChatGPT, Grok, Doubao, and WeChat
- Normalize all data into a single schema regardless of source platform
- Store everything locally with privacy-first design
- Make extracted knowledge searchable and accessible from any OpenClaw project
- Provide a simple user interface: `/extract-history <platform>`

## Platform Analysis

### ChatGPT
- **Official export**: Yes — Settings → Data controls → Export. Delivers ZIP with `conversations.json`
- **API**: Conversations API exists but doesn't expose full history
- **Strategy**: Parse official export JSON (Phase 1, easiest)

### Claude
- **Local data**: Session JSONL already at `~/.claude/projects/`
- **Strategy**: Already handled by session_history — no new work needed

### Grok (x.ai)
- **Official export**: No
- **API**: Limited, no conversation history endpoint
- **Web UI**: `grok.com` — standard React app, conversations in sidebar
- **Strategy**: Playwright browser automation

### Doubao (豆包)
- **Official export**: No
- **API**: No public API for conversation history
- **Web UI**: `doubao.com` — Bytedance product, heavy anti-bot measures
- **Strategy**: Playwright with Chrome extension (use existing login session)
- **Risk**: Aggressive anti-automation detection

### WeChat
- **Official export**: No
- **API**: No personal account API
- **Desktop client**: Win32 native app (not browser-based)
- **Local DB**: SQLite with encryption (key derivable from memory)
- **Strategy options**:
  1. wxauto — GUI automation (Windows only, slow, fragile)
  2. Local DB decryption — faster but requires reverse-engineering effort
  3. Skip in initial phases — hardest platform
- **Risk**: ToS violation concerns, platform-specific

## Success Criteria

- [ ] ChatGPT: Full conversation history extracted from official export ZIP
- [ ] Grok: All conversations extracted via browser automation
- [ ] Doubao: All conversations extracted via browser automation
- [ ] WeChat: At least one extraction method working
- [ ] All platforms produce identical JSONL schema
- [ ] Extracted data searchable via openclaw memory/knowledge base
- [ ] Zero data leaves the local machine

## Constraints & Assumptions

- macOS primary platform (user's environment)
- OpenClaw with Playwright already available
- User has active accounts and login sessions on target platforms
- Extraction is batch (on-demand), not real-time
- Web UIs will change — adapters need maintenance

## Dependencies

- OpenClaw browser automation (Playwright Core)
- Chrome extension for session reuse
- Media understanding for visual fallback (screenshot → OCR)
- Memory/knowledge base plugin for storage

## Questions & Clarifications

- What's the preferred knowledge base format? Vector DB (LanceDB) vs flat JSONL index?
- Should extracted conversations be tagged/categorized automatically?
- How to handle multimedia (images, voice messages, files) in conversations?
- What's the retention policy — keep everything or allow selective extraction?
