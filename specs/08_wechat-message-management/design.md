# Design: WeChat Message Management & Filtering

## Approach

Two-layer filtering system:

1. **Conversation-level filtering** (Phase 1): Include/exclude entire conversations based on metadata (group/DM, contact, activity, message count)
2. **Message-level filtering** (Phase 2, future): Within included conversations, filter individual messages (e.g., skip media-only, forwarded articles, system messages)

All filtering is non-destructive: the source WeChat database is never modified. Filtering only affects which data flows into JSONL output and downstream PKB.

## Architecture

```
WeChat SQLite DB (encrypted, read-only)
        │
        ▼
┌─────────────────────────────┐
│  WeChat Adapter (existing)  │
│  adapters/wechat.py         │
│  - decrypt DB               │
│  - parse messages            │
│  - yield Conversation        │
└─────────┬───────────────────┘
          │
          ▼
┌─────────────────────────────┐
│  Filter Layer (NEW)         │
│  filters/wechat_filter.py   │
│  - load policy file         │
│  - evaluate rules           │
│  - assign tier (keep/       │
│    archive/exclude)         │
│  - skip excluded convos     │
└─────────┬───────────────────┘
          │
          ▼
┌─────────────────────────────┐
│  Storage (existing)         │
│  storage.py                 │
│  - write JSONL              │
│  - update index.json        │
│  - add tier to metadata     │
└─────────┬───────────────────┘
          │
          ▼
┌─────────────────────────────┐
│  PKB Pipeline (Spec 05)     │
│  - embed T1 (keep) only     │
│  - keyword search T1 + T2   │
│  - skip T3 (excluded)       │
└─────────────────────────────┘
```

## Filter Engine

### Core Classes

```python
# src/knowledge_harvester/filters/wechat_filter.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta

@dataclass
class FilterRule:
    name: str
    match: Dict[str, any]       # Matching criteria
    tier: str                    # "keep" | "archive" | "exclude"
    priority: int = 10          # Higher priority wins
    reason: str = ""            # Why this rule exists

@dataclass
class FilterPolicy:
    version: int = 1
    default_tier: str = "archive"
    rules: List[FilterRule] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "FilterPolicy": ...

    def evaluate(self, conversation_meta: dict) -> tuple[str, str]:
        """Returns (tier, matched_rule_name)"""
        matched_tier = self.default_tier
        matched_rule = "default"
        matched_priority = -1

        for rule in self.rules:
            if rule.priority > matched_priority and self._matches(rule, conversation_meta):
                matched_tier = rule.tier
                matched_rule = rule.name
                matched_priority = rule.priority

        return matched_tier, matched_rule

    def _matches(self, rule: FilterRule, meta: dict) -> bool:
        match = rule.match
        # Check each criterion
        if "is_group" in match and meta.get("is_group") != match["is_group"]:
            return False
        if "username" in match and meta.get("username") not in match["username"]:
            return False
        if "title_contains" in match:
            title = meta.get("title", "")
            if not any(kw in title for kw in match["title_contains"]):
                return False
        if "min_messages" in match and meta.get("message_count", 0) < match["min_messages"]:
            return False
        if "active_within_days" in match:
            last = meta.get("last_message_time", "")
            if last:
                cutoff = datetime.utcnow() - timedelta(days=match["active_within_days"])
                if datetime.fromisoformat(last.replace("Z", "+00:00")) < cutoff:
                    return False
        if "dormant_days" in match:
            last = meta.get("last_message_time", "")
            if last:
                cutoff = datetime.utcnow() - timedelta(days=match["dormant_days"])
                if datetime.fromisoformat(last.replace("Z", "+00:00")) >= cutoff:
                    return False
        return True
```

### CLI Flag Integration

Modify `_run_extraction()` in `main.py` to accept filter options:

```python
def cmd_extract_wechat(args):
    # Build filter from CLI flags
    cli_rules = []
    if args.exclude_groups:
        cli_rules.append(FilterRule(
            name="cli-exclude-groups",
            match={"is_group": True},
            tier="exclude",
            priority=50
        ))
    if args.include_users:
        usernames = [u.strip() for u in args.include_users.split(",")]
        cli_rules.append(FilterRule(
            name="cli-include-users",
            match={"username": usernames},
            tier="keep",
            priority=100
        ))
    if args.since:
        # Filter conversations with no messages after --since date
        # Implemented via date check in evaluate()
        pass
    if args.min_messages:
        cli_rules.append(FilterRule(
            name="cli-min-messages",
            match={"min_messages": int(args.min_messages)},
            tier="exclude",  # Exclude conversations below threshold
            priority=30
        ))

    # Load policy file if specified
    policy = FilterPolicy.load(args.policy) if args.policy else FilterPolicy()
    policy.rules.extend(cli_rules)

    adapter = WeChatAdapter(db_key=db_key)
    _run_extraction(storage, adapter, "wechat", filter_policy=policy)
```

### Modified Extraction Flow

```python
def _run_extraction(storage, adapter, platform, source="", filter_policy=None):
    for conversation in adapter.extract(source):
        # Apply filter if policy provided
        if filter_policy:
            meta = {
                "is_group": conversation.metadata.get("is_group", False),
                "username": conversation.metadata.get("username", ""),
                "title": conversation.title,
                "message_count": len(conversation.messages),
                "last_message_time": conversation.messages[-1].timestamp if conversation.messages else "",
            }
            tier, rule = filter_policy.evaluate(meta)
            conversation.metadata["tier"] = tier
            conversation.metadata["filter_rule"] = rule

            if tier == "exclude":
                log.info(f"Excluding: {conversation.title} (rule: {rule})")
                continue

        storage.save_conversation(conversation)
```

## Part A: Cleanup Existing Data

### Audit Command

```bash
$ python3 -m knowledge_harvester wechat-manage audit

WeChat Conversation Audit
=========================
Total conversations: 538
  DM conversations:  312 (58%)
  Group chats:       226 (42%)

By message count:
  >1000 messages:     23 conversations
  100-1000:           87 conversations
  50-99:              64 conversations
  10-49:             142 conversations
  <10:               222 conversations

By recency:
  Active (last 6mo):  156 conversations
  Recent (6mo-2y):    198 conversations
  Dormant (>2y):      184 conversations

Top 20 by message count:
  1. 家人群 (group)           12,847 messages  [active]
  2. 张三 (DM)                 8,234 messages  [active]
  ...
```

### Cleanup Workflow

```bash
# Step 1: Audit
python3 -m knowledge_harvester wechat-manage audit > wechat-audit.txt

# Step 2: Apply default policy (conservative)
python3 -m knowledge_harvester wechat-manage apply-policy \
  --policy wechat-filter-policy.json \
  --dry-run   # Preview what would be excluded

# Step 3: Execute cleanup
python3 -m knowledge_harvester wechat-manage apply-policy \
  --policy wechat-filter-policy.json

# Step 4: Verify
python3 -m knowledge_harvester wechat-manage stats
```

### Excluded Data Handling

Excluded conversations are **moved, not deleted**:

```
知识库/conversations/wechat/
├── wechat-xxx.jsonl          # T1/T2 (kept)
├── index.json                # Updated: only T1/T2
├── state.json
└── _excluded/                # T3 (moved here)
    ├── wechat-yyy.jsonl
    └── index.json            # Excluded conversation metadata
```

## Part B: Ongoing Filtering

### Integration with Spec 04 (Continuous Sync)

The continuous sync pipeline should apply the filter policy to new messages:

```python
# In sync pipeline
policy = FilterPolicy.load("wechat-filter-policy.json")

for new_conversation in sync_new_messages():
    meta = build_meta(new_conversation)
    tier, rule = policy.evaluate(meta)

    if tier == "exclude":
        log.debug(f"Skipping excluded conversation: {new_conversation.title}")
        continue

    # New conversation not in policy → prompt for classification
    if tier == policy.default_tier and rule == "default":
        log.info(f"New conversation needs classification: {new_conversation.title}")
        # Add to "needs-review" queue
```

### Policy Maintenance

```bash
# Add a contact to keep list
python3 -m knowledge_harvester wechat-manage add-rule \
  --name "keep-zhangsan" \
  --match '{"username": ["wxid_zhangsan"]}' \
  --tier keep

# Exclude a noisy group
python3 -m knowledge_harvester wechat-manage add-rule \
  --name "exclude-spam-group" \
  --match '{"title_contains": ["广告群"]}' \
  --tier exclude

# Re-evaluate after policy change
python3 -m knowledge_harvester wechat-manage apply-policy \
  --policy wechat-filter-policy.json
```

## Default Policy Template

```json
{
  "version": 1,
  "default_tier": "archive",
  "rules": [
    {
      "name": "exclude-tiny-conversations",
      "match": { "min_messages": 5 },
      "tier": "exclude",
      "priority": 5,
      "reason": "Conversations with <5 messages are usually noise"
    },
    {
      "name": "exclude-dormant-groups",
      "match": { "is_group": true, "dormant_days": 365 },
      "tier": "exclude",
      "priority": 10,
      "reason": "Group chats inactive for >1 year"
    },
    {
      "name": "exclude-low-activity-groups",
      "match": { "is_group": true, "min_messages": 20 },
      "tier": "exclude",
      "priority": 8,
      "reason": "Group chats with <20 messages are usually dead"
    },
    {
      "name": "keep-active-dms",
      "match": { "is_group": false, "min_messages": 50, "active_within_days": 365 },
      "tier": "keep",
      "priority": 20,
      "reason": "Active personal conversations with substance"
    },
    {
      "name": "keep-active-groups",
      "match": { "is_group": true, "min_messages": 200, "active_within_days": 180 },
      "tier": "keep",
      "priority": 20,
      "reason": "High-activity groups I participate in"
    }
  ]
}
```

## Key Decisions

- **Conversation-level first**: Start with include/exclude entire conversations, not per-message filtering
- **Non-destructive**: Excluded data moved to `_excluded/` folder, never deleted
- **Policy file**: JSON-based rules, not hardcoded -- easy to iterate and version control
- **Default = archive**: Unknown conversations default to `archive` (extract but don't embed)
- **Priority-based rules**: Higher priority rules override lower ones; manual overrides always win

## Alternative Approaches

- **AI classification**: Use LLM to classify each conversation by relevance. More accurate but expensive for 538 conversations. Consider for Phase 2.
- **Per-message filtering**: Filter individual messages within conversations (skip media, system messages). More granular but complex. Defer to Phase 2.
- **Interactive TUI**: Build a terminal UI for conversation triage. Nice UX but overkill for initial version.

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Accidentally exclude important conversations | Non-destructive: moved to `_excluded/`, recoverable |
| Policy too aggressive | Start conservative (default = archive). Review `--dry-run` output. |
| Policy too loose | Iterate: audit → adjust rules → re-apply. Policy is versioned. |
| Contact names change | Match on `username` (stable WeChat ID), not display name |
| New conversations not classified | Default tier catches them; periodic review queue |
