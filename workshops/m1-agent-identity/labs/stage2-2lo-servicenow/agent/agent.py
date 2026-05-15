"""Stage 2 reference solution — Ada with order lookup + ServiceNow incidents.

Same Ada as Stage 1, with one additional tool. The new tool is wrapped in
ADK's `AuthenticatedFunctionTool` and bound to a 2-legged OAuth provider
in Agent Identity Auth Manager. The ServiceNow client_id and client_secret
live in Auth Manager — Ada's process holds only the provider's resource name.
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


# Register Agent Identity Auth Manager as the credential source. Idempotent.
CredentialManager.register_auth_provider(GcpAuthProvider())


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
SNOW_PROVIDER_NAME = os.environ.get("SNOW_PROVIDER_NAME", "snow-incidents")
SNOW_PROVIDER_RESOURCE = (
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
    # The ServiceNow tool wraps `lookup_incidents` in AuthenticatedFunctionTool
    # so the ADK runtime fetches the bearer token from Auth Manager at call time
    # and injects it as `_credential` into the function.
    servicenow_tool = AuthenticatedFunctionTool(
        func=lookup_incidents,
        auth_config=AuthConfig(
            auth_scheme=GcpAuthProviderScheme(name=SNOW_PROVIDER_RESOURCE),
        ),
    )

    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order, servicenow_tool],
    )
