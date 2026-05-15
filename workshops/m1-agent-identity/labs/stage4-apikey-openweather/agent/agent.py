"""Stage 4 — Ada with order lookup + weather (API-key auth provider).

Same Ada as Stage 1 plus a weather tool that uses an Agent Identity Auth
Manager API-key connector. The OpenWeather API key lives in Auth Manager;
Ada's code holds only the connector's resource name and fetches the key
per-call via her SPIFFE identity.
"""

from google.adk.agents import LlmAgent

from .tools import get_weather, lookup_order


INSTRUCTIONS = """
You are Ada, a customer-support copilot for Acme Commerce.

You have two tools:

1. `lookup_order` — find a customer's order by order_id (e.g., "ACME-78214").
   Use this for any customer question about their order status.

2. `get_weather` — get the current weather at a city. Use this when a customer
   asks about delivery delays related to weather, when an order's destination
   city has reported weather issues, or when relevant context (e.g., a customer
   in Denver during winter) helps set expectations.

Be friendly and concise. If a customer asks about a late order to a specific
city, consider checking both the order and the destination weather to give
a complete answer. Never invent weather data.
""".strip()


def create_agent() -> LlmAgent:
    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order, get_weather],
    )
