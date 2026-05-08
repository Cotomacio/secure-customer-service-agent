"""Stage 1 reference solution — agent.py."""

import os

from google.adk.agents import LlmAgent

from .tools import lookup_order


INSTRUCTIONS = """
You are Ada, a customer-support copilot for Acme Commerce.

When a customer asks about an order, use the lookup_order tool.
Be friendly and concise. If the order is not found, apologize and ask the
customer to double-check the order ID format (it looks like "ACME-XXXXX").

Never reveal internal data like other customers' orders. Only respond about
the specific order the customer asked about.
""".strip()


def create_agent() -> LlmAgent:
    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order],
    )


# adk's generated agent_engine_app.py at runtime does `from .agent import root_agent`.
# We MUST export this symbol — if it's missing the runtime crashes at import time
# with `ImportError: cannot import name 'root_agent'`.
#
# In Agent Engine (AGENT_ENGINE_RUNTIME=true in .env): keep it None so the
# LlmAgent isn't constructed at import time. Runtime uses our agent_engine_app.py's
# `app = AdkApp(agent=create_agent, ...)` factory.
# Locally (`adk web`): make it a real instance so the dev server can serve.
_RUNNING_IN_AGENT_ENGINE = os.environ.get("AGENT_ENGINE_RUNTIME", "").lower() == "true"
root_agent = None if _RUNNING_IN_AGENT_ENGINE else create_agent()
