#!/usr/bin/env bash
# Create the GitHub 3LO connector in Auth Manager + bind Ada.
# After this, run `python consent_github.py` once to capture the user
# authorization that 3LO retrieveCredentials looks up.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${LOCATION:=us-central1}"
: "${GH_CLIENT_ID:?Set GH_CLIENT_ID in .env.local}"
: "${GH_CLIENT_SECRET:?Set GH_CLIENT_SECRET in .env.local}"
: "${AGENT_IDENTITY:?Set AGENT_IDENTITY — printed by deploy.py}"

PROVIDER="${GH_PROVIDER_NAME:-github-3lo}"
AUTH_ENDPOINT="https://github.com/login/oauth/authorize"
TOKEN_ENDPOINT="https://github.com/login/oauth/access_token"
SCOPES="${GH_SCOPES:-public_repo}"

echo "GitHub 3LO connector: $PROVIDER  (scopes: $SCOPES)"
gcloud components install alpha --quiet 2>/dev/null || true

if gcloud alpha agent-identity connectors create "$PROVIDER" \
    --location="$LOCATION" \
    --three-legged-oauth-client-id="$GH_CLIENT_ID" \
    --three-legged-oauth-client-secret="$GH_CLIENT_SECRET" \
    --three-legged-oauth-authorization-endpoint="$AUTH_ENDPOINT" \
    --three-legged-oauth-token-endpoint="$TOKEN_ENDPOINT" \
    --three-legged-oauth-scopes="$SCOPES" \
    --quiet 2>/dev/null; then
  echo "  ✓ created"
else
  echo "  ↺ exists — updating"
  gcloud alpha agent-identity connectors update "$PROVIDER" \
    --location="$LOCATION" \
    --three-legged-oauth-client-id="$GH_CLIENT_ID" \
    --three-legged-oauth-client-secret="$GH_CLIENT_SECRET" \
    --three-legged-oauth-authorization-endpoint="$AUTH_ENDPOINT" \
    --three-legged-oauth-token-endpoint="$TOKEN_ENDPOINT" \
    --three-legged-oauth-scopes="$SCOPES" \
    --quiet
fi

gcloud alpha agent-identity connectors add-iam-policy-binding "$PROVIDER" \
  --location="$LOCATION" \
  --member="$AGENT_IDENTITY" \
  --role="roles/iamconnectors.user" \
  --quiet

PROVIDER_RESOURCE="projects/${GOOGLE_CLOUD_PROJECT}/locations/${LOCATION}/connectors/${PROVIDER}"
echo
echo "✓ GitHub connector ready: $PROVIDER_RESOURCE"
echo
echo "📌 BEFORE running consent_github.py, set the GitHub OAuth App's"
echo "   'Authorization callback URL' to:"
echo "       http://localhost:8080/callback"
echo "   at https://github.com/settings/developers"
echo
echo "Then run:  python consent_github.py"
