"""Stage 2 reference solution — tools.

Two tools wired in:

1. `lookup_order` — same as Stage 1, reads `orders.csv` from GCS using Ada's
   own SPIFFE identity (ADC at runtime).
2. `lookup_incidents` — calls ServiceNow's REST API for active incidents.
   Authenticates via the Agent Identity Auth Manager's 2-legged OAuth flow:
   the agent never holds the ServiceNow client_id / client_secret. The
   bearer token is fetched at call time from Auth Manager and injected
   into `_credential` by the ADK `AuthenticatedFunctionTool` wrapper.
"""

import csv
import io
import os

import requests
from google.cloud import storage


# ---------------------------------------------------------------------------
# Stage 1 tool — order lookup via GCS using Agent Identity
# ---------------------------------------------------------------------------

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
        A dict describing the order, or {"found": False} if not found.
    """
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


# ---------------------------------------------------------------------------
# Stage 2 tool — ServiceNow incident lookup via 2-legged OAuth (Auth Manager)
# ---------------------------------------------------------------------------

SNOW_INSTANCE_URL = os.environ.get("SNOW_INSTANCE_URL", "").rstrip("/")


def lookup_incidents(query: str = "active=true", limit: int = 5, _credential=None) -> dict:
    """Look up ServiceNow incidents matching an encoded query.

    Args:
        query: ServiceNow encoded query string. Examples:
            - "active=true"                                  (all active incidents)
            - "active=true^short_descriptionLIKEcheckout"    (active + matching text)
            - "category=software^state=2"                    (software, in-progress)
        limit: Max incidents to return (default 5).
        _credential: Injected by ADK's AuthenticatedFunctionTool with the OAuth
            access token retrieved from Auth Manager. Ada's process never holds
            the ServiceNow client_id / client_secret.

    Returns:
        {"found": True, "count": N, "incidents": [...]} or {"found": False, ...}
    """
    if not SNOW_INSTANCE_URL:
        return {"found": False, "error": "SNOW_INSTANCE_URL not set in agent env"}
    if _credential is None or not getattr(_credential, "access_token", None):
        return {"found": False, "error": "No credential injected by Auth Manager"}

    url = f"{SNOW_INSTANCE_URL}/api/now/table/incident"
    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {_credential.access_token}",
            "Accept": "application/json",
        },
        params={
            "sysparm_query": query,
            "sysparm_limit": str(limit),
            "sysparm_fields": "number,short_description,state,priority,category,sys_created_on",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        return {
            "found": False,
            "error": f"ServiceNow returned {resp.status_code}: {resp.text[:200]}",
        }

    result = resp.json().get("result", [])
    return {
        "found": bool(result),
        "count": len(result),
        "incidents": result,
    }
