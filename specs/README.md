# Project Specifications

**Purpose**: Detailed technical specifications and implementation tracking.

---

## How to Create a New Spec

1. Determine the next available number (check existing specs)
2. Create directory: `##_descriptive-name/` (e.g., `06_user-authentication`)
3. Copy template files from `specs/00_template/`:
   - `README.md` - Overview and navigation
   - `requirements.md` - What needs to be done
   - `design.md` - How it will be done
   - `tasks.md` - Breakdown of work items
4. Add `status.md` when implementation begins

## Naming Convention

- Format: `##_descriptive-name`
- Use two-digit zero-padded numbers (01, 02, ... 10, 11)
- Separate number from name with underscore
- Use kebab-case for descriptive names

## Current Specs

| # | Name | Status | Description |
|---|------|--------|-------------|
| 01 | [full-context-ai-assistant](./01_full-context-ai-assistant/) | Planning | Full context AI personal assistant |
| 02 | [wechat-channel](./02_wechat-channel/) | BLOCKED | WeChat channel extension (PadLocal is dead) |
| 03 | [personal-knowledge-extraction](./03_personal-knowledge-extraction/) | Complete | Multi-platform knowledge harvester |
| 04 | [wechat-continuous-sync](./04_wechat-continuous-sync/) | Planning | Continuous WeChat message capture |
| 05 | [personal-knowledge-base](./05_personal-knowledge-base/) | Draft | Unified PKB from WeChat/ChatGPT/Gmail/etc. |

---

## Template Location

See [`specs/00_template/`](./00_template/) for spec templates.
