#!/usr/bin/env bash
# Enable APIs needed for M1.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT before running}"

apis=(
  aiplatform.googleapis.com         # Agent Engine / reasoning engines
  iamconnectors.googleapis.com      # Auth Manager
  agentregistry.googleapis.com      # Agent Registry (used to attach auth providers in M1)
  storage.googleapis.com            # GCS (Stage 1)
  cloudresourcemanager.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  serviceusage.googleapis.com
  logging.googleapis.com            # Audit logs verification
)

echo "Enabling APIs on project $GOOGLE_CLOUD_PROJECT ..."
gcloud services enable "${apis[@]}" --project="$GOOGLE_CLOUD_PROJECT"
echo "Done."
