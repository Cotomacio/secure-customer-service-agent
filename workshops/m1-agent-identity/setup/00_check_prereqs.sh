#!/usr/bin/env bash
# M1 prerequisite check.
# Run in Cloud Shell, or locally with the Google Cloud SDK installed.
set -euo pipefail

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }

fail=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then green "[ok]    $label"
  else red "[fail]  $label"; fail=1; fi
}

echo "== M1 prerequisite check =="

check "gcloud installed"                command -v gcloud
check "python >= 3.11"                  bash -c 'python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"'
check "pip available"                   command -v pip3
check "gcloud authenticated"            bash -c 'gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .'
check "GOOGLE_CLOUD_PROJECT set"        bash -c '[[ -n "${GOOGLE_CLOUD_PROJECT:-}" ]]'
check "ORG_ID set"                      bash -c '[[ -n "${ORG_ID:-}" ]]'
check "LOCATION set"                    bash -c '[[ -n "${LOCATION:-us-central1}" ]]'

if [[ -n "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
  check "billing enabled on project"    bash -c 'gcloud billing projects describe "$GOOGLE_CLOUD_PROJECT" --format="value(billingEnabled)" | grep -q True'
fi

# Optional but recommended
if command -v adk >/dev/null 2>&1; then
  green "[ok]    adk CLI installed"
else
  yellow "[warn]  adk CLI not found — install with: pip install google-adk"
fi

echo
if (( fail )); then
  red "Prereqs failed. Fix the items marked [fail] and re-run."
  echo "Common fixes:"
  echo "  export GOOGLE_CLOUD_PROJECT=your-project-id"
  echo "  export ORG_ID=\$(gcloud organizations list --format='value(name)' | head -n1)"
  echo "  export LOCATION=us-central1"
  echo "  gcloud auth login && gcloud auth application-default login"
  exit 1
fi

green "All prerequisites satisfied. Continue with 10_enable_apis.sh"
