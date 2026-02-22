# Design: Personal Knowledge Extraction

## Approach

Build an OpenClaw plugin with a layered architecture: platform-specific adapters handle extraction, a normalization layer unifies the data, and an integration layer makes it searchable.

## Architecture

```
/extract-history <platform> [--since <date>] [--conversation <id>]
         │
         ▼
┌─────────────────────────────────────────────┐
│              Extraction Layer                │
│                                             │
│  ┌───────────┐ ┌─────────┐ ┌────────────┐  │
│  │  ChatGPT  │ │  Grok   │ │  Doubao    │  │
│  │  (export  │ │  (PW)   │ │  (PW+ext)  │  │
│  │   JSON)   │ │         │ │            │  │
│  └─────┬─────┘ └────┬────┘ └─────┬──────┘  │
│        │            │            │          │
│        ▼            ▼            ▼          │
│  ┌─────────────────────────────────────┐    │
│  │       Normalization Layer           │    │
│  │  → Unified JSONL schema             │    │
│  │  → Deduplication                    │    │
│  │  → Timestamp normalization          │    │
│  └──────────────┬──────────────────────┘    │
│                 │                            │
└─────────────────┼────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────┐
│           Integration Layer                  │
│  → Local JSONL storage                      │
│  → Full-text search index                   │
│  → OpenClaw memory plugin integration       │
│  → Cross-project access                     │
└─────────────────────────────────────────────┘
```

## Unified Schema

```jsonl
{
  "platform": "chatgpt",
  "conversation_id": "abc123",
  "conversation_title": "Python debugging help",
  "message_id": "msg_001",
  "timestamp": "2026-01-15T14:30:00Z",
  "role": "user",
  "content": "How do I fix this error...",
  "content_type": "text",
  "attachments": []
}
```

Fields:

- `platform`: chatgpt | grok | doubao | wechat | claude
- `conversation_id`: Platform-specific conversation identifier
- `conversation_title`: Human-readable title (if available)
- `message_id`: Unique message ID within conversation
- `timestamp`: ISO 8601 UTC
- `role`: user | assistant | system
- `content`: Text content (markdown when available)
- `content_type`: text | image | audio | file
- `attachments`: Array of `{type, filename, size, local_path}` for media

## Per-Platform Adapter Design

### ChatGPT Adapter (File-based)

```
Input:  conversations.json from official export ZIP
Output: normalized JSONL

Steps:
1. User triggers export in ChatGPT Settings
2. User provides path to downloaded ZIP
3. Adapter extracts conversations.json
4. Maps ChatGPT schema → unified schema
5. Handles: text, code blocks, images (DALL-E URLs), plugins
```

No browser automation needed. Simplest adapter.

### Grok Adapter (Playwright)

```
Steps:
1. Open grok.com using Chrome extension (reuse login session)
2. Snapshot sidebar → extract conversation list
3. For each conversation:
   a. Click to open
   b. Scroll to load full history
   c. Extract messages from DOM
   d. Normalize timestamps, roles, content
4. Output JSONL
```

Key challenges:

- Infinite scroll handling (scroll up to load older messages)
- Dynamic rendering (React, content loads async)
- Rate limiting between conversations

### Doubao Adapter (Playwright)

Similar to Grok but with additional challenges:

- Bytedance anti-bot detection (fingerprinting, behavioral analysis)
- Use Chrome extension profile (existing cookies) to avoid login flow
- Slower extraction pace needed
- May need screenshot + OCR fallback if DOM is obfuscated

### WeChat Adapter (TBD)

Three possible approaches to evaluate:

**Option A: wxauto (GUI automation)**

- Pros: Known working, community maintained
- Cons: Windows only, very slow, fragile

**Option B: Local DB decryption**

- Pros: Fast, offline, complete history
- Cons: Requires key extraction from memory, version-dependent

**Option C: Web WeChat + Playwright**

- Pros: Cross-platform, consistent with other adapters
- Cons: Web WeChat has limited history, may be deprecated

Decision deferred to Phase 4.

## Key Decisions

- **Playwright over Puppeteer**: OpenClaw already uses Playwright Core, no reason to add another browser automation library
- **Chrome extension for auth**: Reuse user's existing browser sessions instead of handling login flows
- **JSONL over SQLite**: Simpler, git-friendly, consistent with session_history
- **Batch over real-time**: On-demand extraction is simpler and avoids persistent connection complexity
- **Local-first**: No cloud component, all data on local filesystem

## Storage Layout

```
~/.openclaw/knowledge/
├── extractions/
│   ├── chatgpt/
│   │   ├── raw/                    # Original export files
│   │   └── normalized/             # JSONL output
│   │       └── conversations.jsonl
│   ├── grok/
│   │   └── normalized/
│   │       └── conversations.jsonl
│   └── doubao/
│       └── normalized/
│           └── conversations.jsonl
├── index/                          # Search index
│   └── full-text.idx
└── metadata.json                   # Last extraction timestamps per platform
```

## Alternative Approaches

- **Browser extension only (no Playwright)**: Could inject content scripts into platform pages. Pros: no separate browser instance. Cons: harder to orchestrate, requires per-platform extension code, Chrome-only.
- **API-first**: Wait for platforms to offer export APIs. Pros: clean, supported. Cons: most platforms never will.
- **Screen recording + OCR**: Record scrolling through conversations, use vision AI to extract text. Pros: works everywhere. Cons: extremely slow, error-prone, expensive (vision API calls).

## Risk Mitigation

- **UI changes break selectors**: Use accessibility snapshots (role-based refs) instead of CSS selectors where possible. Add version detection and adapter versioning.
- **Anti-bot detection**: Use existing Chrome profile (real browser fingerprint), add human-like delays, limit extraction rate.
- **Data corruption**: Write-ahead logging, checkpoint after each conversation, resume from last checkpoint on failure.
- **Privacy leak**: Never transmit extracted data; all processing local. Encryption at rest optional but recommended.
