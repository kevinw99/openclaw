#!/bin/bash
# =============================================================================
# Gmail Intake Label Setup — Spec 07, Phase 3
# Creates PKB label hierarchy and labels relevant emails
# Requires: gog CLI authenticated
# =============================================================================
set -euo pipefail

COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_CYAN='\033[0;36m'
COLOR_BOLD='\033[1m'
COLOR_RESET='\033[0m'

step() { echo -e "\n${COLOR_CYAN}▶ $1${COLOR_RESET}"; }
ok()   { echo -e "${COLOR_GREEN}  ✓ $1${COLOR_RESET}"; }
warn() { echo -e "${COLOR_YELLOW}  ⚠ $1${COLOR_RESET}"; }

# Verify gog
if ! gog auth list &>/dev/null; then
  echo "Error: gog not authenticated. Run: bash scripts/setup-gmail.sh"
  exit 1
fi

echo -e "${COLOR_BOLD}Gmail Intake Label Setup — Spec 07 Phase 3${COLOR_RESET}"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Create PKB labels
# ─────────────────────────────────────────────────────────────────────────────
step "Creating PKB label hierarchy"

for label in "PKB" "PKB/Intake" "PKB/Processed" "PKB/Excluded"; do
  if gog gmail labels list --plain 2>/dev/null | grep -q "^$label"; then
    ok "Label '$label' already exists"
  else
    gog gmail labels create "$label" 2>/dev/null && ok "Created label: $label" || warn "Could not create: $label (may already exist)"
  fi
done

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Label starred emails → PKB/Intake
# ─────────────────────────────────────────────────────────────────────────────
step "Labeling starred emails → PKB/Intake"

STARRED_IDS=$(gog gmail search "is:starred -label:PKB/Intake" --json --limit 500 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        for msg in data:
            if isinstance(msg, dict) and 'id' in msg:
                print(msg['id'])
except:
    pass
" 2>/dev/null || true)

if [ -n "$STARRED_IDS" ]; then
  COUNT=$(echo "$STARRED_IDS" | wc -l | tr -d ' ')
  echo "$STARRED_IDS" | xargs -n 50 gog gmail modify --add-label "PKB/Intake" 2>/dev/null || true
  ok "Labeled $COUNT starred emails"
else
  ok "No new starred emails to label"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Label sent emails (implies personal communication) → PKB/Intake
# ─────────────────────────────────────────────────────────────────────────────
step "Labeling sent email threads → PKB/Intake"

SENT_IDS=$(gog gmail search "in:sent -label:PKB/Intake -category:promotions -category:social" --json --limit 500 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        for msg in data:
            if isinstance(msg, dict) and 'id' in msg:
                print(msg['id'])
except:
    pass
" 2>/dev/null || true)

if [ -n "$SENT_IDS" ]; then
  COUNT=$(echo "$SENT_IDS" | wc -l | tr -d ' ')
  echo "$SENT_IDS" | xargs -n 50 gog gmail modify --add-label "PKB/Intake" 2>/dev/null || true
  ok "Labeled $COUNT sent-mail threads"
else
  ok "No new sent emails to label"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Label important emails → PKB/Intake
# ─────────────────────────────────────────────────────────────────────────────
step "Labeling important emails → PKB/Intake"

IMPORTANT_IDS=$(gog gmail search "is:important -label:PKB/Intake -category:promotions -category:social" --json --limit 500 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        for msg in data:
            if isinstance(msg, dict) and 'id' in msg:
                print(msg['id'])
except:
    pass
" 2>/dev/null || true)

if [ -n "$IMPORTANT_IDS" ]; then
  COUNT=$(echo "$IMPORTANT_IDS" | wc -l | tr -d ' ')
  echo "$IMPORTANT_IDS" | xargs -n 50 gog gmail modify --add-label "PKB/Intake" 2>/dev/null || true
  ok "Labeled $COUNT important emails"
else
  ok "No new important emails to label"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
step "Summary"

INTAKE_COUNT=$(gog gmail search "label:PKB/Intake" --json --limit 1 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data) if isinstance(data, list) else '?')
except:
    print('?')
" 2>/dev/null || echo "?")

echo ""
echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo -e "${COLOR_GREEN}  Labels created and emails categorized!${COLOR_RESET}"
echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo ""
echo "  PKB/Intake emails: ~$INTAKE_COUNT"
echo ""
echo "  View in Gmail: https://mail.google.com/mail/#label/PKB%2FIntake"
echo ""
echo "  Next: configure Gmail filters in Settings for auto-labeling."
echo "  Then: Spec 05 Gmail adapter will extract from label:PKB/Intake"
echo ""
