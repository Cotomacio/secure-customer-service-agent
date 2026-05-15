#!/usr/bin/env bash
# Create the ServiceNow 2LO connector in Auth Manager + bind Ada.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${LOCATION:=us-central1}"
: "${SNOW_INSTANCE_URL:?}"
: "${SNOW_CLIENT_ID:?}"
: "${SNOW_CLIENT_SECRET:?}"
: "${AGENT_IDENTITY:?Set AGENT_IDENTITY — printed by deploy.py}"

PROVIDER="${SNOW_PROVIDER_NAME:-snow-incidents}"
TOKEN_ENDPOINT="${SNOW_INSTANCE_URL%/}/oauth_token.do"

echo "ServiceNow 2LO connector: $PROVIDER  (token: $TOKEN_ENDPOINT)"
gcloud components install alpha --quiet 2>/dev/null || true

if gcloud alpha agent-identity connectors create "$PROVIDER" \
    --location="$LOCATION" \
    --two-legged-oauth-client-id="$SNOW_CLIENT_ID" \
    --two-legged-oauth-client-secret="$SNOW_CLIENT_SECRET" \
    --two-legged-oauth-token-endpoint="$TOKEN_ENDPOINT" \
    --quiet 2>/dev/null; then
  echo "  ✓ created"
else
  echo "  ↺ exists — updating"
  gcloud alpha agent-identity connectors update "$PROVIDER" \
    --location="$LOCATION" \
    --two-legged-oauth-client-id="$SNOW_CLIENT_ID" \
    --two-legged-oauth-client-secret="$SNOW_CLIENT_SECRET" \
    --two-legged-oauth-token-endpoint="$TOKEN_ENDPOINT" \
    --quiet
fi

gcloud alpha agent-identity connectors add-iam-policy-binding "$PROVIDER" \
  --location="$LOCATION" \
  --member="$AGENT_IDENTITY" \
  --role="roles/iamconnectors.user" \
  --quiet

echo "✓ ServiceNow connector ready: projects/${GOOGLE_CLOUD_PROJECT}/locations/${LOCATION}/connectors/${PROVIDER}"
