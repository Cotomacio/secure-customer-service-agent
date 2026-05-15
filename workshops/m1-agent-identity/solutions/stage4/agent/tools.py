"""Stage 4 — Ada tools.

Two tools:

1. `lookup_order` — Stage 1's GCS read via Ada's SPIFFE identity.
2. `get_weather` — calls OpenWeatherMap. The API key lives in an Agent
   Identity Auth Manager API-key connector. ADK's `AuthenticatedFunctionTool`
   fetches it per-call and injects it via the `credential` parameter.

Canonical wiring (same as Stage 2 — see ../stage2.../README.md):
  - Parameter MUST be named `credential` (no underscore) — ADK strips it
    from the LLM schema via `_ignore_params.append("credential")`.
  - Read the secret via `credential.http.credentials.token` per the
    google/adk-python contributing/samples/gcp_auth pattern.
  - `CredentialManager.register_auth_provider(GcpAuthProvider())` lives in
    `agent/__init__.py` so it runs at runtime import.
"""

import csv
import io
import os

import requests
from google.cloud import storage


# ---------------------------------------------------------------------------
# Stage 1 tool — order lookup via GCS using Agent Identity (carries forward)
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
# Stage 4 tool — OpenWeather via API-key auth provider (Auth Manager + ADK)
# ---------------------------------------------------------------------------


def get_weather(city: str, units: str = "imperial", credential=None) -> dict:
    """Get current weather for a city via OpenWeatherMap.

    Args:
        city: City name (e.g., "Denver", "London,uk").
        units: "imperial" (°F, mph) or "metric" (°C, m/s).
        credential: Injected by ADK's AuthenticatedFunctionTool. An
            `AuthCredential` object whose `http.credentials.token` field
            holds the stored API key. Parameter name MUST be `credential`
            (no leading underscore) for the LLM-schema strip to match.

    Returns:
        {"found": True, "city": ..., "temp": ..., ...} or
        {"found": False, "error": "..."}.
    """
    if credential is None:
        return {"found": False, "error": "No credential injected by AuthenticatedFunctionTool"}

    http = getattr(credential, "http", None)
    if not (http and http.credentials and getattr(http.credentials, "token", None)):
        return {"found": False, "error": f"Credential missing http.credentials.token: {credential}"}
    api_key = http.credentials.token

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
