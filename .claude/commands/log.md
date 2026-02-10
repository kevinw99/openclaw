# Update Work Log

Please update the project's `WORK_LOG.md` file in the root directory.

## Update Steps

1. **Read current work log**
   - Read `WORK_LOG.md` from the project root

2. **Get today's Git Commits**
   - Run `git log --since="today 00:00" --format="%h %s"` to get today's commits

3. **Summarize this conversation**
   - Summarize all user instructions from this conversation (in chronological order)
   - List completed work tasks
   - Record important decisions and notes

4. **Update log file**
   - If today's date entry already exists, update that entry
   - If it doesn't exist, add today's entry at the top (after the `---` separator)
   - Update the "Last Updated" timestamp

## Log Entry Format

```markdown
## YYYY-MM-DD

**Session Time**: HH:MM - HH:MM

### User Instructions

1. **Instruction Title**
   - Instruction: "User's original request or summary"
   - Requirements: Specific requirements

### Work Completed

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Task description | Done/In Progress/Not Done | Notes |

### Git Commits

```
commit_hash commit_message
```

### Notes

- Important decisions
- Issues encountered
- Follow-up items
```

## Guidelines

- Order by date descending (newest at top)
- Preserve user instructions as accurately as possible
- Notify user when update is complete
