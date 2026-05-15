#!/usr/bin/env bash
# Create the ServiceNow 2-legged OAuth auth provider in Agent Identity Auth Manager,
# and grant Ada's SPIFFE principal the Connector User role on it.
#
# After this script:
#   - The ServiceNow client_id and client_secret live in Auth Manager — not in
#     the agent's container, source, or env vars.
#   - Ada (identified by AGENT_IDENTITY) can call retrieveCredentials on the
#     provider at runtime to get a fresh ServiceNow bearer token.
#
# Idempotent: re-running updates the provider with the current credentials and
# re-applies the IAM binding.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${LOCATION:=us-central1}"
: "${SNOW_INSTANCE_URL:?Set SNOW_INSTANCE_URL (e.g. https://devXXXXX.service-now.com) in .env.local}"
: "${SNOW_CLIENT_ID:?Set SNOW_CLIENT_ID in .env.local}"
: "${SNOW_CLIENT_SECRET:?Set SNOW_CLIENT_SECRET in .env.local}"
: "${AGENT_IDENTITY:?Set AGENT_IDENTITY — printed by deploy.py}"

PROVIDER_NAME="${SNOW_PROVIDER_NAME:-snow-incidents}"
TOKEN_ENDPOINT="${SNOW_INSTANCE_URL%/}/oauth_token.do"

echo "ServiceNow auth provider configuration"
echo "  Provider:        $PROVIDER_NAME"
echo "  Location:        $LOCATION"
echo "  Token endpoint:  $TOKEN_ENDPOINT"
echo "  Principal:       $AGENT_IDENTITY"
echo

# Make sure alpha components are available (Cloud Shell has them; local installs may not).
gcloud components install alpha --quiet 2>/dev/null || true

# Create-or-update the connector. The CLI returns non-zero on "already exists"; we then
# update instead. That keeps the script re-runnable.
echo "→ Creating connector..."
if gcloud alpha agent-identity connectors create "$PROVIDER_NAME" \
    --location="$LOCATION" \
    --two-legged-oauth-client-id="$SNOW_CLIENT_ID" \
    --two-legged-oauth-client-secret="$SNOW_CLIENT_SECRET" \
    --two-legged-oauth-token-endpoint="$TOKEN_ENDPOINT" \
    --quiet 2>/dev/null; then
  echo "  ✓ created"
else
  echo "  ↺ exists — updating with current credentials"
  gcloud alpha agent-identity connectors update "$PROVIDER_NAME" \
    --location="$LOCATION" \
    --two-legged-oauth-client-id="$SNOW_CLIENT_ID" \
    --two-legged-oauth-client-secret="$SNOW_CLIENT_SECRET" \
    --two-legged-oauth-token-endpoint="$TOKEN_ENDPOINT" \
    --quiet
fi

# Grant Ada permission to call retrieveCredentials on this provider.
echo "→ Granting Ada roles/iamconnectors.user on the connector..."
gcloud alpha agent-identity connectors add-iam-policy-binding "$PROVIDER_NAME" \
  --location="$LOCATION" \
  --member="$AGENT_IDENTITY" \
  --role="roles/iamconnectors.user" \
  --quiet

PROVIDER_RESOURCE="projects/${GOOGLE_CLOUD_PROJECT}/locations/${LOCATION}/connectors/${PROVIDER_NAME}"
echo
echo "✓ ServiceNow auth provider ready."
echo "  Resource name (referenced in agent code):"
echo "    $PROVIDER_RESOURCE"
echo
echo "  ⏳ Allow ~30s for IAM propagation before talking to Ada."
