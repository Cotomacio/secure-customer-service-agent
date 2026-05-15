#!/usr/bin/env bash
# Create the OpenWeather API-key auth provider in Agent Identity Auth Manager,
# and grant Ada's SPIFFE principal the Connector User role on it.
#
# After this script:
#   - The OpenWeather API key lives in Auth Manager — not in the agent's
#     container, source, or env vars.
#   - Ada (identified by AGENT_IDENTITY) can call retrieveCredentials on the
#     provider at runtime to get the API key.
#
# Idempotent: re-running updates the API key and re-applies the IAM binding.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${LOCATION:=us-central1}"
: "${OPENWEATHER_API_KEY:?Set OPENWEATHER_API_KEY in .env.local}"
: "${AGENT_IDENTITY:?Set AGENT_IDENTITY — printed by deploy.py}"

PROVIDER_NAME="${WEATHER_PROVIDER_NAME:-openweather}"

echo "OpenWeather auth provider configuration"
echo "  Provider:  $PROVIDER_NAME"
echo "  Location:  $LOCATION"
echo "  Principal: $AGENT_IDENTITY"
echo

gcloud components install alpha --quiet 2>/dev/null || true

echo "→ Creating connector..."
if gcloud alpha agent-identity connectors create "$PROVIDER_NAME" \
    --location="$LOCATION" \
    --api-key="$OPENWEATHER_API_KEY" \
    --quiet 2>/dev/null; then
  echo "  ✓ created"
else
  echo "  ↺ exists — updating with current API key"
  gcloud alpha agent-identity connectors update "$PROVIDER_NAME" \
    --location="$LOCATION" \
    --api-key="$OPENWEATHER_API_KEY" \
    --quiet
fi

echo "→ Granting Ada roles/iamconnectors.user on the connector..."
gcloud alpha agent-identity connectors add-iam-policy-binding "$PROVIDER_NAME" \
  --location="$LOCATION" \
  --member="$AGENT_IDENTITY" \
  --role="roles/iamconnectors.user" \
  --quiet

PROVIDER_RESOURCE="projects/${GOOGLE_CLOUD_PROJECT}/locations/${LOCATION}/connectors/${PROVIDER_NAME}"
echo
echo "✓ OpenWeather auth provider ready."
echo "  Resource: $PROVIDER_RESOURCE"
echo "  ⏳ Allow several minutes for IAM propagation before talking to Ada."
