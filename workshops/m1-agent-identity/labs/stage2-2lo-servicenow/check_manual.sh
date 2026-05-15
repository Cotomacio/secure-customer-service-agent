#!/usr/bin/env bash
# Stage 2 — Check what's currently configured for Auth Manager / ServiceNow
# after a manual console action. Run from anywhere.
set +e
source ~/secure-customer-service-agent/workshops/m1-agent-identity/.env.local

ENGINE_ID="${REASONING_ENGINE_ID:-2878042604203671552}"

bar() { printf '\n%.0s=' {1..70}; printf '\n  %s\n' "$1"; printf '%.0s=' {1..70}; echo; }

bar "1. All connectors in project"
gcloud alpha agent-identity connectors list \
  --location=us-central1 --project="$GOOGLE_CLOUD_PROJECT" \
  --format='table(name.basename(),createTime,state)'

bar "2. snow-incidents — authorizations list (may be empty)"
gcloud alpha agent-identity connectors authorizations list \
  --connector=snow-incidents --location=us-central1 \
  --project="$GOOGLE_CLOUD_PROJECT"

bar "3. snow-incidents — full spec"
gcloud alpha agent-identity connectors describe snow-incidents \
  --location=us-central1 --project="$GOOGLE_CLOUD_PROJECT" \
  --format=yaml

bar "4. snow-incidents — IAM policy"
gcloud alpha agent-identity connectors get-iam-policy snow-incidents \
  --location=us-central1 --project="$GOOGLE_CLOUD_PROJECT" \
  --format=yaml

bar "5. Chat test against ada-stage2"
cd ~/secure-customer-service-agent/workshops/m1-agent-identity/labs/stage2-2lo-servicenow
source .venv/bin/activate
export REASONING_ENGINE_ID="$ENGINE_ID"
python chat.py "Are there any active checkout incidents?"
