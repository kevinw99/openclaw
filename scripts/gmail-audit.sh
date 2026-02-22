#!/bin/bash
# =============================================================================
# Gmail Inbox Audit — Spec 07, Phase 1
# Counts emails by category, age, and top senders
# Requires: gog CLI authenticated (run setup-gmail.sh first)
# =============================================================================
set -euo pipefail

COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_CYAN='\033[0;36m'
COLOR_BOLD='\033[1m'
COLOR_RESET='\033[0m'

REPORT_DIR="$(cd "$(dirname "$0")/.." && pwd)/specs/07_gmail-cleanup"
REPORT_FILE="$REPORT_DIR/status.md"

header() { echo -e "\n${COLOR_BOLD}${COLOR_CYAN}$1${COLOR_RESET}"; }
info()   { echo -e "  $1"; }

# Verify gog is working
if ! gog auth list &>/dev/null; then
  echo "Error: gog not authenticated. Run: bash scripts/setup-gmail.sh"
  exit 1
fi

ACCOUNT=$(gog auth list --plain 2>/dev/null | head -1 | awk '{print $1}' || echo "unknown")
echo -e "${COLOR_BOLD}Gmail Inbox Audit${COLOR_RESET}"
echo "Account: $ACCOUNT"
echo "Date: $(date '+%Y-%m-%d %H:%M')"

# Helper: count emails matching a query
count_emails() {
  local query="$1"
  local result
  result=$(gog gmail search "$query" --json --fields "resultSizeEstimate" 2>/dev/null || echo "[]")
  # Try to get count from result
  local count
  count=$(echo "$result" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        print(len(data))
    elif isinstance(data, dict) and 'resultSizeEstimate' in data:
        print(data['resultSizeEstimate'])
    else:
        print(len(data) if isinstance(data, list) else 0)
except:
    print('?')
" 2>/dev/null || echo "?")
  echo "$count"
}

# Helper: count using gog gmail list (may be more accurate)
count_query() {
  local query="$1"
  local count
  # Use gog gmail list with query, count results
  count=$(gog gmail list --query "$query" --json --limit 1 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, dict) and 'resultSizeEstimate' in data:
        print(data['resultSizeEstimate'])
    elif isinstance(data, list):
        print(len(data))
    else:
        print('?')
except:
    print('?')
" 2>/dev/null || echo "?")
  echo "$count"
}

# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Email count by category
# ─────────────────────────────────────────────────────────────────────────────
header "1. Emails by Category"

for category in promotions social updates forums primary; do
  count=$(count_emails "category:$category")
  printf "  %-15s %s\n" "$category" "$count"
done

TOTAL_INBOX=$(count_emails "in:inbox")
TOTAL_ALL=$(count_emails "in:anywhere")
TOTAL_SPAM=$(count_emails "in:spam")
TOTAL_TRASH=$(count_emails "in:trash")
TOTAL_UNREAD=$(count_emails "is:unread")

echo ""
printf "  %-15s %s\n" "inbox" "$TOTAL_INBOX"
printf "  %-15s %s\n" "all mail" "$TOTAL_ALL"
printf "  %-15s %s\n" "spam" "$TOTAL_SPAM"
printf "  %-15s %s\n" "trash" "$TOTAL_TRASH"
printf "  %-15s %s\n" "unread" "$TOTAL_UNREAD"

# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Email count by age
# ─────────────────────────────────────────────────────────────────────────────
header "2. Emails by Age"

for age in 7d 30d 90d 1y 2y 5y; do
  count=$(count_emails "newer_than:$age")
  printf "  %-20s %s\n" "Last $age" "$count"
done

OLD_2Y=$(count_emails "older_than:2y")
OLD_5Y=$(count_emails "older_than:5y")
printf "  %-20s %s\n" "Older than 2y" "$OLD_2Y"
printf "  %-20s %s\n" "Older than 5y" "$OLD_5Y"

# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Top senders (promotions)
# ─────────────────────────────────────────────────────────────────────────────
header "3. Top Senders in Promotions (sample)"

# Get a sample of recent promotion emails and extract senders
PROMO_SENDERS=$(gog gmail search "category:promotions" --json --limit 200 2>/dev/null | python3 -c "
import sys, json
from collections import Counter

try:
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        data = [data]

    senders = []
    for msg in data:
        # Try different field locations
        frm = ''
        if isinstance(msg, dict):
            frm = msg.get('from', msg.get('From', ''))
            if not frm:
                headers = msg.get('payload', {}).get('headers', [])
                for h in headers:
                    if h.get('name', '').lower() == 'from':
                        frm = h.get('value', '')
                        break
        if frm:
            # Extract just the domain or email
            import re
            match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', frm)
            if match:
                senders.append(match.group())
            else:
                senders.append(frm[:60])

    counts = Counter(senders)
    for sender, count in counts.most_common(30):
        print(f'  {count:>4}  {sender}')
except Exception as e:
    print(f'  (could not parse: {e})')
" 2>/dev/null || echo "  (could not retrieve)")

echo "$PROMO_SENDERS"

# ─────────────────────────────────────────────────────────────────────────────
# Section 4: Top senders overall
# ─────────────────────────────────────────────────────────────────────────────
header "4. Top Senders Overall (sample from inbox)"

INBOX_SENDERS=$(gog gmail search "in:inbox" --json --limit 200 2>/dev/null | python3 -c "
import sys, json
from collections import Counter

try:
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        data = [data]

    senders = []
    for msg in data:
        frm = ''
        if isinstance(msg, dict):
            frm = msg.get('from', msg.get('From', ''))
            if not frm:
                headers = msg.get('payload', {}).get('headers', [])
                for h in headers:
                    if h.get('name', '').lower() == 'from':
                        frm = h.get('value', '')
                        break
        if frm:
            import re
            match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', frm)
            if match:
                senders.append(match.group())
            else:
                senders.append(frm[:60])

    counts = Counter(senders)
    for sender, count in counts.most_common(20):
        print(f'  {count:>4}  {sender}')
except Exception as e:
    print(f'  (could not parse: {e})')
" 2>/dev/null || echo "  (could not retrieve)")

echo "$INBOX_SENDERS"

# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Labels
# ─────────────────────────────────────────────────────────────────────────────
header "5. Existing Labels"

gog gmail labels list --plain 2>/dev/null | head -30 || echo "  (could not list labels)"

# ─────────────────────────────────────────────────────────────────────────────
# Write report
# ─────────────────────────────────────────────────────────────────────────────
header "Writing report to $REPORT_FILE"

cat > "$REPORT_FILE" << REPORT_EOF
# Status: Gmail Cleanup & Intake Pipeline

## Audit Results ($(date '+%Y-%m-%d'))

Account: $ACCOUNT

### Emails by Category
| Category | Count |
|----------|-------|
| Promotions | $(count_emails "category:promotions") |
| Social | $(count_emails "category:social") |
| Updates | $(count_emails "category:updates") |
| Forums | $(count_emails "category:forums") |
| Primary | $(count_emails "category:primary") |
| **Total (inbox)** | **$TOTAL_INBOX** |
| Total (all mail) | $TOTAL_ALL |
| Spam | $TOTAL_SPAM |
| Unread | $TOTAL_UNREAD |

### Emails by Age
| Period | Count |
|--------|-------|
| Last 7 days | $(count_emails "newer_than:7d") |
| Last 30 days | $(count_emails "newer_than:30d") |
| Last 90 days | $(count_emails "newer_than:90d") |
| Last 1 year | $(count_emails "newer_than:1y") |
| Last 2 years | $(count_emails "newer_than:2y") |
| Older than 2 years | $OLD_2Y |
| Older than 5 years | $OLD_5Y |

### Phase Progress
- [x] Phase 1: Audit (this report)
- [ ] Phase 2: Bulk cleanup (promotions, social, unsubscribe)
- [ ] Phase 3: Intake labeling (PKB/Intake, PKB/Processed)
- [ ] Phase 4: Ongoing automation (Apps Script, cron)
REPORT_EOF

echo -e "${COLOR_GREEN}  Report saved to: $REPORT_FILE${COLOR_RESET}"
echo ""
echo "Next steps:"
echo "  1. Review the audit numbers above"
echo "  2. Run: bash scripts/gmail-cleanup.sh          # Phase 2: bulk cleanup"
echo "  3. Run: bash scripts/gmail-intake-labels.sh    # Phase 3: create labels"
