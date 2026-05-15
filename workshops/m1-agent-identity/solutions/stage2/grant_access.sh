#!/usr/bin/env bash
# Bucket-level grant for Stage 2's Ada (mirrors Stage 1).
# Stage 2's agent keeps the order-lookup tool, so Ada still needs read access
# on gs://acme-orders-${PROJECT_ID}.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${REASONING_ENGINE_ID:?Set REASONING_ENGINE_ID — printed by deploy.py}"

if [[ -z "${AGENT_IDENTITY:-}" ]]; then
  : "${ORG_ID:?Set ORG_ID OR set AGENT_IDENTITY directly from deploy.py output}"
  : "${LOCATION:=us-central1}"
  PROJECT_NUMBER="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')"
  AGENT_IDENTITY="principal://agents.global.org-${ORG_ID}.system.id.goog/resources/aiplatform/projects/${PROJECT_NUMBER}/locations/${LOCATION}/reasoningEngines/${REASONING_ENGINE_ID}"
fi

BUCKET="gs://acme-orders-${GOOGLE_CLOUD_PROJECT}"

echo "Granting Stage 2 Ada read access to $BUCKET"
echo "Principal: $AGENT_IDENTITY"
gcloud storage buckets add-iam-policy-binding "$BUCKET" \
  --member="$AGENT_IDENTITY" \
  --role="roles/storage.objectViewer"
echo "✓ done"
