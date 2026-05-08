#!/usr/bin/env bash
# Bind Ada's SPIFFE principal to roles/storage.objectViewer on the orders bucket.
# Run AFTER deploy.py prints REASONING_ENGINE_ID and AGENT_IDENTITY.
#
# Baseline project-scope roles (serviceUsageConsumer, expressUser, browser) are
# already granted by deploy.py Phase 4. This script only adds the bucket grant
# that is the actual lesson of Stage 1: least-privilege, per-resource access.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${REASONING_ENGINE_ID:?Set REASONING_ENGINE_ID — printed by deploy.py}"

# Prefer the AGENT_IDENTITY printed by deploy.py (uses effective_identity from
# the API). Fall back to constructing from ORG_ID if not provided.
if [[ -z "${AGENT_IDENTITY:-}" ]]; then
  : "${ORG_ID:?Set ORG_ID OR set AGENT_IDENTITY directly from deploy.py output}"
  : "${LOCATION:=us-central1}"
  PROJECT_NUMBER="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')"
  AGENT_IDENTITY="principal://agents.global.org-${ORG_ID}.system.id.goog/resources/aiplatform/projects/${PROJECT_NUMBER}/locations/${LOCATION}/reasoningEngines/${REASONING_ENGINE_ID}"
fi

BUCKET="gs://acme-orders-${GOOGLE_CLOUD_PROJECT}"

echo "Granting Ada read access to $BUCKET"
echo "Principal: $AGENT_IDENTITY"
echo

gcloud storage buckets add-iam-policy-binding "$BUCKET" \
  --member="$AGENT_IDENTITY" \
  --role="roles/storage.objectViewer"

echo
echo "Done. Verify with:"
echo "  gcloud storage buckets get-iam-policy $BUCKET --format='table(bindings.role,bindings.members)'"
