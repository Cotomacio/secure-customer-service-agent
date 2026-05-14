#!/usr/bin/env bash
# Enable Data Access audit logs for Cloud Storage on this project so that
# the Stage 1 audit-log verification step can see the SPIFFE principalSubject
# of GCS object reads. Cloud Storage's data-read events are opt-in; without
# this, only Admin Activity (bucket create/delete/IAM) is logged.
#
# Idempotent — safe to re-run. Merges into the existing project IAM policy
# rather than overwriting.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"

echo "Enabling Storage Data Access audit logs on project $GOOGLE_CLOUD_PROJECT ..."

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
POLICY="$TMPDIR/policy.yaml"

gcloud projects get-iam-policy "$GOOGLE_CLOUD_PROJECT" --format=yaml > "$POLICY"

python3 - "$POLICY" <<'PY'
import sys
import yaml

path = sys.argv[1]
with open(path) as f:
    policy = yaml.safe_load(f) or {}

audit_configs = [
    c for c in policy.get("auditConfigs", [])
    if c.get("service") != "storage.googleapis.com"
]
audit_configs.append({
    "service": "storage.googleapis.com",
    "auditLogConfigs": [
        {"logType": "DATA_READ"},
        {"logType": "DATA_WRITE"},
    ],
})
policy["auditConfigs"] = audit_configs

with open(path, "w") as f:
    yaml.safe_dump(policy, f)
PY

gcloud projects set-iam-policy "$GOOGLE_CLOUD_PROJECT" "$POLICY" --quiet > /dev/null

echo "✓ Storage DATA_READ + DATA_WRITE audit logs enabled."
echo "  Allow ~30 s for the change to take effect before triggering reads."
