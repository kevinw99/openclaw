---
name: extract-history
description: Extract and search personal AI conversation history from ChatGPT, Grok, Doubao, and WeChat using the knowledge_harvester tool.
user_invocable: true
---

# Extract History

Run the knowledge_harvester tool to extract, search, and manage personal AI conversation history.

## How to Run

The tool is at `src/knowledge_harvester/`. First determine the project root via `git rev-parse --show-toplevel`, then run:

```bash
cd "$(git rev-parse --show-toplevel)/src" && python3 -m knowledge_harvester <command> [options]
```

## Available Commands

Parse the user's arguments to determine which subcommand to run:

- **`import-chatgpt <path>`** — Import ChatGPT export (ZIP or conversations.json)
  - Add `-i` for incremental mode (skip unchanged conversations)
- **`scrape-grok`** — Extract Grok conversations via browser automation
  - Requires OpenClaw gateway + Chrome extension
  - `--browser-url`, `--profile` options available
- **`scrape-doubao`** — Extract Doubao conversations via browser automation
  - Same requirements as Grok
- **`extract-wechat [source]`** — Extract WeChat conversations from local SQLite DB
  - `--key <hex>` — SQLCipher decryption key (64-char hex)
  - `--key-file <path>` — File containing the key
  - `--data-dir <path>` — Custom data directory
- **`search <query>`** — Search across all imported conversations
  - `--platform <name>` — Filter by platform
  - `--limit N` — Max results (default: 20)
- **`list`** — List all imported conversations by platform
- **`stats`** — Show knowledge base statistics

## Examples

```
/extract-history import-chatgpt ~/Downloads/chatgpt-export.zip
/extract-history import-chatgpt ~/Downloads/chatgpt-export.zip -i
/extract-history search "Python 装饰器"
/extract-history search "React hooks" --platform chatgpt
/extract-history stats
/extract-history list
/extract-history extract-wechat --key abc123...
```

## Instructions

1. Parse the user's argument to determine the subcommand
2. If no argument is given, run `stats` as the default (show knowledge base overview)
3. Run the appropriate command using Bash
4. Present the output to the user in a readable format
