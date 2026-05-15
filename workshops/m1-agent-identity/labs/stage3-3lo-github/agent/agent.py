"""Stage 3 — Ada with order lookup + GitHub issue filing (3LO).

Same canonical ADK + Auth Manager wiring as Stage 2; only the connector
type differs (3LO with user consent vs 2LO machine-to-machine).
"""

import os

from google.adk.agents import LlmAgent
from google.adk.auth.auth_tool import AuthConfig
from google.adk.integrations.agent_identity import GcpAuthProviderScheme
from google.adk.tools.authenticated_function_tool import AuthenticatedFunctionTool

from .tools import file_github_issue, lookup_order


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("LOCATION", "us-central1")
GH_PROVIDER_NAME = os.environ.get("GH_PROVIDER_NAME", "github-3lo")
GH_CONNECTOR_RESOURCE = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/{GH_PROVIDER_NAME}"
)


INSTRUCTIONS = """
You are Ada, a customer-support copilot for Acme Commerce.

You have two tools:

1. `lookup_order` — find a customer's order by order_id (e.g., "ACME-78214").

2. `file_github_issue` — file a bug report on a GitHub repo on behalf of
   the support engineer. Use this when a customer reports a reproducible
   bug. The `repo` argument is in `owner/name` format. Compose a clear
   title and a body that quotes the customer's report.

Be friendly and concise. Never invent issue numbers. If a tool returns
an error or "found": false, say so honestly.
""".strip()


def create_agent() -> LlmAgent:
    github_tool = AuthenticatedFunctionTool(
        func=file_github_issue,
        auth_config=AuthConfig(
            auth_scheme=GcpAuthProviderScheme(name=GH_CONNECTOR_RESOURCE),
        ),
    )

    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order, github_tool],
    )
