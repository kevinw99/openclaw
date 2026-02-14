# OpenClaw Fork — Repo Guide

This is a fork of [openclaw/openclaw](https://github.com/openclaw/openclaw) with a personal customization layer on top.

## Git Remotes

| Remote | URL | Purpose |
|--------|-----|---------|
| `origin` | `kevinw99/openclaw` | Your fork — push your work here |
| `upstream` | `openclaw/openclaw` | Original project — pull updates from here |
| `base` | `kevinw99/ai-project-base` | Workflow template — pull workflow improvements |

## Repo Structure

The repo is upstream openclaw + your customization files layered on top:

```
~/AI/openclaw/
├── [upstream openclaw]
│   ├── src/                     # OpenClaw source code
│   ├── apps/                    # Native apps (macOS, iOS, Android)
│   ├── docs/                    # OpenClaw documentation
│   ├── extensions/              # Channel plugins
│   ├── skills/                  # OpenClaw skills
│   ├── packages/                # Workspace packages
│   ├── AGENTS.md / CLAUDE.md    # OpenClaw's own AI agent instructions
│   ├── README.md                # OpenClaw README
│   └── ...
│
├── [your customization layer]
│   ├── PROJECT_GUIDELINES.md    # Your workflow conventions
│   ├── REPO_GUIDE.md            # This file
│   ├── WORK_LOG.md              # Session work log
│   ├── requests-claw.txt        # Project requirements notes
│   ├── spec/                    # Your project specs
│   │   ├── README.md
│   │   └── 01_full-context-ai-assistant/
│   └── .claude/                 # Claude Code customizations
│       ├── commands/log.md
│       └── settings.json
```

**Key rule:** Don't modify `CLAUDE.md` / `AGENTS.md` — that's upstream's file and will cause merge conflicts. Keep your conventions in `PROJECT_GUIDELINES.md`.

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
