# Spec 08: WeChat Message Management & Filtering

> Clean up WeChat conversation history and establish filtering/organization for incoming messages to improve PKB signal quality.

## Quick Links
- [Requirements](./requirements.md)
- [Design](./design.md)
- [Tasks](./tasks.md)

## Status: Planning

## Summary

The WeChat knowledge base currently contains 538 conversations with 232K+ messages extracted indiscriminately. Many are noisy group chats, bot notifications, and irrelevant conversations that dilute the PKB. This spec defines: (A) one-time cleanup of existing WeChat extraction data, and (B) an ongoing filtering mechanism to organize new incoming messages by relevance.

Unlike Gmail (which has server-side labels and filters), WeChat messages are extracted from a local encrypted SQLite database -- filtering must happen at extraction time or post-extraction in our pipeline.

## Problem Statement

1. **No extraction filtering** -- All 538 conversations extracted without any relevance filtering
2. **Group chat noise** -- Many group chats are high-volume, low-signal (memes, forwarded articles, etc.)
3. **No categorization** -- No way to distinguish personal DMs from group chats from bot messages
4. **Growing dataset** -- Continuous sync (Spec 04) will keep adding unfiltered messages
5. **PKB quality** -- Noisy data degrades semantic search quality and wastes embedding compute

## Current State

| Aspect | Status |
|--------|--------|
| Total conversations | 538 |
| Total messages | 232K+ |
| Group chats | Unknown count (detected via `is_group` flag but not filtered) |
| DM conversations | Unknown count |
| Extraction filters | None (`extract-wechat` extracts everything) |
| Post-extraction cleanup | None |
| Message categorization | None |
| Metadata available | `is_group`, `username`, `title`, `message_count`, timestamps |

## Relationship to Other Specs

- **Spec 03** (Knowledge Extraction): WeChat adapter -- this spec adds filtering layer on top
- **Spec 04** (WeChat Continuous Sync): Ongoing sync -- this spec adds relevance filtering to the pipeline
- **Spec 05** (PKB): Consumes filtered WeChat data for embedding and search
- **Spec 07** (Gmail Cleanup): Parallel effort -- same intake/filtering philosophy applied to email
