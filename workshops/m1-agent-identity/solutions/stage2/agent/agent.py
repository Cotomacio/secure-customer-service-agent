"""Stage 2 reference solution — Ada with order lookup + ServiceNow incidents.

Same Ada as Stage 1 plus one extra tool that calls ServiceNow on the agent's
own authority. The ServiceNow OAuth client lives in Agent Identity Auth
Manager — Ada's code only holds the connector's resource name and uses her
SPIFFE identity to fetch a fresh bearer token per call from
`iamconnectorcredentials.googleapis.com`.

The tool is registered as a plain function tool. The token fetch happens
inside `lookup_incidents` itself (see `tools.py`) — straightforward, no
hidden parameter injection.
"""

from google.adk.agents import LlmAgent

from .tools import lookup_incidents, lookup_order


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
    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order, lookup_incidents],
    )
