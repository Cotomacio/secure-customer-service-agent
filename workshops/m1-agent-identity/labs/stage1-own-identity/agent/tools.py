"""
Stage 1 — Order lookup tool.

The whole point of this file: read a CSV from GCS using ADC. No credentials passed in.
On Agent Engine with Agent Identity enabled, ADC resolves to Ada's SPIFFE-bound token.
"""

import csv
import io
import os
from typing import Optional

from google.cloud import storage


BUCKET_NAME = os.environ.get(
    "ORDERS_BUCKET",
    f"acme-orders-{os.environ.get('GOOGLE_CLOUD_PROJECT', '')}",
)
ORDERS_BLOB = "orders.csv"


def lookup_order(order_id: str) -> dict:
    """Look up an Acme Commerce order by its ID.

    Args:
        order_id: The order identifier, e.g. "ACME-78214".

    Returns:
        A dict with the order fields, or {"found": False} if not found.
    """
    # TODO(stage1): Implement the lookup.
    #   1. Create a storage.Client() with NO arguments. ADC will resolve to
    #      Ada's Agent Identity when this runs in Agent Engine.
    #   2. Get the bucket BUCKET_NAME and the blob ORDERS_BLOB.
    #   3. Download the blob as text and parse with csv.DictReader.
    #   4. Return the row whose order_id matches; else {"found": False}.
    #
    # The reference solution is ../../solutions/stage1/tools.py
    raise NotImplementedError("Implement lookup_order in tools.py")


def _row_to_response(row: dict) -> dict:
    """Shape the CSV row into a chat-friendly response."""
    return {
        "found": True,
        "order_id": row["order_id"],
        "customer_name": row["customer_name"],
        "destination_city": row["destination_city"],
        "status": row["status"],
        "promised_by": row["promised_by"],
    }
