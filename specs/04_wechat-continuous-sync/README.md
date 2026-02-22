# Spec 04: WeChat Continuous Message Sync

> Continuously capture WeChat messages (historical + ongoing) into a personal knowledge base, without relying on dead third-party puppet services like PadLocal.

## Quick Links

- [Design](./design.md)

## Status: In Progress

## Background

Spec 02 built a WeChat channel extension using Wechaty + PadLocal. However, **PadLocal is dead** (confirmed 2026-02): npm unpublished 3+ years, website down, WeChat protocol changes broke login, maintainer unresponsive.

Spec 03 extracted conversations from the WeChat **desktop** database. As of 2026-02-22: 537 conversations, 352,190 messages (225K compressed texts recovered via zstd). However:

- Desktop only has messages received while logged in on desktop
- Phone-only messages are missing (WeChat keeps per-device history)
- The extraction is a static one-time snapshot

**This spec solves**: How to get **all** WeChat messages (historical + new) into the personal knowledge base, continuously.

## Problem Statement

1. **Incomplete history** — Desktop WeChat DB is missing phone-only messages
2. **Static snapshot** — No mechanism for ongoing capture of new messages
3. **Dead dependency** — PadLocal/Wechaty real-time approach is non-viable
4. **High risk** — All reverse-engineered WeChat automation carries ban risk (>80% for hooks, moderate for pad protocol)

## Approach: Two-Track Strategy

### Track A: Local DB Polling (Low Risk, Desktop-scope)

Poll the local WeChat desktop database periodically for new messages. No reverse engineering of WeChat protocol — just reading the local SQLite/WCDB files that WeChat already creates.

- **Risk**: Minimal — reading local files, no network protocol manipulation
- **Coverage**: Desktop messages only (but combined with manual phone sync, gets everything)
- **Automation**: Fully automatable via launchd/cron

### Track B: Manual Phone Sync + Extraction (Zero Risk, Full Coverage)

Use WeChat's built-in "Transfer Chat History" feature to sync phone messages to desktop, then extract via Track A.

- **Risk**: Zero — using official WeChat feature
- **Coverage**: All messages (phone + desktop)
- **Automation**: Manual trigger required (monthly/weekly)

### Track C: Real-Time Bot (High Risk, Evaluate Only)

Evaluate current alternatives to PadLocal for real-time message reception. **Do not build until viability is confirmed.**

| Alternative            | Status (2026-02)        | Approach           | Risk                                                  |
| ---------------------- | ----------------------- | ------------------ | ----------------------------------------------------- |
| WeChatFerry (org fork) | Active (1.9k stars)     | Windows PC hook    | High — requires Windows, hook detection risk          |
| AstrBot + WeChatPadPro | Very active (17k stars) | Pad protocol (new) | Medium — paid, closed-source, could die like PadLocal |
| WeCom API              | Official                | Enterprise API     | Low — but cannot access personal WeChat messages      |

**Recommendation**: Do NOT invest in Track C until Track A+B are working. If Track C is pursued later, prefer WeChatFerry (open source) with a disposable test account first.

## Architecture

```
Phone WeChat ──────────────────────────────────┐
  │                                             │
  │ (Manual: Settings → Transfer Chat History)  │
  │ (Monthly/weekly)                            │
  │                                             │
  ▼                                             │
Desktop WeChat                                  │
  │                                             │
  │ Local encrypted SQLite DB                   │
  │ ~/Library/Containers/com.tencent.xinWeChat/ │
  │                                             │
  ▼                                             │
┌──────────────────────────────────────┐        │
│  DB Poller (Track A)                 │        │
│                                      │        │
│  - Watch for DB changes (fswatch)    │        │
│  - Decrypt via existing key          │        │
│  - Incremental extraction            │        │
│  - Deduplicate against known msgs    │        │
│  - Emit normalized JSONL             │        │
│                                      │        │
│  Schedule: Every 6 hours (launchd)   │        │
│  Or: on-demand after phone sync      │        │
└──────────┬───────────────────────────┘        │
           │                                    │
           ▼                                    │
┌──────────────────────────────────────┐        │
│  Knowledge Base                      │        │
│  ~/.openclaw/knowledge/              │        │
│                                      │        │
│  extractions/wechat/                 │        │
│    normalized/*.jsonl                │        │
│    state.json (last sync timestamp)  │        │
│                                      │        │
│  Searchable via:                     │        │
│  - knowledge_harvester search        │        │
│  - /search-knowledge skill           │        │
│  - Any AI tool with file access      │        │
└──────────────────────────────────────┘
```

## Phases

### Phase 1: Automated DB Polling

- Wrap existing `knowledge_harvester extract-wechat` into a scheduled poller
- Add filesystem watcher (fswatch) to detect DB changes
- Create macOS launchd plist for periodic extraction
- Incremental mode: only extract messages newer than last sync

### Phase 2: Phone Sync Workflow

- Document the manual phone sync procedure (step-by-step with screenshots)
- Add a `/sync-wechat` skill that:
  1. Prompts user to do phone sync
  2. Waits for DB change detection
  3. Runs incremental extraction
  4. Reports new message count

### Phase 3: Evaluate Real-Time Alternatives (Optional)

- Test WeChatFerry with a secondary/test account
- Evaluate AstrBot + WeChatPadPro
- If viable, build adapter following Spec 02's extension pattern
- **Gate**: Only proceed if ban risk is acceptable to user

## Dependencies

- Spec 03 `knowledge_harvester` — WeChat adapter (already complete)
- `scripts/extract_wechat_key.py` — Master password extraction (already complete)
- `~/.wechat_db_key` — Extracted master password (one-time setup)

## Non-Goals

- Replacing Spec 02 entirely — Spec 02's extension code can be reused if Track C becomes viable
- Automated phone message sync — WeChat provides no API for this
- WeChat Official Account / WeCom integration — different products, different specs

## Risk Register

| Risk                                                 | Severity | Mitigation                                                 |
| ---------------------------------------------------- | -------- | ---------------------------------------------------------- |
| WeChat desktop DB format changes                     | Medium   | Version detection already in adapter; add format migration |
| Master password extraction breaks (macOS/SIP update) | Medium   | Document alternative methods; cache key securely           |
| Track C alternative dies (like PadLocal)             | High     | Track A+B are self-sufficient; Track C is optional         |
| WeChat detects automated DB reads                    | Low      | Read-only access to local files; no protocol manipulation  |

## References

### Internal

- [Spec 02: WeChat Channel](../02_wechat-channel/) — Blocked on PadLocal; extension code reusable
- [Spec 03: Personal Knowledge Extraction](../03_personal-knowledge-extraction/) — Knowledge harvester with WeChat adapter
- `src/knowledge_harvester/adapters/wechat.py` — WeChat DB extraction implementation
- `scripts/extract_wechat_key.py` — LLDB-based master password extraction

### External

- [WeChatFerry (org fork)](https://github.com/wechatferry/wechatferry) — Active Windows hook approach
- [AstrBot](https://github.com/AstrBotDevs/AstrBot) — Multi-platform bot framework with WeChatPadPro support
- [PadLocal Issues](https://github.com/wechaty/puppet-padlocal/issues) — Evidence of PadLocal's demise

---

**Created**: 2026-02-21
**Last Updated**: 2026-02-21
