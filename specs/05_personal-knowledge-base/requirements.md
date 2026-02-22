# Requirements: Personal Knowledge Base & AI Agent Platform

## Overview

Build a unified personal knowledge base (PKB) from all conversation and document sources, then expose it to AI agents that can act on the user's behalf — starting with WeChat.

The system sits on top of OpenClaw's existing infrastructure: the knowledge harvester for extraction, the memory system for indexing, and the WeChat extension for real-time messaging. This spec defines how to wire them together and fill the gaps.

## Objectives

- Consolidate all personal conversation and document data into a single, searchable knowledge base
- Enable semantic (vector) search across all sources in both Chinese and English
- Build a unified contact graph that resolves identities across platforms
- Create AI agents that can communicate on WeChat using the PKB as context
- Support three WeChat agent scenarios: 1-on-1 reply, group engagement, and news curation

## Scope

### In scope

- Data extraction from: WeChat, ChatGPT, Grok, Doubao, Gmail, Google Docs, local files
- Local-first storage with JSONL canonical format (extending existing knowledge_harvester)
- Embedding pipeline with ChromaDB + BGE-M3 for semantic search
- Cross-source contact graph with identity resolution
- PersonalKB query API (Python)
- `pkb_search` tool registered in OpenClaw agent framework
- WeChat Agent Controller with 3 scenarios (1-on-1, group, news curator)
- Safety system: rate limiting, human-like delays, approval mode, kill switch

### Out of scope

- Cloud/server deployment (local-only for now)
- Agents on platforms other than WeChat (future phase)
- Real-time sync with WeChat (read-only from DB extraction; real-time via bot extension)
- Training or fine-tuning custom models

## Content Sources Inventory

| Source          | Type                     | Volume (est.)                    | Extraction Status      | Adapter                  | Technical Details                                                 |
| --------------- | ------------------------ | -------------------------------- | ---------------------- | ------------------------ | ----------------------------------------------------------------- |
| **WeChat**      | Chat (1:1 + group)       | 538 convos, 232K+ messages, 41MB | Extracted              | `wechat.py` (652 lines)  | macOS SQLite + WCDB/SQLCipher4 decryption                         |
| **ChatGPT**     | AI conversations         | ~100 convos, ~10K messages       | Adapter ready, not run | `chatgpt.py` (244 lines) | Parses official ChatGPT ZIP export (`conversations.json`)         |
| **Grok**        | AI conversations         | ~50 convos, ~5K messages         | Adapter ready, not run | `grok.py` (295 lines)    | Browser automation via OpenClaw HTTP API (Chrome extension relay) |
| **Doubao**      | AI conversations         | ~30 convos, ~3K messages         | Adapter ready, not run | `doubao.py` (311 lines)  | Browser automation, extra anti-bot delays (3-7s)                  |
| **Gmail**       | Email                    | TBD                              | No adapter             | Needs `gmail.py`         | Gmail API + OAuth2                                                |
| **Google Docs** | Documents                | TBD                              | No adapter             | Needs `gdocs.py`         | Drive API + export as markdown                                    |
| **Local Files** | Mixed (PDF, MD, DOCX...) | TBD                              | P13 chunker exists     | Enpack_CCC P13           | LLM-driven two-stage extraction pipeline                          |

**Total estimated:** ~880+ conversations, ~250K+ messages once fully extracted.

## Success Criteria

- [ ] All 7 data sources extracted and stored in canonical JSONL format
- [ ] Semantic search returns relevant results across sources in <100ms
- [ ] Cross-source contact graph resolves identities (WeChat name ↔ email address)
- [ ] WeChat Scenario A: 1-on-1 agent can generate contextually appropriate replies in approval mode
- [ ] WeChat Scenario B: Group agent participates naturally at configurable participation rate
- [ ] WeChat Scenario C: News curator summarizes shared links and proactively shares relevant news
- [ ] All agents respect safety constraints (rate limits, active hours, no cross-conversation leakage)

## Constraints & Assumptions

- All data stored locally — no cloud storage dependency
- LLM API calls (Claude) are the only external data path — unavoidable for generation
- WeChat bot relies on PadLocal (paid iPad protocol) — requires active subscription
- BGE-M3 embedding runs locally on M1/M2 Mac — initial full index takes ~14 hours
- WeChat account ban risk exists — mitigated by human-like behavior, not eliminated
- Mixed Chinese/English content throughout — embedding model must handle both

## Dependencies

| Dependency                       | Source                                    | Status           | Required For          |
| -------------------------------- | ----------------------------------------- | ---------------- | --------------------- |
| Knowledge Harvester adapters     | openclaw `src/knowledge_harvester/`       | Ready            | Phase 1               |
| WeChat Extension (bot framework) | openclaw `extensions/wechat/`             | Built            | Phase 3-4             |
| Wechaty + PadLocal puppet        | npm                                       | Installed        | Phase 3-4             |
| OpenClaw agent runner            | openclaw `src/agents/`                    | Built            | Phase 3-4             |
| OpenClaw memory system           | openclaw `src/memory/`                    | Built            | Phase 2 (optional)    |
| P13 Document Chunker             | Enpack_CCC `源代码/chunked_processor/`    | Production       | Phase 1 (local files) |
| Claude API access                | Anthropic                                 | Available        | Phase 3-4             |
| ChromaDB                         | `pip install chromadb`                    | Need to install  | Phase 2               |
| BGE-M3 embedding model           | HuggingFace / `pip install FlagEmbedding` | Need to download | Phase 2               |
| Gmail API credentials            | Google Cloud Console                      | Need to set up   | Phase 1               |
| Google Drive API credentials     | Google Cloud Console                      | Need to set up   | Phase 1               |
| ChatGPT data export              | OpenAI account settings                   | Need to request  | Phase 1               |

## Questions & Clarifications

### Resolved

| Question                 | Answer                                                                |
| ------------------------ | --------------------------------------------------------------------- |
| WeChat bot protocol?     | Wechaty + PadLocal (iPad protocol). Stable, paid service.             |
| Embedding storage?       | ChromaDB (best balance at 250K scale). BGE-M3 for embeddings.         |
| Gmail approach?          | Gmail API with OAuth2 (not Takeout). 3,000 gets/min.                  |
| Multi-device?            | Yes — PadLocal uses iPad protocol, can run alongside phone WeChat.    |
| OpenClaw email handling? | No email adapter exists. Build new `gmail.py` in knowledge_harvester. |

### Still open

1. **PadLocal token**: Do we have an active PadLocal subscription? Need to confirm token availability.
2. **Cost budget**: Is ~$2-4/day acceptable for running all agents? Can be reduced by using Haiku more aggressively.
3. **Which conversations first?**: For Scenario A, which 1:1 contact should we test with?
4. **Which groups first?**: For Scenario B/C, which specific groups?
5. **ChatGPT export**: Have you already requested the data export from OpenAI? It can take 24-48 hours.
6. **Google Cloud project**: Do you already have a Google Cloud project, or do we need to set one up from scratch?
7. **WeChatFerry**: Should we explore WeChatFerry as a free alternative to PadLocal? Requires a Windows machine or VM.
