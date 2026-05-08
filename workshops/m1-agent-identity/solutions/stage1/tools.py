"""Stage 1 reference solution — tools.py."""

import csv
import io
import os

from google.cloud import storage


BUCKET_NAME = os.environ.get(
    "ORDERS_BUCKET",
    f"acme-orders-{os.environ.get('GOOGLE_CLOUD_PROJECT', '')}",
)
ORDERS_BLOB = "orders.csv"


def lookup_order(order_id: str) -> dict:
    """Look up an Acme Commerce order by its ID."""
    client = storage.Client()  # ADC -> Agent Identity at runtime
    blob = client.bucket(BUCKET_NAME).blob(ORDERS_BLOB)
    text = blob.download_as_text()

    for row in csv.DictReader(io.StringIO(text)):
        if row["order_id"] == order_id:
            return {
                "found": True,
                "order_id": row["order_id"],
                "customer_name": row["customer_name"],
                "destination_city": row["destination_city"],
                "status": row["status"],
                "promised_by": row["promised_by"],
            }

    return {"found": False, "order_id": order_id}
