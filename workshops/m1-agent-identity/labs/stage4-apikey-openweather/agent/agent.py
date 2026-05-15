"""Stage 4 — Ada with order lookup + weather via API-key Auth Manager connector.

Same canonical ADK + Auth Manager wiring as Stage 2 — only the connector
type differs (API key vs 2LO).
"""

import os

from google.adk.agents import LlmAgent
from google.adk.auth.auth_tool import AuthConfig
from google.adk.integrations.agent_identity import GcpAuthProviderScheme
from google.adk.tools.authenticated_function_tool import AuthenticatedFunctionTool

from .tools import get_weather, lookup_order


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("LOCATION", "us-central1")
WEATHER_PROVIDER_NAME = os.environ.get("WEATHER_PROVIDER_NAME", "openweather")
WEATHER_CONNECTOR_RESOURCE = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/{WEATHER_PROVIDER_NAME}"
)


INSTRUCTIONS = """
You are Ada, a customer-support copilot for Acme Commerce.

You have two tools:

1. `lookup_order` — find a customer's order by order_id (e.g., "ACME-78214").
   Use this for any customer question about their order status.

2. `get_weather` — get the current weather at a city. Use this when a customer
   asks about delivery delays related to weather, or when relevant context
   (e.g., a customer in Denver during winter) helps set expectations.

Be friendly and concise. If a customer asks about a late order to a specific
city, consider checking both the order and the destination weather.
Never invent weather data.
""".strip()


def create_agent() -> LlmAgent:
    weather_tool = AuthenticatedFunctionTool(
        func=get_weather,
        auth_config=AuthConfig(
            auth_scheme=GcpAuthProviderScheme(name=WEATHER_CONNECTOR_RESOURCE),
        ),
    )

    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order, weather_tool],
    )
