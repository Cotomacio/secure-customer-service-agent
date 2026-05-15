"""Stage 2 reference solution — tools.

Two tools wired in:

1. `lookup_order` — same as Stage 1, reads `orders.csv` from GCS using Ada's
   own SPIFFE identity (ADC at runtime).
2. `lookup_incidents` — calls ServiceNow's REST API for active incidents.
   Authenticates via Agent Identity Auth Manager's 2-legged OAuth flow:
   the function asks the iamconnectorcredentials API for a fresh ServiceNow
   bearer token at every call (using Ada's SPIFFE identity for the API call
   itself), then uses that token to call ServiceNow. The ServiceNow client_id
   and client_secret live in Auth Manager — never in agent source or runtime.
"""

import csv
import io
import os

import requests
from google.cloud import iamconnectorcredentials_v1alpha, storage


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

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("LOCATION", "us-central1")
SNOW_INSTANCE_URL = os.environ.get("SNOW_INSTANCE_URL", "").rstrip("/")
SNOW_PROVIDER_NAME = os.environ.get("SNOW_PROVIDER_NAME", "snow-incidents")
SNOW_CONNECTOR_RESOURCE = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/{SNOW_PROVIDER_NAME}"
)


def _fetch_servicenow_token() -> str:
    """Fetch a fresh ServiceNow bearer token from Agent Identity Auth Manager.

    Uses the agent's SPIFFE identity (via ADC) to authenticate to the
    iamconnectorcredentials API. Auth Manager performs the 2-legged OAuth
    exchange with ServiceNow internally and returns the resulting bearer token.
    The ServiceNow client_id / client_secret stay in Auth Manager.
    """
    client = iamconnectorcredentials_v1alpha.IAMConnectorCredentialsServiceClient()
    request = iamconnectorcredentials_v1alpha.RetrieveCredentialsRequest(
        connector=SNOW_CONNECTOR_RESOURCE,
        # `user_id` is required by the API but irrelevant for 2-legged flows
        # (there's no per-user token to look up). A stable agent identifier
        # makes audit logs readable.
        user_id="ada-agent",
    )
    operation = client.retrieve_credentials(request=request)
    response = operation.result(timeout=30)
    return response.token


def lookup_incidents(query: str = "active=true", limit: int = 5) -> dict:
    """Look up ServiceNow incidents matching an encoded query.

    Args:
        query: ServiceNow encoded query string. Examples:
            - "active=true"                                  (all active incidents)
            - "active=true^short_descriptionLIKEcheckout"    (active + matching text)
            - "category=software^state=2"                    (software, in-progress)
        limit: Max incidents to return (default 5).

    Returns:
        {"found": True, "count": N, "incidents": [...]} or {"found": False, ...}
    """
    if not SNOW_INSTANCE_URL:
        return {"found": False, "error": "SNOW_INSTANCE_URL not set in agent env"}

    try:
        snow_token = _fetch_servicenow_token()
    except Exception as exc:  # noqa: BLE001 — surface auth issues clearly to the LLM
        return {
            "found": False,
            "error": f"Could not fetch ServiceNow token from Auth Manager: {exc}",
        }

    url = f"{SNOW_INSTANCE_URL}/api/now/table/incident"
    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {snow_token}",
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
