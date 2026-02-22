#!/bin/bash
# =============================================================================
# Gmail Setup for OpenClaw Spec 07
# Automates: gcloud install, project creation, Gmail API enable, OAuth setup
# Manual steps: browser OAuth consent (2 times)
# =============================================================================
set -euo pipefail

COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RED='\033[0;31m'
COLOR_CYAN='\033[0;36m'
COLOR_RESET='\033[0m'

step() { echo -e "\n${COLOR_CYAN}▶ $1${COLOR_RESET}"; }
ok()   { echo -e "${COLOR_GREEN}  ✓ $1${COLOR_RESET}"; }
warn() { echo -e "${COLOR_YELLOW}  ⚠ $1${COLOR_RESET}"; }
fail() { echo -e "${COLOR_RED}  ✗ $1${COLOR_RESET}"; exit 1; }
ask()  { echo -e "${COLOR_YELLOW}  → $1${COLOR_RESET}"; }

PROJECT_ID="${GOG_PROJECT_ID:-openclaw-pkb}"
CREDENTIALS_DIR="$HOME/.openclaw/credentials/gmail"
CREDENTIALS_FILE="$CREDENTIALS_DIR/client_secret.json"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Ensure gcloud CLI
# ─────────────────────────────────────────────────────────────────────────────
step "Step 1: Check gcloud CLI"

GCLOUD=""
for p in \
  "$(which gcloud 2>/dev/null || true)" \
  /opt/homebrew/share/google-cloud-sdk/bin/gcloud \
  /usr/local/share/google-cloud-sdk/bin/gcloud \
  /opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/bin/gcloud \
  "$HOME/google-cloud-sdk/bin/gcloud"; do
  if [ -n "$p" ] && [ -x "$p" ]; then
    GCLOUD="$p"
    break
  fi
done

if [ -z "$GCLOUD" ]; then
  warn "gcloud not found. Installing via Homebrew..."
  brew install --cask google-cloud-sdk
  # After cask install, find it
  for p in \
    /opt/homebrew/share/google-cloud-sdk/bin/gcloud \
    /opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/bin/gcloud; do
    if [ -x "$p" ]; then
      GCLOUD="$p"
      break
    fi
  done
  if [ -z "$GCLOUD" ]; then
    fail "gcloud install failed"
  fi
fi

# Add gcloud to PATH for this session
export PATH="$(dirname "$GCLOUD"):$PATH"
ok "gcloud found: $GCLOUD ($(gcloud --version 2>&1 | head -1))"

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Ensure gcloud is authenticated
# ─────────────────────────────────────────────────────────────────────────────
step "Step 2: Check gcloud authentication"

ACTIVE_ACCOUNT=$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null || true)
if [ -z "$ACTIVE_ACCOUNT" ]; then
  ask "Opening browser for Google Cloud login..."
  gcloud auth login
  ACTIVE_ACCOUNT=$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null || true)
  if [ -z "$ACTIVE_ACCOUNT" ]; then
    fail "gcloud authentication failed"
  fi
fi
ok "Authenticated as: $ACTIVE_ACCOUNT"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Create or select GCP project
# ─────────────────────────────────────────────────────────────────────────────
step "Step 3: Set up GCP project '$PROJECT_ID'"

if gcloud projects describe "$PROJECT_ID" &>/dev/null; then
  ok "Project '$PROJECT_ID' already exists"
else
  warn "Creating project '$PROJECT_ID'..."
  gcloud projects create "$PROJECT_ID" --name="OpenClaw PKB" --set-as-default
  ok "Project created"
fi
gcloud config set project "$PROJECT_ID" --quiet
ok "Active project: $PROJECT_ID"

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Enable Gmail API
# ─────────────────────────────────────────────────────────────────────────────
step "Step 4: Enable Gmail API"

if gcloud services list --enabled --filter="name:gmail.googleapis.com" --format="value(name)" 2>/dev/null | grep -q gmail; then
  ok "Gmail API already enabled"
else
  gcloud services enable gmail.googleapis.com --quiet
  ok "Gmail API enabled"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Configure OAuth consent screen
# ─────────────────────────────────────────────────────────────────────────────
step "Step 5: Configure OAuth consent screen"
echo "  OAuth consent screen must be configured in the browser."
echo "  If not already done, the credential creation will prompt you."
echo ""
echo "  Quick setup (if needed):"
echo "    1. Go to: https://console.cloud.google.com/apis/credentials/consent?project=$PROJECT_ID"
echo "    2. User Type: External → Create"
echo "    3. App name: 'OpenClaw PKB', support email: $ACTIVE_ACCOUNT"
echo "    4. Scopes: Add 'Gmail API - .../gmail.modify'"
echo "    5. Test users: Add $ACTIVE_ACCOUNT"
echo "    6. Save"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Create OAuth client credentials
# ─────────────────────────────────────────────────────────────────────────────
step "Step 6: Create OAuth client credentials"

mkdir -p "$CREDENTIALS_DIR"

if [ -f "$CREDENTIALS_FILE" ]; then
  ok "Credentials file already exists: $CREDENTIALS_FILE"
else
  # Check if an OAuth client already exists
  EXISTING_CLIENT=$(gcloud auth application-default print-access-token &>/dev/null && \
    gcloud --format=json alpha iap oauth-clients list 2>/dev/null || true)

  # Create OAuth desktop client via gcloud
  # Note: gcloud doesn't directly create OAuth clients; we use the REST API
  warn "Creating OAuth Desktop client..."

  # Get access token
  ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null || true)
  if [ -z "$ACCESS_TOKEN" ]; then
    fail "Cannot get access token. Run: gcloud auth login"
  fi

  # Create OAuth client via API
  CREATE_RESULT=$(curl -s -X POST \
    "https://oauth2.googleapis.com/v1/projects/$PROJECT_ID/oauthClients" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "displayName": "OpenClaw PKB Desktop",
      "applicationType": "DESKTOP"
    }' 2>/dev/null || true)

  # The REST API approach may not work for all cases.
  # Fallback: guide user to download from console
  if echo "$CREATE_RESULT" | grep -q "clientId"; then
    CLIENT_ID=$(echo "$CREATE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['clientId'])" 2>/dev/null || true)
    CLIENT_SECRET=$(echo "$CREATE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['clientSecret'])" 2>/dev/null || true)

    if [ -n "$CLIENT_ID" ] && [ -n "$CLIENT_SECRET" ]; then
      cat > "$CREDENTIALS_FILE" <<CRED_EOF
{
  "installed": {
    "client_id": "$CLIENT_ID",
    "client_secret": "$CLIENT_SECRET",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost"]
  }
}
CRED_EOF
      ok "Credentials saved to: $CREDENTIALS_FILE"
    fi
  fi

  # If API approach didn't work, try gcloud CLI
  if [ ! -f "$CREDENTIALS_FILE" ] || [ ! -s "$CREDENTIALS_FILE" ]; then
    warn "Automated credential creation didn't work. Trying gcloud CLI..."

    # Use gcloud to create OAuth brand + client
    # First ensure OAuth brand exists
    gcloud alpha iap oauth-brands create \
      --application_title="OpenClaw PKB" \
      --support_email="$ACTIVE_ACCOUNT" \
      --project="$PROJECT_ID" 2>/dev/null || true

    # Create OAuth client
    CLIENT_OUTPUT=$(gcloud alpha iap oauth-clients create \
      "projects/$PROJECT_ID/brands/-" \
      --display_name="OpenClaw PKB Desktop" \
      --project="$PROJECT_ID" \
      --format=json 2>/dev/null || true)

    if echo "$CLIENT_OUTPUT" | grep -q "name"; then
      ok "OAuth client created via gcloud"
    fi
  fi

  # Final fallback: manual instructions
  if [ ! -f "$CREDENTIALS_FILE" ] || [ ! -s "$CREDENTIALS_FILE" ]; then
    echo ""
    echo -e "${COLOR_YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
    echo -e "${COLOR_YELLOW}  MANUAL STEP REQUIRED: Download OAuth credentials${COLOR_RESET}"
    echo -e "${COLOR_YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
    echo ""
    echo "  1. Open: https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID"
    echo "  2. Click '+ CREATE CREDENTIALS' → 'OAuth client ID'"
    echo "  3. Application type: 'Desktop app'"
    echo "  4. Name: 'OpenClaw PKB'"
    echo "  5. Click 'CREATE'"
    echo "  6. Click 'DOWNLOAD JSON'"
    echo "  7. Save the file, then run:"
    echo ""
    echo "     cp ~/Downloads/client_secret_*.json $CREDENTIALS_FILE"
    echo ""
    echo "  Then re-run this script."
    echo ""
    exit 1
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 7: Feed credentials to gog
# ─────────────────────────────────────────────────────────────────────────────
step "Step 7: Configure gog with credentials"

GOG_STATUS=$(gog auth credentials list 2>&1 || true)
if echo "$GOG_STATUS" | grep -q "client_id"; then
  ok "gog already has credentials configured"
else
  gog auth credentials set "$CREDENTIALS_FILE"
  ok "Credentials loaded into gog"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 8: Authenticate gog with Gmail account
# ─────────────────────────────────────────────────────────────────────────────
step "Step 8: Authenticate gog with your Gmail account"

GOG_ACCOUNTS=$(gog auth list 2>&1 || true)
if echo "$GOG_ACCOUNTS" | grep -q "@"; then
  ok "gog already authenticated"
  echo "$GOG_ACCOUNTS"
else
  ask "Opening browser for Gmail OAuth consent..."
  echo "  Grant gog access to your Gmail account."
  echo ""
  gog auth add "$ACTIVE_ACCOUNT"
  ok "gog authenticated with $ACTIVE_ACCOUNT"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 9: Verify
# ─────────────────────────────────────────────────────────────────────────────
step "Step 9: Verify Gmail access"

TEST_RESULT=$(gog gmail search "in:inbox" --limit 1 --json 2>&1 || true)
if echo "$TEST_RESULT" | grep -q "id\|threadId\|snippet"; then
  ok "Gmail access verified! gog can read your inbox."
else
  warn "Verification inconclusive. Output: $TEST_RESULT"
fi

echo ""
echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo -e "${COLOR_GREEN}  Gmail setup complete! Ready for Spec 07 execution.${COLOR_RESET}"
echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo ""
echo "  Next steps:"
echo "    gog gmail search 'category:promotions' --limit 5    # test search"
echo "    bash scripts/gmail-audit.sh                         # run full audit"
echo ""
