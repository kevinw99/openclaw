# Design: Gmail Cleanup & Intake Pipeline

## Approach

Three-phase approach leveraging existing tools (`gog` CLI + Google Apps Script) before building anything custom:

1. **Audit & Cleanup** -- Use `gog` to understand inbox state, then batch-delete/archive noise
2. **Label & Organize** -- Create PKB label hierarchy, classify existing emails, set up filters
3. **Automate** -- Google Apps Script for ongoing cleanup + `gog` cron for periodic sweeps

## Architecture

```
Phase 1: One-time Cleanup
┌─────────────────────────────────────────────────────┐
│  gog gmail search → audit (categories, senders)     │
│  gog gmail trash  → delete promotions/social        │
│  gmail-ai-unsub   → AI-powered bulk unsubscribe     │
│  gog gmail modify → archive old irrelevant emails   │
└─────────────────────────────────────────────────────┘

Phase 2: Intake Labeling
┌─────────────────────────────────────────────────────┐
│  Create labels: PKB/Intake, PKB/Processed, Excluded │
│  gog gmail search → find personal/relevant emails   │
│  gog gmail modify → label into PKB/Intake           │
│  Gmail UI filters → auto-label new incoming emails  │
└─────────────────────────────────────────────────────┘

Phase 3: Ongoing Automation
┌─────────────────────────────────────────────────────┐
│  Google Apps Script (runs in Google, zero infra)     │
│  ├── Daily: auto-label new personal emails          │
│  ├── Weekly: archive old promotions                 │
│  └── Monthly: unsubscribe sweep                     │
│                                                     │
│  cron + gog (local, for PKB sync)                   │
│  └── Weekly: export PKB/Intake → Spec 05 adapter    │
└─────────────────────────────────────────────────────┘
```

## Phase 1: One-time Cleanup (Manual + Scripted)

### Step 1.1: Audit

```bash
# Count emails by category
gog gmail search "category:promotions" --format json | jq length
gog gmail search "category:social" --format json | jq length
gog gmail search "category:updates" --format json | jq length
gog gmail search "category:forums" --format json | jq length
gog gmail search "category:primary" --format json | jq length

# Top senders (promotions)
gog gmail search "category:promotions" --format json \
  | jq -r '.[].from' | sort | uniq -c | sort -rn | head -30

# Old emails
gog gmail search "older_than:2y" --format json | jq length
gog gmail search "older_than:5y" --format json | jq length
```

### Step 1.2: Bulk Delete Promotions & Social

```bash
# Delete all promotional emails (moves to trash)
gog gmail search "category:promotions" --format json \
  | jq -r '.[].id' | xargs -n 100 gog gmail trash

# Delete all social notification emails
gog gmail search "category:social" --format json \
  | jq -r '.[].id' | xargs -n 100 gog gmail trash

# Empty trash after review
gog gmail trash empty
```

### Step 1.3: Unsubscribe

Two options (use both):

**Option A: `gog` + Gmail header-based**
```bash
# Find emails with List-Unsubscribe header
gog gmail search "list:* category:promotions" --format json \
  | jq -r '.[].id' | head -50
# Then use gog to process unsubscribe links
```

**Option B: `gmail-ai-unsub` (AI-powered)**
```bash
# Scan and label marketing emails
gmail-ai-unsub scan --provider claude

# Review in Gmail UI (labeled as "AI-Unsub/Marketing")
# Then process unsubscribes
gmail-ai-unsub unsubscribe --confirm
```

### Step 1.4: Archive Old Irrelevant Emails

```bash
# Archive emails older than 2 years that aren't starred or important
gog gmail search "older_than:2y -is:starred -is:important category:primary" \
  --format json | jq -r '.[].id' | xargs -n 100 gog gmail archive
```

## Phase 2: Intake Labeling

### Step 2.1: Create Label Hierarchy

```bash
gog gmail labels create "PKB"
gog gmail labels create "PKB/Intake"
gog gmail labels create "PKB/Processed"
gog gmail labels create "PKB/Excluded"
```

### Step 2.2: Define Intake Rules

Personal knowledge emails to label as `PKB/Intake`:

```bash
# Personal conversations (from known contacts)
gog gmail search "from:contact1@gmail.com OR from:contact2@gmail.com" \
  --format json | jq -r '.[].id' | xargs -n 100 gog gmail modify --add-label "PKB/Intake"

# Professional discussions (by domain)
gog gmail search "from:@company.com" \
  --format json | jq -r '.[].id' | xargs -n 100 gog gmail modify --add-label "PKB/Intake"

# Important threads (starred or replied-to)
gog gmail search "is:starred OR in:sent" \
  --format json | jq -r '.[].id' | xargs -n 100 gog gmail modify --add-label "PKB/Intake"
```

### Step 2.3: Gmail Filters (Auto-label New Emails)

Set up via Gmail Settings > Filters or `gog gmail filters create`:

| Filter | Action |
|--------|--------|
| `from:known-contacts` | Add label `PKB/Intake` |
| `category:promotions` | Skip inbox, no label |
| `category:social` | Skip inbox, no label |
| `from:@important-domain.com` | Add label `PKB/Intake` |
| `subject:receipt OR subject:confirmation` | Add label `PKB/Intake` |

## Phase 3: Ongoing Automation

### Google Apps Script (Deployed to Google)

```javascript
// auto_cleanup.gs -- runs on schedule via Apps Script triggers

function weeklyCleanup() {
  // Archive promotions older than 7 days
  const promos = GmailApp.search("category:promotions older_than:7d -is:starred");
  for (const thread of promos) {
    thread.moveToArchive();
  }

  // Archive social older than 3 days
  const social = GmailApp.search("category:social older_than:3d -is:starred");
  for (const thread of social) {
    thread.moveToArchive();
  }

  Logger.log(`Archived ${promos.length} promo + ${social.length} social threads`);
}

function dailyIntakeLabel() {
  // Label new personal emails from known contacts
  const knownContacts = ["contact1@gmail.com", "contact2@gmail.com"];
  const query = knownContacts.map(c => `from:${c}`).join(" OR ");
  const threads = GmailApp.search(`(${query}) -label:PKB/Intake newer_than:2d`);

  const intakeLabel = GmailApp.getUserLabelByName("PKB/Intake");
  for (const thread of threads) {
    thread.addLabel(intakeLabel);
  }

  Logger.log(`Labeled ${threads.length} threads for PKB intake`);
}

function monthlyUnsubscribeSweep() {
  // Find newsletters not yet unsubscribed
  const newsletters = GmailApp.search(
    "list:* category:promotions newer_than:30d -label:PKB/Excluded"
  );
  // Log for manual review (can't auto-unsubscribe via Apps Script)
  Logger.log(`Found ${newsletters.length} newsletter threads to review`);
}
```

### Cron Job (Local -- for PKB sync)

```bash
# scripts/sync-gmail-intake.sh
#!/bin/bash
# Weekly: export PKB/Intake emails for Spec 05 extraction
# Runs after cleanup, feeds into knowledge_harvester gmail adapter

gog gmail search "label:PKB/Intake -label:PKB/Processed" \
  --format json > /tmp/gmail-intake-pending.json

echo "$(jq length /tmp/gmail-intake-pending.json) emails pending PKB extraction"

# Mark as processed after extraction (Spec 05 adapter handles this)
```

## Integration with Spec 05 (PKB Gmail Adapter)

The Gmail adapter (Spec 05) should:
1. **Default extraction scope**: `label:PKB/Intake` (only pre-labeled emails)
2. **After extraction**: Move label from `PKB/Intake` → `PKB/Processed`
3. **Full extraction mode**: Optional `--all` flag to extract everything (bypass label filter)

```python
class GmailAdapter(BaseAdapter):
    platform = "gmail"

    def extract(self, source: str = "label:PKB/Intake") -> Iterator[Conversation]:
        # source = Gmail search query (default: PKB/Intake label)
        # Group by threadId → one Conversation per thread
        ...

    def mark_processed(self, thread_ids: List[str]):
        # Remove PKB/Intake, add PKB/Processed
        ...
```

## Key Decisions

- **`gog` CLI as primary tool**: Already installed, scriptable, handles OAuth2, data stays local
- **Google Apps Script for scheduling**: Zero infrastructure, runs in Google, free tier sufficient
- **Label-based intake**: `PKB/Intake` label as the bridge between Gmail and PKB extraction
- **No third-party cleanup services**: Unroll.me/Cleanfox sell data; use open-source tools only
- **AI classification optional**: For borderline emails, use Claude via Inbox Zero MCP or manual review

## Alternative Approaches

- **Inbox Zero (self-hosted)**: More powerful AI triage but requires Docker setup. Good if manual classification is too tedious.
- **Pure `gog` scripting**: No Apps Script, all via cron + `gog`. Simpler but requires machine to be on.
- **Gmail Takeout + local processing**: Export all, classify locally with Claude. More private but slower.

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Accidentally delete important emails | Always use `trash` (recoverable 30 days), never `delete`. Check starred/important first. |
| OAuth token expiry | `gog` handles refresh. Apps Script tokens are managed by Google. |
| Gmail API rate limits | `gog` has built-in rate limiting. Batch operations in chunks of 100. |
| Over-aggressive filtering | Start conservative (promotions/social only). Manual review before deleting primary. |
| Apps Script quota limits | Free tier: 5 min/execution, 90 min/day. More than sufficient for cleanup. |
