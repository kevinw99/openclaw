---
name: log
description: Update the project work log with session summary
user_invocable: true
---

# Update Work Log

Read the current `WORK_LOG.md`, get today's git commits via `git log --since="today 00:00" --format="%h %s"`, summarize user instructions and completed work from this conversation, and update the log file.

If today's date entry already exists, update it. Otherwise add a new entry at the top (after the `---` separator).

## Entry Format

```markdown
## YYYY-MM-DD

**Session Time**: HH:MM - HH:MM

### User Instructions
1. **Title** - Summary of request

### Work Completed
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Description | Done/In Progress/Not Done | Notes |

### Git Commits
```
hash message
```

### Notes
- Decisions, issues, follow-ups
```
