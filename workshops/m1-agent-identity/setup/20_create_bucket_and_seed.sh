#!/usr/bin/env bash
# Create the acme-orders GCS bucket and seed it with sample data for Stage 1.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${LOCATION:=us-central1}"

BUCKET="gs://acme-orders-${GOOGLE_CLOUD_PROJECT}"

if gcloud storage buckets describe "$BUCKET" >/dev/null 2>&1; then
  echo "Bucket $BUCKET already exists."
else
  echo "Creating bucket $BUCKET in $LOCATION ..."
  gcloud storage buckets create "$BUCKET" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --location="$LOCATION" \
    --uniform-bucket-level-access
fi

# Seed orders.csv. The "Maria / ACME-78214 / Denver" row is the capstone scenario.
tmp="$(mktemp)"
cat > "$tmp" <<'CSV'
order_id,customer_name,customer_email,destination_city,status,placed_at,promised_by
ACME-78214,Maria Alvarez,maria@example.com,Denver,out_for_delivery,2026-05-04T10:12:00Z,2026-05-06T18:00:00Z
ACME-78215,Jordan Kim,jordan@example.com,Austin,delivered,2026-05-03T08:30:00Z,2026-05-05T18:00:00Z
ACME-78216,Sam Patel,sam@example.com,Seattle,processing,2026-05-06T09:00:00Z,2026-05-09T18:00:00Z
ACME-78217,Alex Chen,alex@example.com,Boston,shipped,2026-05-05T14:45:00Z,2026-05-08T18:00:00Z
ACME-78218,Riya Nair,riya@example.com,Denver,shipped,2026-05-05T15:00:00Z,2026-05-08T18:00:00Z
CSV

gcloud storage cp "$tmp" "$BUCKET/orders.csv"
rm -f "$tmp"

echo "Seeded $BUCKET/orders.csv"
echo
echo "Note: deliberately NO public read binding. Only Ada's SPIFFE principal will be granted access in Stage 1."
