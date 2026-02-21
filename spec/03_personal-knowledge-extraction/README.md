# Personal Knowledge Extraction

> Extract conversation history from multiple AI platforms and chat apps into a unified local knowledge base, using official APIs where available and browser automation as fallback.

## Quick Links
- [Requirements](./requirements.md)
- [Design](./design.md)
- [Tasks](./tasks.md)
- [Status](./status.md)

## Status: Planning

## Summary

Users accumulate valuable personal knowledge across many AI tools — ChatGPT, Claude, Grok, Doubao (豆包), WeChat, and others. This knowledge is siloed, non-exportable (in most cases), and lost when switching tools. This spec defines a general-purpose extraction system that pulls conversation history from these platforms, normalizes it into a standard format, and integrates it into a local knowledge base accessible from any OpenClaw project.

## Key Decisions

- **Architecture**: Layered — per-platform adapters → normalization → knowledge base integration
- **Extraction strategy**: Official export/API first, Playwright browser automation as fallback, native app automation last resort
- **Runtime**: OpenClaw plugin using built-in Playwright browser automation (no new dependencies)
- **Storage**: Local only — all extracted data stays on-device, never uploaded to third-party services
- **Format**: JSONL with unified schema: `{platform, conversation_id, timestamp, role, content}`

## Scope

**In scope:**
- ChatGPT conversation export (official JSON → JSONL parser)
- Grok web conversation extraction (Playwright)
- Doubao (豆包) web conversation extraction (Playwright)
- WeChat message extraction (evaluate approaches)
- Unified JSONL normalization layer
- Local knowledge base indexing
- OpenClaw skill: `/extract-history <platform>`

**Out of scope (initial cut):**
- Real-time sync / live monitoring
- Sending messages or interacting with platforms
- Cloud storage or cross-device sync
- Enterprise/team conversation extraction
- Platform accounts the user doesn't own

## References

### Internal
- `[ref-browser]` /Users/kweng/AI/openclaw/src/browser/ — Playwright browser automation
- `[ref-chrome-ext]` /Users/kweng/AI/openclaw/assets/chrome-extension/ — Chrome extension for controlling existing tabs
- `[ref-media-understanding]` /Users/kweng/AI/openclaw/src/media-understanding/ — Vision AI for screenshot analysis
- `[ref-memory]` /Users/kweng/AI/openclaw/extensions/memory-core/ — Memory/knowledge base plugin
- `[ref-spec-01]` /Users/kweng/AI/openclaw/spec/01_full-context-ai-assistant/ — consumer of extracted knowledge

### External
- `[ref-chatgpt-export]` ChatGPT Settings → Data controls → Export data
- `[ref-playwright]` https://playwright.dev/docs/api/class-page
- `[ref-wxauto]` https://github.com/cluic/wxauto — WeChat desktop GUI automation (Windows)

---

**Last Updated**: 2026-02-20
