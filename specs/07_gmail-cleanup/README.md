# Spec 07: Gmail Cleanup & Intake Pipeline

> One-time Gmail cleanup (unsubscribe, delete promotions, archive) + ongoing intake pipeline that labels relevant emails for PKB extraction.

## Quick Links
- [Requirements](./requirements.md)
- [Design](./design.md)
- [Tasks](./tasks.md)

## Status: Planning

## Summary

Before extracting Gmail into the Personal Knowledge Base (Spec 05), the inbox needs cleanup. Years of accumulated promotional emails, newsletters, and irrelevant notifications would pollute the PKB with noise. This spec defines a two-phase approach: (1) one-time bulk cleanup using existing tools, and (2) an ongoing intake pipeline that labels relevant emails into a dedicated folder for automated PKB extraction.

## Problem Statement

1. **Noisy inbox** -- Years of promotional emails, newsletters, and notification spam would overwhelm the PKB if extracted as-is
2. **No intake process** -- No systematic way to identify which emails contain personal knowledge worth preserving
3. **Manual unsubscribe burden** -- Hundreds of newsletter/promotional subscriptions need bulk unsubscribe
4. **No automation** -- No cron/scheduled cleanup to keep the inbox manageable over time
5. **Extraction dependency** -- Spec 05 Gmail adapter needs clean, labeled data to produce a useful knowledge base

## Current State

| Aspect | Status |
|--------|--------|
| Gmail extraction adapter | Not built (Spec 05 scope) |
| `gog` CLI installed | Yes (OpenClaw dependency) |
| OAuth2 credentials | May need setup via `gog` |
| Inbox size (est.) | Unknown -- needs audit |
| Promotions/newsletters | Many -- never cleaned up |
| Relevant personal emails | Mixed in with noise |

## Relationship to Other Specs

- **Spec 05** (PKB): Gmail adapter consumes the clean, labeled output of this spec
- **Spec 06** (Backup): Cleaned Gmail data will be backed up as part of PKB
- **Spec 08** (WeChat Management): Parallel effort applying similar filtering to WeChat
