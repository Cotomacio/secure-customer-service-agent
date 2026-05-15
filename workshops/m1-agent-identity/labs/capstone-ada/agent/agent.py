"""Capstone Ada — single agent with all four Agent Identity auth flows.

Tool inventory:
  1. lookup_order        — Ada's own SPIFFE identity (Stage 1)
  2. lookup_incidents    — 2LO OAuth via Auth Manager       (Stage 2)
  3. file_github_issue   — 3LO OAuth via Auth Manager       (Stage 3)
  4. get_weather         — API key via Auth Manager         (Stage 4)

Same canonical ADK + Auth Manager wiring across all three Auth Manager-
backed tools. See ../stage2-2lo-servicenow/README.md "How the tool wiring
works" for the contract.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.auth.auth_tool import AuthConfig
from google.adk.integrations.agent_identity import GcpAuthProviderScheme
from google.adk.tools.authenticated_function_tool import AuthenticatedFunctionTool

from .tools import file_github_issue, get_weather, lookup_incidents, lookup_order


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("LOCATION", "us-central1")

SNOW_PROVIDER = os.environ.get("SNOW_PROVIDER_NAME", "snow-incidents")
GH_PROVIDER = os.environ.get("GH_PROVIDER_NAME", "github-3lo")
WEATHER_PROVIDER = os.environ.get("WEATHER_PROVIDER_NAME", "openweather")


def _connector(name: str) -> str:
    return f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/{name}"


INSTRUCTIONS = """
You are Ada, a customer-support copilot for Acme Commerce.

You have four tools:

1. `lookup_order` — find a customer's order by order_id (e.g., "ACME-78214").
   Use this for any customer question about their order status.

2. `lookup_incidents` — check Acme's ServiceNow for active incidents.
   Use this when a customer reports a problem (e.g., "checkout is broken")
   to find out if Acme already knows about it. Pass a ServiceNow encoded
   query, e.g. "active=true^short_descriptionLIKEcheckout".

3. `file_github_issue` — file a bug report on a GitHub repo on behalf of
   the support engineer. Use this when a problem is reproducible and not
   already tracked in ServiceNow. The repo defaults to the one configured
   in env (GH_TEST_REPO).

4. `get_weather` — get current weather at a city. Use this when a customer
   asks about delivery delays related to weather, or when relevant context
   helps explain a late shipment.

Be friendly and concise. When a customer asks a multi-part question, use
multiple tools in parallel. Never invent data: if a tool returns an error
or "found": false, say so honestly rather than making up an answer.
""".strip()


def create_agent() -> LlmAgent:
    snow_tool = AuthenticatedFunctionTool(
        func=lookup_incidents,
        auth_config=AuthConfig(auth_scheme=GcpAuthProviderScheme(name=_connector(SNOW_PROVIDER))),
    )
    gh_tool = AuthenticatedFunctionTool(
        func=file_github_issue,
        auth_config=AuthConfig(auth_scheme=GcpAuthProviderScheme(name=_connector(GH_PROVIDER))),
    )
    weather_tool = AuthenticatedFunctionTool(
        func=get_weather,
        auth_config=AuthConfig(auth_scheme=GcpAuthProviderScheme(name=_connector(WEATHER_PROVIDER))),
    )

    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order, snow_tool, gh_tool, weather_tool],
    )
