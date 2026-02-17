# OpenClaw Fork — Repo Guide

This is a fork of [openclaw/openclaw](https://github.com/openclaw/openclaw) with a personal customization layer on top.

## Git Remotes

| Remote | URL | Purpose |
|--------|-----|---------|
| `origin` | `kevinw99/openclaw` | Your fork — push your work here |
| `upstream` | `openclaw/openclaw` | Original project — pull updates from here |
| `base` | `kevinw99/ai-project-base` | Workflow template — pull workflow improvements |

## Repo Structure

All files live flat at the root. Upstream openclaw files and your customizations coexist side-by-side — there are no wrapper subdirectories.

```
~/AI/openclaw/
│
│  ── Upstream openclaw files ──
├── src/                         # OpenClaw source code
├── apps/                        # Native apps (macOS, iOS, Android)
├── docs/                        # OpenClaw documentation
├── extensions/                  # Channel plugins
├── skills/                      # OpenClaw skills
├── packages/                    # Workspace packages
├── AGENTS.md / CLAUDE.md        # OpenClaw's own AI agent instructions
├── README.md                    # OpenClaw README
├── package.json                 # OpenClaw package config
├── ...                          # (other upstream files)
│
│  ── From base (edit in ~/AI/base, pull here) ──
├── PROJECT_GUIDELINES.md        # Workflow conventions
├── WORK_LOG.md                  # Session work log template
├── specs/00_template/           # Spec templates
├── specs/README.md              # Spec index
├── src/session_history/         # Session history tool
├── .claude/commands/log.md      # /log command
├── .claude/commands/history.md  # /history command
├── .claude/skills/log.md        # Log skill
├── .claude/skills/history.md    # History skill
├── .claude/settings.json        # Hooks config
├── .gitignore                   # Ignore rules
│
│  ── Project-specific (edit here) ──
├── REPO_GUIDE.md                # This file
├── requests-claw.txt            # Project requirements notes
└── spec/                        # Your project specs
    ├── README.md
    └── 01_full-context-ai-assistant/
```

Your files don't exist in upstream, so `git merge upstream/main` won't touch them.

## Where to Make Changes

This repo has three layers. **Always edit in the layer that owns the code.**

| Layer | Source remote | What it contains | Edit where? |
|-------|-------------|------------------|-------------|
| **Upstream** | `upstream` (openclaw/openclaw) | OpenClaw source code (`src/`, `apps/`, `docs/`, `CLAUDE.md`, etc.) | In this repo if you're modifying openclaw. Push to `origin`. |
| **Base** | `base` (ai-project-base) | Generic workflow tools and templates (`PROJECT_GUIDELINES.md`, `specs/00_template/`, `.claude/commands/`, `.claude/skills/`, `src/session_history/`) | **In `~/AI/base`, not here.** Then pull via `git fetch base && git merge base/main`. |
| **Project** | `origin` (this fork) | Project-specific files (`REPO_GUIDE.md`, `WORK_LOG.md`, `spec/01_*`, `requests-claw.txt`) | In this repo. Push to `origin`. |

**Key rules:**
- **Don't modify base-owned files here.** If you need to fix `PROJECT_GUIDELINES.md`, `src/session_history/`, `.claude/skills/log.md`, or spec templates — do it in `~/AI/base` and pull the change into this repo. This keeps all projects in sync.
- **Don't modify `CLAUDE.md` / `AGENTS.md`** — that's upstream's file and will cause merge conflicts. Keep your conventions in `PROJECT_GUIDELINES.md`.

## Common Operations

### Pull upstream openclaw updates

```bash
git fetch upstream
git merge upstream/main
# your customization files won't conflict (they don't exist upstream)
git push origin main
```

### Pull workflow improvements from base template

```bash
git fetch base
git merge base/main --allow-unrelated-histories  # first time only
git merge base/main                               # subsequent times
```

### Push your changes

```bash
git push origin main
```

### Check remote status

```bash
git remote -v
git log --oneline origin/main..upstream/main  # see what's new upstream
```

## Build / Test / Dev

See upstream's `CLAUDE.md` for full build commands. Quick reference:

```bash
pnpm install          # install deps
pnpm build            # type-check + build
pnpm test             # run tests
pnpm lint             # lint
pnpm dev              # run CLI in dev mode
```

Requires Node 22+.
