---
name: create-task
description: Create a new numbered task directory under tasks/ for operational work that doesn't need a full spec. Use when user says "create a task" or "new task".
user_invocable: true
---

# Create Task

Create a numbered task entity under the `tasks/` directory. Tasks are for operational work that doesn't warrant a full spec — migrations, cleanups, one-off investigations, etc.

## Steps

1. **Get the task name** from the user's arguments. If none provided, ask what the task is about.

2. **Determine next number**:
   ```bash
   ls -d tasks/[0-9]*_* 2>/dev/null | sort -t/ -k2 -V | tail -1
   ```
   Extract the highest number, increment by 1. If no tasks exist yet, start at `01`. Zero-pad to 2 digits.

3. **Slugify the name**: lowercase, replace spaces with hyphens, strip special chars. Example: "Three-Tier History Storage" → `three-tier-history-storage`

4. **Create the directory and README**:
   ```
   tasks/NN_slug-name/
   tasks/NN_slug-name/README.md
   ```

5. **Create `tasks/` directory first if it doesn't exist.**

## README.md Template

```markdown
# Task NN: {Title}

> {One-line description}

## Status: Active

## Goal

{What needs to be done and why}

## Done When

- [ ] {Concrete completion criteria}
```

Fill in the title from the task name. Leave `{One-line description}`, `{What needs to be done and why}`, and `{Concrete completion criteria}` for the user to fill in, OR fill them in if the user provided enough context.

## After Creation

Tell the user:
- The task path: `tasks/NN_slug-name/`
- History will be stored inline at `tasks/NN_slug-name/history/` (auto-managed by session_history)
- They can run `session_history scan` to classify sessions under this task
