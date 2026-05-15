"""Stage 4 — Ada tools.

Two tools wired in:

1. `lookup_order` — same as Stage 1, reads `orders.csv` from GCS using Ada's
   own SPIFFE identity (ADC at runtime).
2. `get_weather` — calls OpenWeatherMap for the current weather at a city.
   Authenticates via an Agent Identity Auth Manager API-key connector: the
   function asks the iamconnectorcredentials API for the stored API key
   at every call (using Ada's SPIFFE identity), then uses the key as a
   query param on the OpenWeather request. The API key lives in Auth
   Manager — never in agent source or runtime.
"""

import csv
import io
import os

import requests
from google.cloud import iamconnectorcredentials_v1alpha, storage


# ---------------------------------------------------------------------------
# Stage 1 tool — order lookup via GCS using Agent Identity (carries forward)
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
# Stage 4 tool — OpenWeatherMap via API-key auth provider (Auth Manager)
# ---------------------------------------------------------------------------

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("LOCATION", "us-central1")
WEATHER_PROVIDER_NAME = os.environ.get("WEATHER_PROVIDER_NAME", "openweather")
WEATHER_CONNECTOR_RESOURCE = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/{WEATHER_PROVIDER_NAME}"
)


def _fetch_openweather_api_key() -> str:
    """Fetch the OpenWeather API key from Agent Identity Auth Manager.

    Uses the agent's SPIFFE identity (via ADC) to authenticate to the
    iamconnectorcredentials API. Returns the stored API key. The key lives
    in Auth Manager — Ada's process holds only the connector's resource name.
    """
    client = iamconnectorcredentials_v1alpha.IAMConnectorCredentialsServiceClient()
    request = iamconnectorcredentials_v1alpha.RetrieveCredentialsRequest(
        connector=WEATHER_CONNECTOR_RESOURCE,
        user_id="ada-agent",
    )
    operation = client.retrieve_credentials(request=request)
    response = operation.result(timeout=30)
    return response.token


def get_weather(city: str, units: str = "imperial") -> dict:
    """Get current weather for a city via OpenWeatherMap.

    Args:
        city: City name (e.g., "Denver", "London,uk").
        units: "imperial" (°F, mph) or "metric" (°C, m/s). Default imperial.

    Returns:
        {"found": True, "city": ..., "temp": ..., "conditions": ..., ...}
        or {"found": False, "error": "..."} on failure.
    """
    try:
        api_key = _fetch_openweather_api_key()
    except Exception as exc:  # noqa: BLE001
        return {
            "found": False,
            "error": f"Could not fetch OpenWeather API key from Auth Manager: {exc}",
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
