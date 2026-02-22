# Tasks: Personal Knowledge Base & AI Agent Platform

## Phase 1: Complete Extraction

**Goal:** Get all data sources into canonical JSONL format.

- [ ] Task 1.1 - Run ChatGPT adapter (`import-chatgpt`) — need export ZIP from OpenAI first
- [ ] Task 1.2 - Run Grok adapter (`scrape-grok`) — requires OpenClaw browser gateway running
- [ ] Task 1.3 - Run Doubao adapter (`scrape-doubao`) — requires OpenClaw browser gateway running
- [ ] Task 1.4 - Set up Google Cloud project with OAuth2 (Gmail + Drive APIs)
- [ ] Task 1.5 - Build Gmail adapter (`gmail.py`) — OAuth2 flow, thread extraction, incremental sync
- [ ] Task 1.6 - Build Google Docs adapter (`gdocs.py`) — Drive API export as markdown, Changes API sync
- [ ] Task 1.7 - Validate all extracted data, fix any parsing issues
- [ ] Task 1.8 - Run `knowledge_harvester stats` — document final source counts

## Phase 2: Unified Index & Semantic Search

**Goal:** Make all data searchable via keyword + semantic search.

- [ ] Task 2.1 - Install ChromaDB (`pip install chromadb`), set up persistent store at `_embeddings/pkb.chromadb/`
- [ ] Task 2.2 - Download BGE-M3 embedding model (`pip install FlagEmbedding` or HuggingFace)
- [ ] Task 2.3 - Build embedding pipeline (`embeddings.py`) — chunk messages → embed → store in ChromaDB
- [ ] Task 2.4 - Run initial full embedding index (~250K messages, ~14 hours on M1 Mac)
- [ ] Task 2.5 - Build unified cross-source index (`_unified_index.json`) — merge all platform index.json files
- [ ] Task 2.6 - Build contact graph (`contacts.py`) — WeChat contacts + cross-source name matching
- [ ] Task 2.7 - Implement PersonalKB query interface (`pkb.py`) — wraps storage + ChromaDB + contacts
- [ ] Task 2.8 - Test retrieval quality — especially cross-language (Chinese query → English result and vice versa)
- [ ] Task 2.9 - Add `pkb search` CLI command to knowledge_harvester main.py

## Phase 3: WeChat Agent — Scenario A (1-on-1 Reply)

**Goal:** Working 1-on-1 reply agent with approval mode.

- [ ] Task 3.1 - Build Agent Controller module (`wechat-agent/controller.ts`)
- [ ] Task 3.2 - Implement prompt assembly — persona + contact profile + conversation summary + PKB context
- [ ] Task 3.3 - Register `pkb_search` tool in OpenClaw agent toolkit (`pkb-search-tool.ts`)
- [ ] Task 3.4 - Implement approval mode (human-in-the-loop) — response shown in UI, user approves/edits/rejects
- [ ] Task 3.5 - Implement auto mode with safety config — delays, rate limits, active hours
- [ ] Task 3.6 - Implement safety module (`safety.ts`) — SafetyConfig, rate limiting, content filtering
- [ ] Task 3.7 - End-to-end test with a real 1:1 conversation — iterative prompt tuning

## Phase 4: WeChat Agent — Scenarios B & C

**Goal:** Group engagement agent + news curator agent.

- [ ] Task 4.1 - Build GroupParticipationEngine (`participation.ts`) — when to speak logic
- [ ] Task 4.2 - Implement trigger system — pattern matching + configurable actions
- [ ] Task 4.3 - Implement GroupContext assembly — members, active members, topics, vibe
- [ ] Task 4.4 - Test Scenario B with a real group chat (e.g., tennis group)
- [ ] Task 4.5 - Build news curation pipeline (`news-curator.ts`) — RSS fetch + arXiv + filtering
- [ ] Task 4.6 - Implement link summarization — URL extraction + readability parse + LLM summarize
- [ ] Task 4.7 - Implement PKB cross-referencing in responses — connect news to existing knowledge
- [ ] Task 4.8 - Test Scenario C with a real tech group

## Phase 5: Polish & Expand

**Goal:** Production hardening and feature expansion.

- [ ] Task 5.1 - Agent monitoring dashboard (web UI) — see what agents are doing/saying
- [ ] Task 5.2 - Multi-agent coordination — run multiple group agents simultaneously
- [ ] Task 5.3 - Learning from feedback — track which responses got reactions/replies
- [ ] Task 5.4 - Mobile notifications for approval mode — push when agent needs approval
- [ ] Task 5.5 - Expand to Telegram/Slack/Discord (OpenClaw already has these channels)

## Notes

- Phase 1 tasks 1.1-1.3 can run in parallel (independent adapters)
- Phase 1 tasks 1.5-1.6 depend on task 1.4 (Google Cloud project setup)
- Phase 2 task 2.4 (full embedding) takes ~14 hours — run overnight
- Phase 3 depends on Phase 2 (PKB must be searchable before agents can query it)
- Phase 4 builds on Phase 3 (Agent Controller is shared infrastructure)
- Embedding pipeline sizing: 250K messages × ~100 tokens avg = 25M tokens; BGE-M3 at ~500 tokens/sec on M1
- Daily LLM cost estimate (all agents): ~$2-4/day (Opus for generation, Haiku for triage)
- PadLocal subscription required for WeChat bot — confirm token availability before Phase 3
