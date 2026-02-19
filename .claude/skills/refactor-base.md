---
name: refactor-base
description: Identify and fix base project inefficiencies — hardcoded paths, project-specific assumptions, non-portable patterns
user_invocable: true
---

# Refactor Base Project Tool

When a base-owned tool (from `~/AI/base`) doesn't work in a new project, use this workflow to diagnose and fix the portability issue.

## Ownership Rule

Base-owned files live in `~/AI/base` and are pulled into project repos via `git merge base/main`. The canonical list from REPO_GUIDE.md:
- `PROJECT_GUIDELINES.md`
- `specs/00_template/`
- `src/session_history/`
- `.claude/commands/` and `.claude/skills/`
- `.claude/settings.json`

**All fixes MUST be made in `~/AI/base`, then pulled into the project repo.** Never fix base files only in the project repo.

## Diagnosis Workflow

1. **Identify the symptom** — what failed and in which project?
2. **Find the hardcoded assumption** — scan the base tool for:
   - Hardcoded paths (e.g., `~/.claude/projects/-Users-kweng-AI-Enpack-CCC`)
   - Hardcoded directory names (e.g., `规格/` instead of also supporting `spec/`)
   - Project-specific naming conventions (e.g., `P##_` prefix only, not `##_`)
   - Hardcoded project slugs, URLs, or identifiers
3. **Design the generic fix**:
   - Derive paths from `git rev-parse --show-toplevel` or project root
   - Support multiple naming conventions (Chinese + English)
   - Use auto-detection: check which directories actually exist
   - Add config override for edge cases
4. **Implement in `~/AI/base`**
5. **Pull into project**: `git fetch base && git merge base/main`

## Common Patterns to Generalize

### Session directory path
Bad: `Path.home() / ".claude" / "projects" / "-Users-kweng-AI-Enpack-CCC"`
Good: Derive from project root — `~/.claude/projects/-{project_root.replace('/', '-')}`

### Directory name conventions
Support both Chinese (from Enpack-CCC) and English (from openclaw/new projects):

| Purpose | Chinese | English |
|---------|---------|---------|
| Specs | `规格/` | `spec/`, `specs/` |
| Source | `源代码/` | `src/` |
| Research | `研究/` | `research/` |
| Knowledge | `知识库/` | `knowledge/`, `docs/` |
| Tools | `工具/` | `tools/` |

### Entity numbering patterns
Support: `P##_name`, `R##_name`, `##_name` (plain number prefix)

## Checklist Before Committing

- [ ] Fix applied in `~/AI/base` (not just the project repo)
- [ ] Works with both Chinese and English directory names
- [ ] No hardcoded project paths remain
- [ ] Existing projects still work (backward compatible)
- [ ] New projects work out of the box (forward compatible)

## Tracking

When you fix an inefficiency, append it to the "Fixed Issues" section below so we build institutional memory.

### Fixed Issues

| Date | File | Issue | Fix |
|------|------|-------|-----|
| _(append here)_ | | | |
