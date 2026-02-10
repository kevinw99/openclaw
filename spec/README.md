# Project Specifications

**Purpose**: Detailed technical specifications and implementation tracking

This is the primary location for project specifications. Alternative location: `.kiro/specs/`

---

## How to Create a New Spec

1. Determine the next available number (check existing specs)
2. Create directory: `##_descriptive-name/` (e.g., `01_user-authentication`)
3. Copy template files from `.kiro/specs/00_template/`:
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
| 01 | [full-context-ai-assistant](./01_full-context-ai-assistant/) | Planning | Full context AI personal assistant that knows the user deeply and collaborates across all activities |

---

## Template Location

See [`.kiro/specs/00_template/`](../.kiro/specs/00_template/) for spec templates.

---

**Last Updated**: 2026-02-01
