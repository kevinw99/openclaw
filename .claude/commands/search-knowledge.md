# Search Personal Knowledge Base

Search across all extracted personal conversation history (WeChat, ChatGPT, Grok, Doubao).

## How to Run

```bash
cd "$(git rev-parse --show-toplevel)/src" && python3 -m knowledge_harvester search "$ARGUMENTS" --limit 30
```

## Instructions

1. Run the search command with the user's query
2. Present results clearly: show platform, conversation title, timestamp, and message content
3. If the user asks follow-up questions about a specific conversation, use `view` to show its full context
4. If no arguments given, run `stats` instead to show the knowledge base overview

## Tiered Context Retrieval

Search results show **Tier 0** inline labels (e.g. `[文件: AI计划.pdf (2.3MB)]`, `[链接: 深度学习入门]`).

- **Tier 0 (default)**: Present the search results as-is — inline labels are already in message content
- **Tier 1 (on request)**: When user wants file/link details, run `view <conversation> --media` to show full metadata (URL, description, file size)
- **Tier 2 (future)**: AI-generated summary of file contents — not yet implemented
- **Tier 3 (explicit)**: Read actual file from filesystem — only when user explicitly asks to read a specific file's contents

Escalation flow: search shows Tier 0 → user asks "what file?" → `view --media` shows Tier 1 → user asks "what does it say?" → read file from disk (Tier 3)
