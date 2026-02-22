# Status: WeChat Message Management & Filtering

**Last updated**: 2026-02-22

## Phase 1: Audit & Planning — COMPLETE

- [x] Task 1.1 - Audit existing 537 conversations: 151 groups, 386 DMs, 352K messages
- [x] Task 1.2 - Identified top 20 conversations by message count (top is 58K msgs tennis group)
- [x] Task 1.3 - Note: `last_message_time` not populated in current index — dormant detection deferred
- [x] Task 1.4 - Identified 44 tiny conversations (<5 messages)
- [x] Task 1.5 - Created `wechat-filter-policy.json` with 4 rules (message-count based)
- [x] Task 1.6 - Documented findings in this status.md

### Audit Findings
- 79% of messages are in group chats (278K of 352K)
- Top 3 groups alone have 130K messages (37% of total)
- 44 conversations had <5 messages (noise)
- 26 groups had <20 messages (dead)

## Phase 2: Build Filter Engine — COMPLETE

- [x] Task 2.1 - Implemented `FilterPolicy` and `FilterRule` in `filters/wechat_filter.py`
- [x] Task 2.2 - Priority-based rule matching with support for: is_group, username, title_contains, title_not_contains, min_messages, max_messages, active_within_days, dormant_days
- [x] Task 2.3 - Unit tests for filter engine (21 tests, all passing)
- [x] Task 2.4 - Integrated filter into `_run_extraction()` in `main.py`
- [x] Task 2.5 - Added CLI flags: `--exclude-groups`, `--include-users`, `--min-messages`, `--policy`
- [ ] Task 2.6 - Add `--tier` flag to extract only specific tiers (deferred)

## Phase 3: Cleanup Existing Data — COMPLETE

- [x] Task 3.1 - `wechat-manage audit` command working
- [x] Task 3.2 - `wechat-manage apply-policy` command with `--dry-run` support
- [x] Task 3.3 - Excluded data moved to `_excluded/` folder with its own `index.json`
- [x] Task 3.4 - Applied default policy with `--dry-run`, reviewed output
- [x] Task 3.5 - Executed cleanup: 62 excluded, 475 kept
- [x] Task 3.6 - Verified: re-audit confirmed 0 tiny, 0 dead groups

### Cleanup Results
| Tier    | Conversations | Messages   |
|---------|--------------|------------|
| Keep    | 196          | 343,642    |
| Archive | 279          | 8,234      |
| Exclude | 62           | 316        |
| **Total** | **537**    | **352,192** |

## Phase 4: Policy Management — COMPLETE

- [x] Task 4.1 - `wechat-manage add-rule` command
- [x] Task 4.2 - `wechat-manage stats` command (breakdown by tier)
- [ ] Task 4.3 - Manual override support (per-conversation tier) — deferred
- [ ] Task 4.4 - Version policy file (track changes) — deferred

## Phase 5: Integration — NOT STARTED

Depends on Spec 04 (continuous sync) and Spec 05 (PKB).

## Phase 6: Message-Level Filtering — NOT STARTED

Future scope.

## Known Limitations

1. **No `last_message_time`**: Current WeChat extraction doesn't populate this field, so time-based rules (active_within_days, dormant_days) don't work yet. Policy uses message-count rules only.
2. ~~No unit tests~~ — 21 unit tests now covering all match criteria and policy evaluation.
3. **No `--tier` flag**: Can't yet extract only specific tiers during re-extraction.

## Files Created/Modified

- `src/knowledge_harvester/filters/__init__.py` (new)
- `src/knowledge_harvester/filters/wechat_filter.py` (new) — Filter engine
- `src/knowledge_harvester/wechat_manage.py` (new) — Management commands
- `src/knowledge_harvester/main.py` (modified) — CLI integration
- `wechat-filter-policy.json` (new) — Default filter policy
- `tests/test_wechat_filter.py` (new) — 21 unit tests for filter engine
