#!/bin/bash
# =============================================================================
# Gmail Bulk Cleanup — Spec 07, Phase 2
# Trashes promotions/social, archives old irrelevant emails
# Requires: gog CLI authenticated
# =============================================================================
set -euo pipefail

COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RED='\033[0;31m'
COLOR_CYAN='\033[0;36m'
COLOR_BOLD='\033[1m'
COLOR_RESET='\033[0m'

step()    { echo -e "\n${COLOR_CYAN}▶ $1${COLOR_RESET}"; }
ok()      { echo -e "${COLOR_GREEN}  ✓ $1${COLOR_RESET}"; }
warn()    { echo -e "${COLOR_YELLOW}  ⚠ $1${COLOR_RESET}"; }
confirm() {
  echo -e "${COLOR_YELLOW}  → $1 [y/N]${COLOR_RESET}"
  read -r response
  [[ "$response" =~ ^[Yy]$ ]]
}

DRY_RUN="${DRY_RUN:-false}"
BATCH_SIZE=100

if [ "$DRY_RUN" = "true" ]; then
  echo -e "${COLOR_YELLOW}DRY RUN MODE — no changes will be made${COLOR_RESET}"
fi

# Verify gog
if ! gog auth list &>/dev/null; then
  echo "Error: gog not authenticated. Run: bash scripts/setup-gmail.sh"
  exit 1
fi

# Helper: batch trash emails matching a query
batch_trash() {
  local query="$1"
  local description="$2"
  local count=0

  step "Trashing: $description"
  echo "  Query: $query"

  if [ "$DRY_RUN" = "true" ]; then
    local est
    est=$(gog gmail search "$query" --json --limit 1 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data) if isinstance(data, list) else '?')
except:
    print('?')
" 2>/dev/null || echo "?")
    warn "DRY RUN: Would trash ~$est emails"
    return
  fi

  # Process in batches
  while true; do
    local ids
    ids=$(gog gmail search "$query" --json --limit "$BATCH_SIZE" 2>/dev/null | python3 -c "
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

    if [ -z "$ids" ]; then
      break
    fi

    local batch_count
    batch_count=$(echo "$ids" | wc -l | tr -d ' ')
    count=$((count + batch_count))

    echo "$ids" | xargs -n 50 gog gmail trash 2>/dev/null || true

    echo "  Trashed $count so far..."

    # Small delay to respect rate limits
    sleep 1
  done

  ok "Trashed $count emails ($description)"
}

# Helper: batch archive emails matching a query
batch_archive() {
  local query="$1"
  local description="$2"
  local count=0

  step "Archiving: $description"
  echo "  Query: $query"

  if [ "$DRY_RUN" = "true" ]; then
    warn "DRY RUN: Would archive matching emails"
    return
  fi

  while true; do
    local ids
    ids=$(gog gmail search "$query" --json --limit "$BATCH_SIZE" 2>/dev/null | python3 -c "
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

    if [ -z "$ids" ]; then
      break
    fi

    local batch_count
    batch_count=$(echo "$ids" | wc -l | tr -d ' ')
    count=$((count + batch_count))

    echo "$ids" | xargs -n 50 gog gmail archive 2>/dev/null || true

    echo "  Archived $count so far..."
    sleep 1
  done

  ok "Archived $count emails ($description)"
}

echo -e "${COLOR_BOLD}Gmail Bulk Cleanup — Spec 07 Phase 2${COLOR_RESET}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Trash all promotions
# ─────────────────────────────────────────────────────────────────────────────
if confirm "Trash ALL promotional emails? (recoverable from trash for 30 days)"; then
  batch_trash "category:promotions -is:starred" "Promotional emails (not starred)"
else
  warn "Skipped promotions cleanup"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Trash all social
# ─────────────────────────────────────────────────────────────────────────────
if confirm "Trash ALL social notification emails?"; then
  batch_trash "category:social -is:starred" "Social notifications (not starred)"
else
  warn "Skipped social cleanup"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Archive old updates/forums
# ─────────────────────────────────────────────────────────────────────────────
if confirm "Archive updates & forums older than 1 year?"; then
  batch_archive "category:updates older_than:1y -is:starred" "Old update emails"
  batch_archive "category:forums older_than:1y -is:starred" "Old forum emails"
else
  warn "Skipped old updates/forums archive"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Archive old primary (>2 years, not important)
# ─────────────────────────────────────────────────────────────────────────────
if confirm "Archive primary emails older than 2 years (not starred/important)?"; then
  batch_archive "category:primary older_than:2y -is:starred -is:important" "Old primary emails"
else
  warn "Skipped old primary archive"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo -e "${COLOR_GREEN}  Cleanup complete!${COLOR_RESET}"
echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo ""
echo "  Trashed emails are recoverable for 30 days."
echo "  Review in Gmail: https://mail.google.com/mail/#trash"
echo ""
echo "  Next steps:"
echo "    bash scripts/gmail-audit.sh              # Re-audit to see improvement"
echo "    bash scripts/gmail-intake-labels.sh      # Set up PKB intake labels"
echo ""
