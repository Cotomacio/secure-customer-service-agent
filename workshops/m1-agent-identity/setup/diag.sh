#!/usr/bin/env bash
# One-shot diagnostic for a stuck Agent Engine deploy.
# Run in Cloud Shell after a failed `python deploy.py`.
#
#   bash diag.sh [REASONING_ENGINE_ID]
#
# If no engine id is passed, uses $REASONING_ENGINE_ID from the env.
set -uo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${LOCATION:=us-central1}"
ENGINE_ID="${1:-${REASONING_ENGINE_ID:-}}"
if [[ -z "$ENGINE_ID" ]]; then
  echo "Usage: bash diag.sh <REASONING_ENGINE_ID> (or export REASONING_ENGINE_ID)"
  exit 1
fi

PROJECT_NUMBER="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')"

bar() { printf '\n%.0s=' {1..72}; printf '\n  %s\n' "$1"; printf '%.0s=' {1..72}; echo; }

bar "1. Engine state (REST describe)"
curl -sH "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${GOOGLE_CLOUD_PROJECT}/locations/${LOCATION}/reasoningEngines/${ENGINE_ID}" \
  | python -m json.tool 2>&1 | head -80

bar "2. Recent operations on this engine (LROs — true error often lives here)"
curl -sH "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${GOOGLE_CLOUD_PROJECT}/locations/${LOCATION}/operations?filter=metadata.genericMetadata.resourceName=projects/${PROJECT_NUMBER}/locations/${LOCATION}/reasoningEngines/${ENGINE_ID}&pageSize=5" \
  | python -m json.tool 2>&1 | head -120

bar "3. ALL logs from this engine, last 30 min, any severity"
gcloud logging read \
  "resource.type=\"aiplatform.googleapis.com/ReasoningEngine\" AND resource.labels.reasoning_engine_id=\"${ENGINE_ID}\"" \
  --limit=20 --freshness=30m \
  --format='table(timestamp.date(),severity,jsonPayload.message,textPayload)' \
  --project="$GOOGLE_CLOUD_PROJECT" 2>&1 | head -100

bar "4. Project-wide ReasoningEngine errors, last 30 min (catches some platform-level errors not bound to engine id)"
gcloud logging read \
  'resource.type="aiplatform.googleapis.com/ReasoningEngine" AND severity>=ERROR' \
  --limit=10 --freshness=30m \
  --format='table(timestamp.date(),resource.labels.reasoning_engine_id,jsonPayload.message:label=MESSAGE,textPayload:label=TEXT)' \
  --project="$GOOGLE_CLOUD_PROJECT" 2>&1 | head -60

bar "5. IAM bindings on this agent's SPIFFE principal (project scope)"
PRINCIPAL_SUFFIX="reasoningEngines/${ENGINE_ID}"
gcloud projects get-iam-policy "$GOOGLE_CLOUD_PROJECT" \
  --flatten='bindings[].members' \
  --format='table(bindings.role,bindings.members)' \
  --filter="bindings.members ~ ${PRINCIPAL_SUFFIX}" 2>&1 | head -30

bar "6. IAM on the orders bucket"
gcloud storage buckets get-iam-policy "gs://acme-orders-${GOOGLE_CLOUD_PROJECT}" \
  --format='table(bindings.role,bindings.members)' 2>&1 | head -30

bar "7. Local source state — adk-shipped paths"
echo "--- agent/ tree ---"
ls -la agent/ 2>/dev/null
echo "--- last lines of agent/agent.py ---"
tail -20 agent/agent.py 2>/dev/null
echo "--- agent_engine_app.py ---"
cat agent/agent_engine_app.py 2>/dev/null
echo "--- .env that gets shipped ---"
cat .env 2>/dev/null
echo "--- requirements ---"
cat agent/requirements.txt 2>/dev/null || cat requirements.txt 2>/dev/null

bar "Done. Paste this whole block back."
