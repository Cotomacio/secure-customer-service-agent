#!/usr/bin/env bash
# Create the OpenWeather API-key connector in Auth Manager + bind Ada.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${LOCATION:=us-central1}"
: "${OPENWEATHER_API_KEY:?}"
: "${AGENT_IDENTITY:?Set AGENT_IDENTITY — printed by deploy.py}"

PROVIDER="${WEATHER_PROVIDER_NAME:-openweather}"

echo "OpenWeather API-key connector: $PROVIDER"
gcloud components install alpha --quiet 2>/dev/null || true

if gcloud alpha agent-identity connectors create "$PROVIDER" \
    --location="$LOCATION" \
    --api-key="$OPENWEATHER_API_KEY" \
    --quiet 2>/dev/null; then
  echo "  ✓ created"
else
  echo "  ↺ exists — updating"
  gcloud alpha agent-identity connectors update "$PROVIDER" \
    --location="$LOCATION" \
    --api-key="$OPENWEATHER_API_KEY" \
    --quiet
fi

gcloud alpha agent-identity connectors add-iam-policy-binding "$PROVIDER" \
  --location="$LOCATION" \
  --member="$AGENT_IDENTITY" \
  --role="roles/iamconnectors.user" \
  --quiet

echo "✓ OpenWeather connector ready"
