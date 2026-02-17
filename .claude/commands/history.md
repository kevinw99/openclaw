# Session History

Manage and explore Claude Code session history using the session_history tool.

## How to Run

The tool is at `src/session_history/`. First determine the project root via `git rev-parse --show-toplevel`, then run:

```bash
cd "$(git rev-parse --show-toplevel)/src" && python3 -m session_history <command> [options]
```

## Available Commands

Based on user input (or default to `list` if no specific command mentioned):

- **scan** — Scan all sessions and classify them. Use `--incremental` / `-i` for incremental scan.
- **list** — List all sessions with classifications. Use `--type <type>` to filter.
- **replay `<entity>`** — Generate readable replay for an entity. Use `--raw` for old-format HTML/Markdown.
- **search `<query>`** — Search session content. Use `--limit N` to control matches per session.
- **stats** — Show classification statistics.

## Instructions

1. Parse the user's argument (e.g., `/history scan`, `/history search auth`, `/history stats`)
2. If no argument is given, run `list` as the default
3. Run the appropriate command using Bash
4. Present the output to the user
