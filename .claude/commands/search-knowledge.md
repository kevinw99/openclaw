# Search Personal Knowledge Base

Search across all extracted personal conversation history (WeChat, ChatGPT, Grok, Doubao).

## How to Run

```bash
cd "$(git rev-parse --show-toplevel)/src" && python3 -m knowledge_harvester search "$ARGUMENTS" --limit 30
```

## Instructions

1. Run the search command with the user's query
2. Present results clearly: show platform, conversation title, timestamp, and message content
3. If the user asks follow-up questions about a specific conversation, use `list` to show its full context
4. If no arguments given, run `stats` instead to show the knowledge base overview
