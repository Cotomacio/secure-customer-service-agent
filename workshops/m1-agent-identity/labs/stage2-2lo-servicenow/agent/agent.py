"""Stage 2 reference solution — Ada with order lookup + ServiceNow incidents.

Canonical ADK + Agent Identity Auth Manager integration:
  https://github.com/google/adk-python/tree/main/contributing/samples/gcp_auth

The ServiceNow OAuth client lives in an Agent Identity Auth Manager 2LO
connector. ADK's `AuthenticatedFunctionTool` calls `retrieve_credentials`
under the hood and injects the resulting bearer token into the wrapped
function via the `credential` parameter.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.auth.auth_tool import AuthConfig
from google.adk.auth.credential_manager import CredentialManager
from google.adk.integrations.agent_identity import (
    GcpAuthProvider,
    GcpAuthProviderScheme,
)
from google.adk.tools.authenticated_function_tool import AuthenticatedFunctionTool

from .tools import lookup_incidents, lookup_order


# Register Agent Identity Auth Manager as the credential source. Class-level,
# one-shot. Idempotent.
CredentialManager.register_auth_provider(GcpAuthProvider())


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("LOCATION", "us-central1")
SNOW_PROVIDER_NAME = os.environ.get("SNOW_PROVIDER_NAME", "snow-incidents")
SNOW_CONNECTOR_RESOURCE = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/{SNOW_PROVIDER_NAME}"
)


INSTRUCTIONS = """
You are Ada, a customer-support copilot for Acme Commerce.

You have two tools:

1. `lookup_order` — find a customer's order by order_id (e.g., "ACME-78214").
   Use this for any customer question about their order status.

2. `lookup_incidents` — check Acme's ServiceNow for active incidents.
   Use this when a customer reports a problem (e.g., "checkout is broken",
   "I can't see my account") to find out if Acme already knows about it.
   Pass a ServiceNow encoded query, e.g. "active=true^short_descriptionLIKEcheckout".

Be friendly and concise. If both tools are relevant to a customer's question
(e.g., "my order isn't arriving and the site is broken"), use both.
Never reveal another customer's order. Never invent incident numbers.
""".strip()


def create_agent() -> LlmAgent:
    servicenow_tool = AuthenticatedFunctionTool(
        func=lookup_incidents,
        auth_config=AuthConfig(
            auth_scheme=GcpAuthProviderScheme(name=SNOW_CONNECTOR_RESOURCE),
        ),
    )

    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order, servicenow_tool],
    )
