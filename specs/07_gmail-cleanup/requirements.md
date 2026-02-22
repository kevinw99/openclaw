# Requirements: Gmail Cleanup & Intake Pipeline

## Overview

Clean up Gmail inbox before PKB extraction (Spec 05) and establish an ongoing pipeline that routes relevant emails to a labeled folder for automated knowledge base intake.

## Objectives

- Bulk unsubscribe from all newsletters and promotional email lists
- Delete or archive all promotional/social/notification emails
- Identify and label emails containing personal knowledge worth preserving
- Set up a dedicated Gmail label (`PKB/Intake`) for emails to be extracted
- Automate ongoing cleanup and intake via scheduled rules
- Prepare clean email data for Spec 05 Gmail adapter extraction

## Scope

### In scope

- **Phase 1: One-time cleanup** (using existing tools)
  - Audit inbox size, categories, top senders
  - Bulk unsubscribe from newsletters/promotions
  - Delete all promotional emails (category:promotions)
  - Delete all social notification emails (category:social)
  - Archive old irrelevant emails (>2 years, non-personal)
  - Identify and label relevant personal emails

- **Phase 2: Intake labeling**
  - Create Gmail label hierarchy: `PKB/Intake`, `PKB/Processed`, `PKB/Excluded`
  - Define intake criteria (what counts as "personal knowledge")
  - Label existing relevant emails into `PKB/Intake`
  - Set up Gmail filters for auto-labeling new incoming emails

- **Phase 3: Ongoing automation**
  - Scheduled cleanup (weekly/monthly) via Google Apps Script or cron + `gog`
  - Auto-archive promotions older than 7 days
  - Auto-label new personal emails into `PKB/Intake`
  - Periodic unsubscribe sweeps for new newsletter subscriptions

### Out of scope

- Building the Gmail extraction adapter (Spec 05)
- Email backup/archival (Spec 06)
- Sending or replying to emails
- Email client replacement

## Intake Criteria

Emails worth preserving in PKB:

| Include | Examples |
|---------|----------|
| Personal conversations | Friends, family, colleagues |
| Professional discussions | Work threads, project coordination |
| Important receipts/confirmations | Travel, financial, legal |
| Knowledge-sharing emails | Technical discussions, shared articles with commentary |
| Personal accounts/services | Account setup, important notifications |

| Exclude | Examples |
|---------|----------|
| Promotions/marketing | Sales, coupons, product announcements |
| Automated notifications | GitHub stars, CI/CD, social media alerts |
| Newsletters (bulk) | Unless specifically high-value |
| Spam/phishing | Already in spam folder |
| Transient alerts | Delivery notifications, OTPs, verification codes |

## Tool Evaluation

### Existing tools considered

| Tool | Stars | Use For | Decision |
|------|-------|---------|----------|
| **`gog` CLI** (gogcli) | 4.5K | Batch search, label, delete, trash | **Use** -- already installed |
| **Inbox Zero** (elie222/inbox-zero) | 10K | AI-powered bulk unsubscribe + categorize | **Evaluate** -- self-host for privacy |
| **gmail-ai-unsub** | 8 | AI-powered unsubscribe (Claude/Gemini) | **Evaluate** -- focused tool |
| **Gmail Cleaner GUI** | 1.7K | Visual bulk delete | **Skip** -- prefer CLI |
| **Google Apps Script** | N/A | Scheduled auto-cleanup | **Use** -- for ongoing automation |
| **Unroll.me / Cleanfox** | N/A | Bulk unsubscribe | **Reject** -- sells user data |

### Recommended approach

1. **`gog` CLI** for batch operations (already installed, scriptable, local)
2. **Google Apps Script** for scheduled automation (runs in Google, zero maintenance)
3. **Optional: Inbox Zero MCP** for Claude-assisted triage (if manual review needed)

## Success Criteria

- [ ] Inbox audited: know total emails, breakdown by category, top senders
- [ ] All newsletters/promotions unsubscribed (>90% reduction in incoming noise)
- [ ] Promotional/social emails deleted or archived
- [ ] `PKB/Intake` label created and populated with relevant emails
- [ ] Gmail filters set up for auto-labeling new relevant emails
- [ ] Scheduled cleanup running (weekly or monthly)
- [ ] Clean email set ready for Spec 05 extraction

## Constraints & Assumptions

- Gmail API rate limits: 15,000 quota units/user/min (messages.get = 5 units)
- `gog` CLI handles OAuth2 and rate limiting
- Google Apps Script free tier sufficient for scheduled tasks
- Privacy: no email content sent to third-party services (except LLM API for classification if needed)
- Inbox may have 10K-100K+ emails -- need batch processing with progress tracking

## Dependencies

- `gog` CLI installed and authenticated (OpenClaw dependency)
- Google Cloud project with Gmail API enabled (may share with Spec 05)
- Gmail account access

## Questions & Clarifications

| Question | Status |
|----------|--------|
| How many emails in inbox? | Need to audit |
| Any emails that must never be deleted? | Starred emails preserved |
| Preferred cleanup aggression level? | Aggressive (delete promos, keep personal) |
| Should we use AI classification? | Yes, for borderline cases. Use Claude via `gog` or Inbox Zero |
| Label hierarchy preference? | `PKB/Intake`, `PKB/Processed`, `PKB/Excluded` |
| Automation frequency? | Weekly cleanup, daily intake labeling |
