#!/usr/bin/env bash
# Deploy the Streamlit chat UI to Cloud Run.
#
# Prerequisites:
#   - GOOGLE_CLOUD_PROJECT, LOCATION, REASONING_ENGINE_ID set
#   - You're authenticated with gcloud
#   - The Cloud Run service's runtime SA needs roles/aiplatform.user
#     (handled below; uses the project's default compute SA unless
#     you set ADA_WEB_RUNTIME_SA).
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?}"
: "${LOCATION:=us-central1}"
: "${REASONING_ENGINE_ID:?Set REASONING_ENGINE_ID — the engine the UI will chat with}"

SERVICE="${ADA_WEB_SERVICE:-ada-web}"
RUNTIME_SA="${ADA_WEB_RUNTIME_SA:-}"

# Default to the compute engine default SA (always exists with the project)
if [[ -z "$RUNTIME_SA" ]]; then
  PROJECT_NUMBER=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')
  RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
fi

echo "Cloud Run deploy"
echo "  Service:        $SERVICE"
echo "  Region:         $LOCATION"
echo "  Engine:         projects/$GOOGLE_CLOUD_PROJECT/locations/$LOCATION/reasoningEngines/$REASONING_ENGINE_ID"
echo "  Runtime SA:     $RUNTIME_SA"
echo

# Enable the APIs we need (idempotent)
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  --project="$GOOGLE_CLOUD_PROJECT" 2>&1 | grep -v "^Operation" || true

# Grant the runtime SA permission to invoke the agent engine
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/aiplatform.user" \
  --condition=None --quiet > /dev/null
echo "  ✓ granted roles/aiplatform.user to $RUNTIME_SA"

# Build + deploy. --allow-unauthenticated makes the URL public — fine for
# demos / colleague playground; for production restrict via IAP or Cloud Run IAM.
gcloud run deploy "$SERVICE" \
  --source . \
  --region="$LOCATION" \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --service-account="$RUNTIME_SA" \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT,LOCATION=$LOCATION,REASONING_ENGINE_ID=$REASONING_ENGINE_ID,AGENT_DISPLAY_NAME=${AGENT_DISPLAY_NAME:-Ada}" \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=600

URL=$(gcloud run services describe "$SERVICE" --region="$LOCATION" --format='value(status.url)')
echo
echo "✓ Deployed"
echo "  URL: $URL"
echo "  Open in browser and chat with Ada."
