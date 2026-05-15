"""Capstone Ada — all four tools.

Each tool demonstrates a different Agent Identity / Auth Manager pattern:

| Tool              | Identity / Auth                          | Credential shape ADK injects                              |
|-------------------|------------------------------------------|-----------------------------------------------------------|
| lookup_order      | Agent's own SPIFFE identity (ADC)        | (no credential param; uses ADC directly)                  |
| lookup_incidents  | 2-legged OAuth via Auth Manager          | credential.http.credentials.token (bearer)                |
| file_github_issue | 3-legged OAuth via Auth Manager          | credential.http.credentials.token (bearer, post-consent)  |
| get_weather       | API key via Auth Manager                 | credential.http.additional_headers["X-API-Key"]           |

All four functions follow the canonical ADK contract:
  - Parameter named `credential` (no underscore) for the LLM-schema strip
  - Read the right field for the connector type (see table above)
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
# Stage 2 tool — ServiceNow incidents via 2-legged OAuth
# ---------------------------------------------------------------------------

SNOW_INSTANCE_URL = os.environ.get("SNOW_INSTANCE_URL", "").rstrip("/")


def lookup_incidents(query: str = "active=true", limit: int = 5, credential=None) -> dict:
    """Look up active ServiceNow incidents matching an encoded query.

    Args:
        query: ServiceNow encoded query (e.g. "active=true^short_descriptionLIKEcheckout").
        limit: Max incidents to return.
        credential: Injected by ADK. 2LO bearer at credential.http.credentials.token.
    """
    if not SNOW_INSTANCE_URL:
        return {"found": False, "error": "SNOW_INSTANCE_URL not set in agent env"}
    if credential is None:
        return {"found": False, "error": "No credential injected"}

    http = getattr(credential, "http", None)
    if not (http and http.credentials and getattr(http.credentials, "token", None)):
        return {"found": False, "error": f"ServiceNow credential missing http.credentials.token: {credential}"}

    headers = {
        "Authorization": f"{http.scheme.title() if http.scheme else 'Bearer'} {http.credentials.token}",
        "Accept": "application/json",
    }
    if getattr(http, "additional_headers", None):
        headers.update(http.additional_headers)

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
        return {"found": False, "error": f"ServiceNow {resp.status_code}: {resp.text[:200]}"}

    result = resp.json().get("result", [])
    return {"found": bool(result), "count": len(result), "incidents": result}


# ---------------------------------------------------------------------------
# Stage 3 tool — GitHub issue creation via 3-legged OAuth
# ---------------------------------------------------------------------------


def file_github_issue(repo: str, title: str, body: str = "", credential=None) -> dict:
    """File a GitHub issue on behalf of the consenting user.

    Args:
        repo: GitHub repo in `owner/name` format (e.g. "Cotomacio/ada-bug-reports").
        title: Issue title (short, descriptive).
        body: Issue body (markdown).
        credential: Injected by ADK. 3LO bearer at credential.http.credentials.token
            (post-consent; user must have authorized the OAuth app once).
    """
    if credential is None:
        return {"found": False, "error": "No credential injected"}

    http = getattr(credential, "http", None)
    if not (http and http.credentials and getattr(http.credentials, "token", None)):
        return {
            "found": False,
            "error": (
                "GitHub credential missing http.credentials.token. "
                "Did you run `python consent_github.py` to authorize Ada first? "
                f"Got: {credential}"
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


# ---------------------------------------------------------------------------
# Stage 4 tool — OpenWeather via API key
# ---------------------------------------------------------------------------


def get_weather(city: str, units: str = "imperial", credential=None) -> dict:
    """Get current weather for a city via OpenWeatherMap.

    Args:
        city: City name (e.g., "Denver", "London,uk").
        units: "imperial" (°F, mph) or "metric" (°C, m/s).
        credential: Injected by ADK. API key at credential.http.additional_headers["X-API-Key"].
    """
    if credential is None:
        return {"found": False, "error": "No credential injected"}

    http = getattr(credential, "http", None)
    headers = getattr(http, "additional_headers", None) if http else None
    api_key = (headers or {}).get("X-API-Key") or (headers or {}).get("X-GOOG-API-KEY")
    if not api_key:
        return {
            "found": False,
            "error": f"Weather credential missing API key in http.additional_headers: {credential}",
        }

    resp = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": city, "appid": api_key, "units": units},
        timeout=15,
    )
    if resp.status_code != 200:
        return {
            "found": False,
            "error": f"OpenWeather returned {resp.status_code}: {resp.text[:200]}",
        }

    data = resp.json()
    main = data.get("main", {})
    weather_list = data.get("weather", [{}])
    return {
        "found": True,
        "city": data.get("name", city),
        "country": data.get("sys", {}).get("country", ""),
        "temp": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "conditions": weather_list[0].get("description", "") if weather_list else "",
        "wind_speed": data.get("wind", {}).get("speed"),
        "units": units,
    }
