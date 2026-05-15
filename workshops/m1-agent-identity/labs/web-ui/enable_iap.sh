#!/usr/bin/env bash
# Wrap the Cloud Run UI with Identity-Aware Proxy.
#
# After this:
#   - Cloud Run service requires IAP to invoke (--no-allow-unauthenticated)
#   - Users hitting the URL get a Google sign-in
#   - Only users you've granted roles/iap.httpsResourceAccessor pass through
#
# Per https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
#
# Run AFTER deploy.sh has succeeded once. Idempotent.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?}"
: "${LOCATION:=us-central1}"

SERVICE="${ADA_WEB_SERVICE:-ada-web}"
IAP_USERS="${IAP_USERS:-}"   # comma-separated list of user:foo@example.com,group:bar@example.com

PROJECT_NUMBER=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')
IAP_SA="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"

echo "Enabling IAP on Cloud Run service '$SERVICE' in '$LOCATION'"
echo

# Step 1: enable IAP API + Cloud Resource Manager API (used by IAP UI for org check)
echo "→ Enabling iap.googleapis.com..."
gcloud services enable iap.googleapis.com --project="$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1 || true
echo "  ✓"

# Step 2: flip the Cloud Run service to require IAP
echo "→ Updating Cloud Run service to require IAP..."
gcloud run services update "$SERVICE" \
  --region="$LOCATION" \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --no-allow-unauthenticated \
  --iap \
  --quiet
echo "  ✓ service now requires IAP"

# Step 3: grant the IAP service agent permission to invoke the service.
# (IAP authenticates the user, then calls Cloud Run as itself.)
echo "→ Granting roles/run.invoker to the IAP service agent ($IAP_SA)..."
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$LOCATION" \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:$IAP_SA" \
  --role="roles/run.invoker" \
  --quiet > /dev/null
echo "  ✓"

# Step 4: grant access to users / groups.
if [[ -z "$IAP_USERS" ]]; then
  # Default: the gcloud-authenticated user (i.e., you)
  ME=$(gcloud auth list --filter=status:ACTIVE --format='value(account)')
  IAP_USERS="user:$ME"
  echo "→ No IAP_USERS env var set — granting access to your account: $ME"
fi

IFS=',' read -ra MEMBERS <<< "$IAP_USERS"
for m in "${MEMBERS[@]}"; do
  m="$(echo "$m" | xargs)"   # trim whitespace
  [[ -z "$m" ]] && continue
  echo "→ Granting roles/iap.httpsResourceAccessor to $m..."
  gcloud iap web add-iam-policy-binding \
    --member="$m" \
    --role="roles/iap.httpsResourceAccessor" \
    --region="$LOCATION" \
    --resource-type=cloud-run \
    --service="$SERVICE" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --quiet > /dev/null
  echo "  ✓"
done

URL=$(gcloud run services describe "$SERVICE" \
  --region="$LOCATION" --project="$GOOGLE_CLOUD_PROJECT" \
  --format='value(status.url)')

echo
echo "✓ IAP enabled."
echo "  URL: $URL"
echo
echo "  Open the URL in a browser. You'll get a Google sign-in. The"
echo "  accounts you granted iap.httpsResourceAccessor will pass through;"
echo "  others will see 'You don't have access'."
echo
echo "To add more users later:"
echo "  IAP_USERS=user:colleague@acme.example bash enable_iap.sh"
echo
echo "If this is the first time you've used IAP in this project, you may"
echo "need to configure the OAuth consent screen once at:"
echo "  https://console.cloud.google.com/apis/credentials/consent?project=$GOOGLE_CLOUD_PROJECT"
