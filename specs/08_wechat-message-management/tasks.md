# Tasks: WeChat Message Management & Filtering

## Phase 1: Audit & Planning
- [ ] Task 1.1 - Audit existing 538 conversations: breakdown by group/DM, message count, recency
- [ ] Task 1.2 - Identify top 30 conversations by message count (manual review)
- [ ] Task 1.3 - Identify dormant conversations (no messages in >1 year)
- [ ] Task 1.4 - Identify tiny conversations (<5 messages)
- [ ] Task 1.5 - Create initial `wechat-filter-policy.json` with default rules
- [ ] Task 1.6 - Document findings in `status.md`

## Phase 2: Build Filter Engine
- [ ] Task 2.1 - Implement `FilterPolicy` and `FilterRule` classes (`filters/wechat_filter.py`)
- [ ] Task 2.2 - Implement policy evaluation logic with priority-based matching
- [ ] Task 2.3 - Add unit tests for filter engine
- [ ] Task 2.4 - Integrate filter into `_run_extraction()` in `main.py`
- [ ] Task 2.5 - Add CLI flags: `--exclude-groups`, `--include-users`, `--since`, `--min-messages`, `--policy`
- [ ] Task 2.6 - Add `--tier` flag to extract only specific tiers

## Phase 3: Cleanup Existing Data
- [ ] Task 3.1 - Implement `wechat-manage audit` command
- [ ] Task 3.2 - Implement `wechat-manage apply-policy` command with `--dry-run` support
- [ ] Task 3.3 - Implement excluded data handling (move to `_excluded/` folder)
- [ ] Task 3.4 - Apply default policy with `--dry-run`, review output
- [ ] Task 3.5 - Execute cleanup: apply policy, move excluded conversations
- [ ] Task 3.6 - Verify: re-audit, confirm reduction in noise

## Phase 4: Policy Management
- [ ] Task 4.1 - Implement `wechat-manage add-rule` command
- [ ] Task 4.2 - Implement `wechat-manage stats` command (breakdown by tier)
- [ ] Task 4.3 - Add manual override support (per-conversation tier in policy)
- [ ] Task 4.4 - Version policy file (track changes)

## Phase 5: Integration
- [ ] Task 5.1 - Integrate filter with Spec 04 continuous sync pipeline
- [ ] Task 5.2 - Add tier metadata to `index.json` entries
- [ ] Task 5.3 - Spec 05 PKB: embed T1 only, keyword-search T1+T2, skip T3
- [ ] Task 5.4 - Re-extract with policy: clean re-extraction of filtered dataset
- [ ] Task 5.5 - Verify: search quality comparison (before vs after filtering)

## Phase 6 (Future): Message-Level Filtering
- [ ] Task 6.1 - Design per-message filter rules (skip media-only, system messages, forwarded content)
- [ ] Task 6.2 - Implement message-level filtering in extraction pipeline
- [ ] Task 6.3 - AI-powered message classification (relevant vs noise within a conversation)

## Notes

- Phase 1 can be done immediately using existing `index.json` data
- Phase 2-3 require code changes to `knowledge_harvester`
- Phase 4 is quality-of-life for ongoing management
- Phase 5 depends on Spec 04 and Spec 05 progress
- Phase 6 is future scope -- start with conversation-level filtering
- All cleanup is non-destructive: excluded data moves to `_excluded/`, never deleted
- Policy file should be version-controlled (not gitignored)
