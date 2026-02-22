# Design: Personal Knowledge Base & AI Agent Platform

## Approach

Leverage OpenClaw's existing infrastructure (knowledge harvester, WeChat extension, memory system, agent runner) and build three new layers on top:

1. **Complete extraction** — run existing adapters + build Gmail/Docs adapters
2. **Unified index** — ChromaDB embeddings + contact graph + PersonalKB query API
3. **Agent controller** — orchestrates PKB + LLM + WeChat extension for autonomous messaging

## Existing Infrastructure Audit

### Knowledge Harvester (Python — `src/knowledge_harvester/`)

Already built and operational. All adapters output to unified data models:

```python
# models.py — Unified data classes
@dataclass
class Message:
    role: str              # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: str = ""    # ISO 8601
    message_id: str = ""
    content_type: str = "text"  # "text" | "image" | "audio" | "file" | "mixed"
    media: List[MediaRef] = []

@dataclass
class Conversation:
    id: str
    platform: str          # "chatgpt" | "grok" | "doubao" | "wechat"
    title: str
    participants: List[str] = []
    messages: List[Message] = []
    metadata: Dict[str, Any] = {}
```

**Storage layer** (`storage.py`):
- One JSONL file per conversation (one message per line)
- `index.json` per platform (conversation metadata: title, participants, message count, timestamps)
- `state.json` per platform (incremental extraction state — tracks message counts + last message time)

**Search engine** (`search.py`):
- Keyword-based full-text search (AND logic)
- **Gap**: No semantic/vector search — purely keyword matching

**CLI** (`main.py`):
```bash
python3 -m knowledge_harvester import-chatgpt <zip_or_json_path>
python3 -m knowledge_harvester scrape-grok [--browser-url ...] [--incremental]
python3 -m knowledge_harvester scrape-doubao [--browser-url ...] [--incremental]
python3 -m knowledge_harvester extract-wechat [--key <64-char-hex>] [--key-file <path>]
python3 -m knowledge_harvester search <query> [--platform <plat>] [--limit 20]
python3 -m knowledge_harvester list
python3 -m knowledge_harvester stats
```

### WeChat Adapter Technical Details

Extracts from macOS local SQLite databases:
- **DB location:** `~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/{wxid}_{hash}/db_storage/message/message_*.db`
- **Encryption:** WCDB (SQLCipher 4) — PBKDF2-HMAC-SHA512, 256,000 iterations
- **Message types:** Text (1), Image (3), Audio (34), Video (43), Sticker (47), Location (48), Link/File (49), System (10000), Revoke (10002)
- **Role mapping:** `status == 3` or `IsSender == 1` → `"user"`, otherwise → `"assistant"`

### ChatGPT/Grok/Doubao Adapters

- **ChatGPT:** Parses official export ZIP. Traverses `mapping` tree, extracts text + multimodal content.
- **Grok & Doubao:** Browser automation via `BrowserClient` (HTTP API at `127.0.0.1:18791`). Chrome extension relay reuses logged-in sessions. Multiple CSS selector fallbacks. Anti-bot delays (Grok: 2-4s, Doubao: 3-7s).

### WeChat Extension (TypeScript — `extensions/wechat/`)

29 source files, comprehensively tested. **Protocol:** Wechaty with PadLocal (iPad, paid) or Wechat4u (web, free).

| Capability | File | Details |
|-----------|------|---------|
| Send messages | `send.ts` | Text (chunked at 2000 chars), media (FileBox), group & DM |
| Receive messages | `monitor.ts` | Real-time bot events; text, audio, image, video, contact, URL |
| Contact graph | `contact-graph.ts` | Full index with group memberships; search by name/wxid/group |
| Voice transcription | `voice.ts` | SILK→MP3→Whisper (OpenAI) or system (macOS) |
| Moments polling | `moments.ts` | Periodic fetch via PadLocal (default 5min interval) |
| Multi-account | `accounts.ts` | Per-account config overrides |
| Policy/safety | `policy.ts` | DM policy (pairing/allowlist/open/disabled), group policy, @mention gating |
| Health checks | `probe.ts` | Login status, puppet type, response time |
| Reply dispatch | `reply-dispatcher.ts` | Buffered block dispatch with configurable delays |

**Message processing pipeline** (from `monitor.ts`):
1. Skip self messages and stale messages (>60s old)
2. Type dispatch: text, audio (→transcribe), image/video (→save media), contact, URL
3. Context resolution: room/contact, chatId, senderName
4. Group @mention gate (configurable `requireMention`)
5. DM policy enforcement (pairing/allowlist/open/disabled)
6. Route resolution → session key
7. Session recording
8. Reply dispatch → LLM → deliver response

### OpenClaw Memory System

- SQLite-based vector indexing + FTS5 (full-text search)
- Embedding providers: OpenAI (`text-embedding-3-small`), Gemini, Voyage, local (`embeddinggemma-300M-Q8_0.gguf`)
- Hybrid search: vector similarity + BM25 keyword matching
- Configurable chunking: default 400 tokens / 80 overlap
- **Key gap:** Indexes workspace files (MEMORY.md, daily logs) — not connected to knowledge_harvester JSONL data

### OpenClaw Agent Framework

- Agent runner: `src/agents/pi-embedded-runner/run.ts` (Maria Zechner's pi-* packages)
- Tools available: `memory_search`, `memory_get`, `read/write/exec`, `send/channel_send`, `sessions_spawn`
- Sub-agent spawning with isolated memory
- Auto-compaction when context nears limit

## Architecture / Structure

### Layer Stack

```
┌───────────────────────────────────────────────────────────────────┐
│  Layer 4: AI Agents                                               │
│  OpenClaw agent runner + channel_send to WeChat                   │
│  Files: src/agents/pi-embedded-runner/run.ts                      │
├───────────────────────────────────────────────────────────────────┤
│  Layer 3: Query & Retrieval                                       │
│  PersonalKB API — wraps memory_search + keyword search            │
│  Files: NEW src/knowledge_harvester/pkb.py                        │
├───────────────────────────────────────────────────────────────────┤
│  Layer 2: Index & Enrichment                                      │
│  Embeddings (ChromaDB) + contact graph + summaries                │
│  Files: NEW src/knowledge_harvester/embeddings.py                 │
│         NEW src/knowledge_harvester/contacts.py                   │
├───────────────────────────────────────────────────────────────────┤
│  Layer 1: Normalized Storage (JSONL)                              │
│  Existing storage.py + index.json + state.json per platform       │
│  Files: src/knowledge_harvester/storage.py (existing)             │
├───────────────────────────────────────────────────────────────────┤
│  Layer 0: Source Adapters (Extraction)                            │
│  WeChat ✅ | ChatGPT ✅ | Grok ✅ | Doubao ✅ | Gmail ❌ | Docs ❌  │
│  Files: src/knowledge_harvester/adapters/*.py                     │
└───────────────────────────────────────────────────────────────────┘
```

### Storage Directory Structure (Extending Current)

```
openclaw/
└── 知识库/
    ├── conversations/                   # All chat-based sources
    │   ├── wechat/                      # ✅ 538 files, 41MB, 232K messages
    │   │   ├── wechat-{id}.jsonl
    │   │   ├── index.json
    │   │   └── state.json
    │   ├── chatgpt/                     # Ready to extract
    │   ├── grok/                        # Ready to extract
    │   ├── doubao/                      # Ready to extract
    │   └── gmail/                       # Needs adapter
    │       ├── gmail-thread-{id}.jsonl
    │       ├── index.json
    │       └── state.json
    │
    ├── documents/
    │   ├── google-docs/                 # Needs adapter
    │   │   ├── {doc-id}.md
    │   │   └── index.json
    │   └── local/                       # P13 chunker
    │
    ├── _contacts.json                   # NEW: Cross-source contact graph
    ├── _unified_index.json              # NEW: Cross-source conversation index
    └── _embeddings/
        └── pkb.chromadb/               # NEW: ChromaDB persistent store
```

### Gmail Adapter Design

Gmail API with OAuth2 (not MBOX/Takeout):

| Aspect | Gmail API | Google Takeout (MBOX) |
|--------|-----------|----------------------|
| Incremental sync | Query by date, use history API | Full export each time |
| Selectivity | Full query syntax | By label only |
| Speed | Minutes-hours | Hours-days |
| Automation | Fully programmable | Manual trigger |

Rate limits: 15,000 quota units/user/min. `messages.get` = 5 units → 3,000 gets/min.

```python
class GmailAdapter(BaseAdapter):
    platform = "gmail"
    def __init__(self, credentials_path: str = "~/.openclaw/credentials/gmail/"): ...
    def extract(self, source: str = "") -> Iterator[Conversation]:
        # messages.list (maxResults=500) → messages.get (format=raw)
        # Group by threadId → one Conversation per thread
        # Parse RFC 2822 → Message objects
    def extract_incremental(self, since: datetime) -> Iterator[Conversation]:
        # Query: after:YYYY/MM/DD or history.list API
```

### Google Docs Adapter Design

Drive API for listing + export as `text/markdown` (new format, best for KB).
Rate limits: 300 read requests/user/min. Export limit: 10MB/file.
Incremental sync: Drive API Changes API (`changes.getStartPageToken` + `changes.list`).

### Embedding & Vector Search

**ChromaDB** (over FAISS and SQLite-vec):

| | FAISS | ChromaDB | SQLite-vec |
|---|---|---|---|
| Query speed (250K vectors) | ~0.34ms | ~10-17ms | ~50-190ms |
| Metadata filtering | No (DIY) | Built-in | SQL WHERE |
| Full-text search | No | Built-in | Via FTS5 |
| Setup complexity | Medium | Low | Low |
| Persistence | Manual | Built-in | Built-in |

**BGE-M3** embedding model (BAAI):

| Model | Params | Dims | Max Tokens | Chinese/English |
|---|---|---|---|---|
| **BGE-M3** (BAAI) | 570M | 1024 | 8,192 | Excellent |
| Qwen3-Embedding-0.6B | 600M | 32-1024 | Large | Best benchmarks (#1 MTEB) |
| paraphrase-multilingual-MiniLM-L12-v2 | 118M | 384 | 512 | Good |
| OpenAI text-embedding-3-small | API | 1536 | 8,191 | Good |

BGE-M3: strong Chinese+English, 8K context, dense+sparse retrieval, runs locally.

### Contact Graph

```python
@dataclass
class UnifiedContact:
    id: str                          # Generated UUID
    display_name: str
    aliases: List[str]
    identities: Dict[str, str]       # {"wechat": "wxid_xxx", "gmail": "alice@gmail.com"}
    groups: List[str]
    conversation_ids: Dict[str, List[str]]  # {platform: [conv_ids]}
    last_interaction: str
    interaction_count: int
    topics: List[str]

class ContactGraph:
    def build_from_sources(self, platforms: List[str]) -> List[UnifiedContact]
    def merge_identities(self, name_a, source_a, name_b, source_b)
    def search(self, query: str) -> List[UnifiedContact]
    def get_context_for(self, contact_id: str, max_tokens: int = 4000) -> str
```

Merge heuristics: same email → auto-merge; WeChat remark matches Gmail name → suggest; manual merge for ambiguous.

### PersonalKB Query Interface

```python
class PersonalKB:
    def __init__(self, kb_root, embeddings, contacts): ...
    def search(self, query, sources=None, limit=20, semantic=True) -> List[SearchResult]
    def get_conversation(self, platform, conv_id) -> Conversation
    def get_contact(self, name) -> UnifiedContact
    def get_context(self, topic, max_tokens=8000) -> str  # RAG-ready
    def get_recent(self, platform, conv_id, limit=50) -> List[Message]
    def get_conversation_summary(self, platform, conv_id) -> str  # LLM-generated, cached
    def stats(self) -> Dict
```

### OpenClaw Integration

**Sidecar approach (recommended):** PKB as separate Python module. OpenClaw agents call via `pkb_search` tool:

```typescript
{
  name: "pkb_search",
  description: "Search personal knowledge base across WeChat, ChatGPT, Gmail, etc.",
  parameters: {
    query: { type: "string" },
    sources: { type: "array", items: { type: "string" }, optional: true },
    limit: { type: "number", default: 10 }
  }
}
```

Alternative: point `memorySearch.extraPaths` at `知识库/conversations/` — simpler but less control.

## WeChat Agent Controller

### Architecture

```
                    ┌─────────────────────┐
                    │   Agent Controller   │
                    │   (new module)       │
                    └────────┬────────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
   │ WeChat Ext   │  │ Personal KB  │  │ LLM (Claude) │
   │ (existing)   │  │ (new)        │  │ (existing)   │
   │ • monitor.ts │  │ • search()   │  │ • Opus 4.6   │
   │ • send.ts    │  │ • contacts   │  │ • Haiku 4.5  │
   │ • contact-   │  │ • context()  │  │              │
   │   graph.ts   │  │ • embeddings │  │              │
   └─────────────┘  └──────────────┘  └──────────────┘
```

Orchestration: receive message → query PKB → assemble prompt → call LLM → safety check → deliver via WeChat.

### WeChat Bot Protocol Options (2025-2026)

| Protocol | Type | Status | Cost | Platform |
|----------|------|--------|------|----------|
| **PadLocal** (current) | iPad protocol | Active, beta | Paid (7-day trial) | Cross-platform |
| **Wechat4u** (current) | Web protocol | Limited | Free | Cross-platform |
| **WeChatFerry (WCF)** | Windows Hook (C++) | Active, Apr 2025 | Free | Windows only |
| **WeChatPadPro** | Pad protocol | Active | Paid | Cross-platform |
| **Wechaty puppet-xp** | Windows Hook | Active | Free | Windows only |
| **859 iPad Protocol** | iPad protocol | Enterprise | Paid | Cross-platform |

Recommendation: stay with PadLocal for macOS. Monitor WeChatFerry for future Windows deployment.

### WeChat Risk Control (2025 Tencent Security Report)

| Metric | Value |
|--------|-------|
| Daily banned accounts increase (YoY) | +37% Q2 2024 |
| New registration ban rate (first 7 days) | 43% |
| Abnormal device environment bans | 31% |
| Abnormal operational behavior bans | 28% |

Rate limits: max 40 msgs/min same recipient (1-3s intervals); 3-5s between different recipients; friend requests 5-50/day by account age.

Detection methods: device fingerprinting, network analysis, behavioral AI, session tracking, login pattern detection.

### Safety System

```python
class SafetyConfig:
    min_reply_delay_ms: int = 30_000    # 30s minimum
    max_reply_delay_ms: int = 120_000   # 2min maximum
    jitter_factor: float = 0.3          # ±30% randomization
    active_hours: tuple = (9, 22)       # 9am-10pm only
    max_messages_per_hour: int = 20
    max_messages_per_conversation_per_hour: int = 5
    cooldown_after_burst: int = 300     # 5min after 3 rapid messages
    never_initiate: bool = True         # Only respond, never start
```

### Scenario A: 1-on-1 Conversation Agent

Agent reads a 1:1 conversation, monitors real-time, replies on your behalf.

**Flow:** Load history from JSONL → build contact profile → generate conversation summary → monitor via `monitor.ts` → on new message: retrieve context + PKB search → assemble prompt with persona → LLM generate → deliver (approval or auto mode).

**Prompt template:**
```python
system_prompt = f"""
You are acting as {user_name} in a WeChat conversation with {contact_name}.
## Your persona
{persona_description}
## About {contact_name}
{contact_profile}  # From ContactGraph + PKB
## Conversation summary
{conversation_summary}  # LLM-generated, cached
## Important context from knowledge base
{pkb_context}  # Semantic search results
## Rules
- Match language (Chinese/English/mixed) and tone
- Keep responses concise (WeChat style)
- Never reveal you are an AI
- Never share content from other conversations
"""
```

**Config:**
```yaml
agents:
  personal_reply_zhangsan:
    type: personal-reply
    channel: wechat
    target: { kind: direct, contact_name: "张三", contact_wxid: "wxid_zhangsan123" }
    mode: approval  # approval | auto | observe-only
    persona: "Casual and friendly. Match their language."
    context: { recent_messages: 50, pkb_search_enabled: true }
    safety: { min_reply_delay_ms: 30000, max_reply_delay_ms: 120000, active_hours: [9, 22] }
    llm: { model: claude-opus-4-6, max_tokens: 500 }
```

### Scenario B: Group Engagement Agent

Agent participates in a group chat — jokes, coordination, topic engagement.

**Key challenge:** Must decide *when* to speak. Not every message.

```python
class GroupParticipationEngine:
    def should_respond(self, message, context) -> tuple[bool, str]:
        if self.is_mentioned(message):       return True, "mentioned"
        if self.is_direct_question(message): return True, "direct_question"
        if self.matches_specialty(message):
            if random.random() < self.participation_rate:
                return True, "specialty_match"
        if self.conversation_is_dying(context):
            if self.has_something_to_share(): return True, "revival"
        for trigger in self.triggers:
            if trigger.matches(message):     return True, f"trigger:{trigger.name}"
        return False, "skip"
```

**Config:**
```yaml
agents:
  tennis_group:
    type: group-engagement
    target: { kind: group, group_name: "网球群", group_id: "12345678@chatroom" }
    mode: active
    persona: "Fun tennis enthusiast. Jokes in Chinese. Help coordinate matches."
    participation: { rate: 0.15, max_per_hour: 5, never_respond_twice_in_row: true }
    specialties: ["tennis technique", "match scheduling", "weather and courts"]
    triggers:
      - { name: mention, pattern: "@我|@agent", action: always_reply }
      - { name: scheduling, pattern: "打球|约球|比赛", action: engage }
      - { name: weather, pattern: "天气|下雨", action: share_weather }
```

### Scenario C: Tech News Curator Agent

Agent curates, summarizes, and analyzes tech news in a sharing group.

**Unique capabilities:**
1. **Link summarization:** detect URLs → fetch + readability parse → LLM summarize + analyze
2. **Proactive sharing:** scheduled RSS/arXiv fetch → filter by relevance → share top articles
3. **PKB cross-referencing:** connect news to user's existing knowledge ("relates to X you discussed last week")

**Config:**
```yaml
agents:
  tech_curator:
    type: news-curator
    target: { kind: group, group_name: "技术分享群" }
    focus_areas: ["AI/ML", "battery technology", "semiconductors", "startups"]
    actions: { summarize_links: true, proactive_sharing: true, max_shares_per_day: 4 }
    news_sources:
      - { type: rss, url: "https://hnrss.org/newest?points=100", name: "HN" }
      - { type: rss, url: "https://36kr.com/feed", name: "36氪" }
      - { type: arxiv, categories: ["cs.AI", "cs.CL"], name: "arXiv" }
    llm: { model: claude-opus-4-6, summarize_model: claude-haiku-4-5 }
```

## Key Decisions

- **ChromaDB over FAISS/SQLite-vec**: Best balance of speed (10-17ms at 250K), built-in metadata filtering, persistence, and ease of use at our scale
- **BGE-M3 over OpenAI embeddings**: Local (no API cost, no data leaves machine), excellent Chinese+English, 8K context, dense+sparse retrieval
- **PadLocal over other WeChat protocols**: Only production-viable option for macOS; already integrated in OpenClaw
- **Sidecar PKB over memory system integration**: More control over chunking and metadata; keeps concerns separated
- **Approval mode as default**: Safety-first; auto mode requires explicit opt-in
- **Claude Opus for generation, Haiku for triage**: Best reasoning for persona adherence; Haiku for binary decisions and bulk summarization

**Estimated daily LLM cost (all agents):** ~$2-4/day with Opus for generation, Haiku for triage.

## Alternative Approaches

- **Use existing chatgpt-on-wechat (CowAgent)**: Most mature open-source WeChat AI project (30K+ stars, v1.7.5). But it's a generic chatbot — no PKB integration. Our differentiator is the personal knowledge base context.
- **WeChatFerry instead of PadLocal**: Free, active (Apr 2025), but Windows-only. Good future option for server deployment.
- **OpenAI embeddings instead of BGE-M3**: Faster initial indexing ($0.50 for full index), but data leaves machine and ongoing API cost.
- **Memory system extraPaths**: Point at `知识库/conversations/` for free indexing. Simpler but 400-token chunks suboptimal for conversation data.

## Risk Mitigation

- **WeChat account ban**: Human-like delays (30-120s), active hours only, low participation rate, never initiate. Approval mode as default.
- **Cross-conversation leakage**: Enforced in system prompt + code. Agent never shares content from one conversation in another.
- **Runaway agent**: Kill switch (`openclaw agent stop --all`). Rate limits at Agent Controller level.
- **Embedding quality**: Test with real Chinese+English queries. Fall back to OpenAI if BGE-M3 quality insufficient.
- **PadLocal service disruption**: Monitor WeChatFerry as backup protocol. Keep bot logic protocol-agnostic via Wechaty abstraction.

## Related Projects

| Project | Stars | Status | Protocol | Notes |
|---------|-------|--------|----------|-------|
| chatgpt-on-wechat (CowAgent) | 30K+ | v1.7.5 (Apr 2025) | WeChatFerry, Wechaty, itchat | Most mature. Multi-LLM. Long-term memory. |
| wechat-gptbot | 5K+ | Active | Windows Hook | Plugin system. |
| AstrBot + WeChatPadPro | Growing | Active 2025 | Pad protocol | Docker-based. Visual panel. |
| wechat-bot | 3K+ | Active | Wechaty | Group analysis, zombie detection. |
| WinAutoWx | New | Active 2025 | MCP-based | Claude/GPT to WeChat desktop via MCP. |

## File Inventory

### Existing
```
src/knowledge_harvester/
├── main.py, config.py, models.py, storage.py, search.py, browser_client.py
├── adapters/{base,chatgpt,wechat,grok,doubao}.py
└── tests/

extensions/wechat/src/
├── bot.ts, send.ts, channel.ts, monitor.ts, contact-graph.ts
├── voice.ts, moments.ts, accounts.ts, config-schema.ts, policy.ts
├── probe.ts, reply-dispatcher.ts, status-issues.ts, onboarding.ts
├── actions.ts, outbound.ts, targets.ts, client.ts, runtime.ts, types.ts
└── *.test.ts
```

### New files to create
```
src/knowledge_harvester/
├── adapters/gmail.py          # Gmail API adapter
├── adapters/gdocs.py          # Google Docs adapter
├── embeddings.py              # ChromaDB + BGE-M3 pipeline
├── contacts.py                # Cross-source contact graph
└── pkb.py                     # PersonalKB unified query API

src/agents/tools/
└── pkb-search-tool.ts         # PKB search tool for agents

src/agents/wechat-agent/
├── controller.ts              # Agent Controller
├── participation.ts           # Group participation engine
├── news-curator.ts            # News curation pipeline
└── safety.ts                  # Rate limiting + content filtering
```
