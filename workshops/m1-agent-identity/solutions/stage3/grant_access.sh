#!/usr/bin/env bash
# Bucket-level grant for Stage 3's Ada (carries Stage 1's order lookup).
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${AGENT_IDENTITY:?Set AGENT_IDENTITY — printed by deploy.py}"

BUCKET="gs://acme-orders-${GOOGLE_CLOUD_PROJECT}"
echo "Granting Stage 3 Ada read access to $BUCKET"
echo "Principal: $AGENT_IDENTITY"
gcloud storage buckets add-iam-policy-binding "$BUCKET" \
  --member="$AGENT_IDENTITY" \
  --role="roles/storage.objectViewer"
echo "✓ done"
