# Session History

Classifies and replays Claude Code sessions by project entity (specs, source code, research, etc.).

## Usage

Run from the `src/` directory:

```bash
cd src

# Scan and classify all sessions
python3 -m session_history scan

# List classified sessions
python3 -m session_history list

# Generate replay files for a specific entity
python3 -m session_history replay 01_data-pipeline

# Search across sessions
python3 -m session_history search "keyword"

# Show statistics
python3 -m session_history stats
```

## How It Works

1. **Discovers** project entities from directory structure (specs, source projects, research topics, etc.)
2. **Reads** Claude Code session JSONL files from `~/.claude/projects/`
3. **Classifies** sessions using file path, text pattern, and keyword signals
4. **Generates** per-entity session indices and human-readable replay files

## Configuration

By default, the tool uses these directory conventions:

| Logical Name | Default Directory |
|-------------|-------------------|
| spec        | `specs/`          |
| source      | `src/`            |
| research    | `research/`       |
| knowledge   | `docs/`           |
| tool        | `scripts/`        |

Spec naming pattern: `##_descriptive-name` (e.g., `01_data-pipeline`)

### Custom Configuration

Create `.session-history.json` at your project root to override defaults:

```json
{
  "entity_dirs": {
    "spec": "specifications",
    "source": "source",
    "research": "research",
    "knowledge": "knowledge-base",
    "tool": "tools"
  },
  "history_root": "session-history",
  "spec_pattern": "([A-Z]\\d+)_(.+)",
  "spec_display": "Spec {num}: {desc}",
  "restricted_spec_dir": "RESTRICTED/specs",
  "legacy_aliases": {
    "A01_old-name": ["01_old-name"]
  },
  "skip_files": {
    "spec": ["00_template"],
    "research": ["README.md"]
  }
}
```

## Running Tests

```bash
cd src
python3 -m unittest discover -s session_history/tests -v
```
