# Tasks: Gmail Cleanup & Intake Pipeline

## Phase 1: Audit & Setup
- [ ] Task 1.1 - Verify `gog` CLI is authenticated and working (`gog gmail search "in:inbox" --limit 1`)
- [ ] Task 1.2 - Audit inbox: count emails by category (promotions, social, updates, forums, primary)
- [ ] Task 1.3 - Audit top 30 senders in promotions category
- [ ] Task 1.4 - Audit email volume by age (1y, 2y, 5y buckets)
- [ ] Task 1.5 - Document findings in `status.md`

## Phase 2: One-time Cleanup
- [ ] Task 2.1 - Bulk trash all `category:promotions` emails
- [ ] Task 2.2 - Bulk trash all `category:social` emails
- [ ] Task 2.3 - Run unsubscribe sweep (via `gmail-ai-unsub` or `gog` + List-Unsubscribe headers)
- [ ] Task 2.4 - Archive old irrelevant primary emails (>2y, not starred/important)
- [ ] Task 2.5 - Empty trash after manual review
- [ ] Task 2.6 - Verify: re-audit inbox, confirm noise reduction

## Phase 3: Intake Labeling
- [ ] Task 3.1 - Create Gmail labels: `PKB/Intake`, `PKB/Processed`, `PKB/Excluded`
- [ ] Task 3.2 - Define intake contact list (personal + professional contacts)
- [ ] Task 3.3 - Label existing personal emails into `PKB/Intake` (batch via `gog`)
- [ ] Task 3.4 - Label starred/important threads into `PKB/Intake`
- [ ] Task 3.5 - Label sent-mail threads into `PKB/Intake` (implies personal communication)
- [ ] Task 3.6 - Set up Gmail filters for auto-labeling new incoming emails
- [ ] Task 3.7 - Verify: spot-check labeled emails, adjust criteria

## Phase 4: Ongoing Automation
- [ ] Task 4.1 - Write Google Apps Script for weekly promo/social archive
- [ ] Task 4.2 - Write Google Apps Script for daily intake auto-labeling
- [ ] Task 4.3 - Deploy Apps Script with scheduled triggers
- [ ] Task 4.4 - Write `scripts/sync-gmail-intake.sh` for local cron
- [ ] Task 4.5 - Test end-to-end: new email → auto-label → cron detects → ready for Spec 05

## Phase 5: Spec 05 Integration
- [ ] Task 5.1 - Coordinate with Spec 05 Gmail adapter: extraction scoped to `label:PKB/Intake`
- [ ] Task 5.2 - Implement post-extraction label move (`PKB/Intake` → `PKB/Processed`)
- [ ] Task 5.3 - Verify full pipeline: email → label → extract → JSONL → search

## Notes

- Phase 2 is **one-time** and can be done manually with `gog` commands
- Phase 3 needs careful definition of "intake contacts" -- start with a small allowlist
- Phase 4 Apps Script runs for free in Google's infra, no local machine dependency
- Tasks 5.x depend on Spec 05 Gmail adapter being built
- Always use `trash` not `delete` during cleanup -- trash is recoverable for 30 days
- Preserve starred and important emails regardless of category
