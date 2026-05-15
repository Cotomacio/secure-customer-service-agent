"""Stage 3 — Ada tools.

Two tools:

1. `lookup_order` — Stage 1's GCS read via Ada's SPIFFE identity (carries
   forward so we can prove Stage 3 doesn't break prior behavior).
2. `file_github_issue` — files a GitHub issue **on behalf of the consenting
   user** via a 3-legged OAuth connector in Agent Identity Auth Manager.
   The user must run `consent_github.py` once before Ada can call this.
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
    """Look up an Acme Commerce order by its ID."""
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
# Stage 3 tool — file GitHub issue on behalf of consenting user (3LO)
# ---------------------------------------------------------------------------


def file_github_issue(repo: str, title: str, body: str = "", credential=None) -> dict:
    """File a GitHub issue on behalf of the consenting user.

    Args:
        repo: GitHub repo in `owner/name` format (e.g. "Cotomacio/ada-bug-reports").
        title: Issue title (short, descriptive).
        body: Issue body (markdown).
        credential: Injected by ADK's AuthenticatedFunctionTool. Post-consent,
            the 3LO bearer is at credential.http.credentials.token.

    Returns:
        {"found": True, "issue_number": N, "url": "...", "author": "..."} on success,
        {"found": False, "error": "..."} otherwise.
    """
    if credential is None:
        return {"found": False, "error": "No credential injected by AuthenticatedFunctionTool"}

    http = getattr(credential, "http", None)
    if not (http and http.credentials and getattr(http.credentials, "token", None)):
        return {
            "found": False,
            "error": (
                "GitHub credential missing http.credentials.token. The user "
                "may not have completed consent yet. Run `python consent_github.py` "
                f"once to authorize. Got: {credential}"
            ),
        }

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {http.credentials.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": title, "body": body},
        timeout=15,
    )
    if resp.status_code != 201:
        return {
            "found": False,
            "error": f"GitHub returned {resp.status_code}: {resp.text[:200]}",
        }

    data = resp.json()
    return {
        "found": True,
        "issue_number": data["number"],
        "url": data["html_url"],
        "title": data["title"],
        "author": data.get("user", {}).get("login", "?"),
    }
