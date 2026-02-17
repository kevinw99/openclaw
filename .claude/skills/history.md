---
name: history
description: Explore and manage Claude Code session history (scan, list, replay, search, stats)
user_invocable: true
---

# Session History

Run the session_history tool to explore Claude Code session history.

Parse the user's arguments to determine which subcommand to run. Default to `list` if none specified.

Commands:
- `scan [--incremental]` - Scan and classify sessions
- `list [--type <type>]` - List sessions with classifications
- `replay <entity> [--raw]` - Generate replay for an entity
- `search <query> [--limit N]` - Search session content
- `stats` - Show classification statistics

Run from project root:
```bash
cd "$(git rev-parse --show-toplevel)/src" && python3 -m session_history <command> [args]
```
