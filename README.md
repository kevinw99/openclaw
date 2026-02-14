# AI Project Base

Generic project template for AI-assisted development. Clone this to start any new project with a consistent workflow.

## What's Included

```
├── PROJECT_GUIDELINES.md        # Core principles, spec workflow, doc standards
├── WORK_LOG.md                  # Session-by-session work tracking
├── .claude/                     # Claude Code integration
│   ├── commands/log.md          # /log slash command
│   ├── skills/log.md            # Log update skill
│   └── settings.json            # Hooks (Stop → log reminder)
├── specs/                       # Spec-driven development
│   ├── README.md                # How to create specs
│   └── 00_template/             # Templates for new specs
│       ├── README.md
│       ├── requirements.md
│       ├── design.md
│       ├── tasks.md
│       └── status.md
├── docs/                        # Project documentation
├── research/                    # Research notes and findings
├── scripts/                     # Utility scripts
└── src/                         # Source code
```

## Usage

### Start a New Project

```bash
# Option A: GitHub template
gh repo create my-new-project --template kevinw99/ai-project-base --private

# Option B: Clone and re-point
git clone https://github.com/kevinw99/ai-project-base.git ~/AI/my-new-project
cd ~/AI/my-new-project
git remote rename origin base
git remote add origin git@github.com:kevinw99/my-new-project.git
git push -u origin main
```

### Pull Base Improvements Into an Existing Project

When the base template evolves, pull improvements into any project:

```bash
cd ~/AI/my-project

# First time: add base as a remote
git remote add base https://github.com/kevinw99/ai-project-base.git

# Pull updates
git fetch base
git merge base/main --allow-unrelated-histories  # only needed first time
git merge base/main                               # subsequent times
```

### Spec-Driven Development

All significant work follows the spec workflow:

1. Create a spec: `specs/##_descriptive-name/`
2. Add `requirements.md`, `design.md`, `tasks.md` (copy from `specs/00_template/`)
3. Implement according to spec
4. Add `status.md` when work begins, update as you go

### Session Workflow

1. Work on your project
2. At session end, run `/log` to update `WORK_LOG.md`
3. The Stop hook will remind you if you forget

## Evolving the Base

When you discover a new generic pattern in any project:

1. Add it to this base repo
2. Commit and push
3. Pull into active projects via `git fetch base && git merge base/main`
