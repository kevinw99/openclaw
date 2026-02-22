# Requirements: WeChat Message Management & Filtering

## Overview

Add filtering and organization to WeChat message extraction, covering both retroactive cleanup of existing data and ongoing filtering for new messages. Ensure only relevant conversations enter the Personal Knowledge Base.

## Objectives

- Clean up existing 538-conversation extraction: categorize, tag, and prune irrelevant data
- Add extraction-time filters to `extract-wechat` command (groups, contacts, dates, message count)
- Define and maintain a relevance policy for WeChat conversations
- Enable ongoing automatic filtering for continuous sync (Spec 04)
- Improve PKB search quality by reducing noise

## Scope

### In scope

**Part A: Cleanup existing WeChat history**

- Audit current extraction: breakdown by group/DM, message count, active/dormant
- Define relevance tiers (Keep / Archive / Exclude)
- Categorize existing 538 conversations into tiers
- Remove or archive excluded conversations from JSONL storage
- Update `index.json` to reflect filtered state

**Part B: Ongoing filtering & organization**

- Add CLI flags to `extract-wechat`: `--exclude-groups`, `--include-users`, `--since`, `--min-messages`
- Create a filter policy file (`wechat-filter-policy.json`) for reusable rules
- Tag/categorize conversations in `index.json` metadata
- Integrate with continuous sync (Spec 04) to auto-filter new messages
- Provide a `wechat-manage` CLI command for ongoing maintenance

### Out of scope

- Modifying WeChat app data (we only read from the local DB, never write back)
- Real-time message routing (that's Spec 02/04 territory)
- WeChat bot behavior (Spec 02)
- Building a WeChat client or UI

## Conversation Relevance Tiers

| Tier | Label | Action | Examples |
|------|-------|--------|----------|
| **T1: Keep** | `keep` | Extract, embed, search | Close friends, family, important work |
| **T2: Archive** | `archive` | Extract but don't embed | Acquaintances, old work groups, reference |
| **T3: Exclude** | `exclude` | Don't extract | Spam groups, bot notifications, dead groups |

### Classification Criteria

| Signal | T1 (Keep) | T2 (Archive) | T3 (Exclude) |
|--------|-----------|--------------|---------------|
| **Conversation type** | DM with known contacts | DM with acquaintances | Bot accounts, service accounts |
| **Group activity** | Active groups I participate in | Groups I lurk in | Dead groups, meme groups |
| **Message count** | >50 messages | 10-50 messages | <10 messages |
| **Recency** | Active in last 6 months | Active in last 2 years | Dormant >2 years |
| **My participation** | I sent messages | I occasionally reply | I never replied |
| **Content type** | Text conversations | Mixed text/media | Pure media forwarding |

## Filter Policy Schema

```json
{
  "version": 1,
  "default_tier": "archive",
  "rules": [
    {
      "name": "exclude-groups-by-default",
      "match": { "is_group": true },
      "tier": "exclude",
      "priority": 10
    },
    {
      "name": "keep-important-groups",
      "match": { "is_group": true, "title_contains": ["家人", "工作"] },
      "tier": "keep",
      "priority": 20
    },
    {
      "name": "keep-active-dms",
      "match": { "is_group": false, "min_messages": 50, "active_within_days": 180 },
      "tier": "keep",
      "priority": 20
    },
    {
      "name": "exclude-dormant",
      "match": { "dormant_days": 730 },
      "tier": "exclude",
      "priority": 5
    },
    {
      "name": "manual-keep",
      "match": { "username": ["wxid_friend1", "wxid_friend2"] },
      "tier": "keep",
      "priority": 100
    }
  ]
}
```

## CLI Interface

### New flags for `extract-wechat`

```bash
# Filter by conversation type
python3 -m knowledge_harvester extract-wechat --exclude-groups
python3 -m knowledge_harvester extract-wechat --groups-only

# Filter by contacts
python3 -m knowledge_harvester extract-wechat --include-users "wxid_xxx,wxid_yyy"
python3 -m knowledge_harvester extract-wechat --exclude-users "wxid_bot1,wxid_bot2"

# Filter by activity
python3 -m knowledge_harvester extract-wechat --since 2025-01-01
python3 -m knowledge_harvester extract-wechat --min-messages 50

# Use policy file
python3 -m knowledge_harvester extract-wechat --policy wechat-filter-policy.json

# Tier-based extraction
python3 -m knowledge_harvester extract-wechat --tier keep        # T1 only
python3 -m knowledge_harvester extract-wechat --tier keep,archive # T1 + T2
```

### New `wechat-manage` command

```bash
# Audit current state
python3 -m knowledge_harvester wechat-manage audit

# Categorize conversations interactively
python3 -m knowledge_harvester wechat-manage categorize --interactive

# Apply policy and clean up
python3 -m knowledge_harvester wechat-manage apply-policy --policy wechat-filter-policy.json

# Show stats by tier
python3 -m knowledge_harvester wechat-manage stats
```

## Success Criteria

- [ ] Existing 538 conversations audited and categorized by tier
- [ ] Excluded (T3) conversations removed from JSONL storage
- [ ] `extract-wechat` supports `--exclude-groups`, `--include-users`, `--since`, `--min-messages`
- [ ] Filter policy file (`wechat-filter-policy.json`) created and working
- [ ] `wechat-manage audit` command shows conversation breakdown
- [ ] Re-extraction with policy produces cleaner dataset
- [ ] Integration with Spec 04 continuous sync (filters applied to new messages)

## Constraints & Assumptions

- WeChat data is read-only (extracted from macOS SQLite DB, never written back)
- Filtering happens in our pipeline, not in WeChat app
- Group detection relies on `@chatroom` suffix in username
- Contact names may change over time (WeChat allows renaming)
- Some conversations have ambiguous relevance -- manual override via policy file

## Dependencies

- Spec 03 (Knowledge Extraction): WeChat adapter is the foundation
- Spec 04 (Continuous Sync): Ongoing filtering integrates with sync pipeline
- Spec 05 (PKB): Embedding pipeline should respect tier labels

## Questions & Clarifications

| Question | Answer |
|----------|--------|
| Should excluded conversations be deleted or moved? | Moved to `知识库/conversations/wechat/_excluded/` |
| Should we re-extract after filtering? | Yes, cleaner re-extraction recommended |
| How to handle borderline conversations? | Default to `archive` tier; manual override |
| Should filtering be destructive? | No -- original DB is untouched; only JSONL output is filtered |
| Per-message filtering (within a conversation)? | Phase 2 -- start with conversation-level only |
