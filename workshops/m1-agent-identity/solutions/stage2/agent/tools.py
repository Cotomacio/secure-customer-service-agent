"""Stage 2 reference solution — tools.

Two tools wired in:

1. `lookup_order` — same as Stage 1, reads `orders.csv` from GCS using Ada's
   own SPIFFE identity (ADC at runtime).
2. `lookup_incidents` — calls ServiceNow's REST API for active incidents.
   Authenticates via Agent Identity Auth Manager's 2-legged OAuth flow.
   The tool is wrapped in `AuthenticatedFunctionTool`; ADK calls
   `retrieve_credentials` and injects the resulting bearer token via the
   `credential` parameter at call time. The ServiceNow client_id and
   client_secret live in Auth Manager — never in agent source or runtime.

Canonical pattern: https://github.com/google/adk-python/tree/main/contributing/samples/gcp_auth
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
    client = storage.Client()
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
# Stage 2 tool — ServiceNow via 2-legged OAuth (Auth Manager + ADK)
# ---------------------------------------------------------------------------

SNOW_INSTANCE_URL = os.environ.get("SNOW_INSTANCE_URL", "").rstrip("/")


def lookup_incidents(query: str = "active=true", limit: int = 5, credential=None) -> dict:
    """Look up ServiceNow incidents matching an encoded query.

    Args:
        query: ServiceNow encoded query string. Examples:
            - "active=true"                                  (all active incidents)
            - "active=true^short_descriptionLIKEcheckout"    (active + matching text)
            - "category=software^state=2"                    (software, in-progress)
        limit: Max incidents to return (default 5).
        credential: Injected by ADK's AuthenticatedFunctionTool. An
            `AuthCredential` object with the OAuth bearer token. Note:
            parameter name MUST be `credential` (no leading underscore)
            so ADK strips it from the Gemini function declaration.

    Returns:
        {"found": True, "count": N, "incidents": [...]} or {"found": False, ...}
    """
    if not SNOW_INSTANCE_URL:
        return {"found": False, "error": "SNOW_INSTANCE_URL not set in agent env"}
    if credential is None:
        return {"found": False, "error": "No credential injected by AuthenticatedFunctionTool"}

    # Extract the bearer token from the AuthCredential. Per the canonical
    # adk-python contributing/samples/gcp_auth pattern: read from credential.http.
    headers = {"Accept": "application/json"}
    http = getattr(credential, "http", None)
    if http and http.scheme and http.credentials and getattr(http.credentials, "token", None):
        headers["Authorization"] = f"{http.scheme.title()} {http.credentials.token}"
        # Some providers add extra headers (e.g. signed JWTs)
        if getattr(http, "additional_headers", None):
            headers.update(http.additional_headers)
    else:
        return {"found": False, "error": f"Credential missing http.credentials.token: {credential}"}

    resp = requests.get(
        f"{SNOW_INSTANCE_URL}/api/now/table/incident",
        headers=headers,
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
