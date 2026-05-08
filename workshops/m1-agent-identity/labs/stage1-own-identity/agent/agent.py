"""
Stage 1 — Ada agent definition.

The agent has a single tool: lookup_order. The model is gemini-2.5-flash.
The interesting thing is what's NOT in this file: no credentials, no key paths,
no service-account references. Identity comes from the deployment flag in deploy.py.
"""

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
    """Factory function — Agent Engine calls this to instantiate Ada."""
    # TODO(stage1): Build and return the LlmAgent.
    #   - name="ada"
    #   - model="gemini-2.5-flash"
    #   - instruction=INSTRUCTIONS
    #   - tools=[lookup_order]
    #
    # The reference solution is ../../solutions/stage1/agent/agent.py
    raise NotImplementedError("Implement create_agent in agent.py")


# adk's generated agent_engine_app.py at runtime does `from .agent import root_agent`.
# We MUST export this symbol — if it's missing the runtime crashes at import time
# with `ImportError: cannot import name 'root_agent'`.
#
# In Agent Engine (AGENT_ENGINE_RUNTIME=true): keep it None so the LlmAgent
# isn't constructed at import time. Runtime uses our agent_engine_app.py's app.
# Locally (`adk web`): make it a real instance so the dev server can serve.
import os  # noqa: E402

_RUNNING_IN_AGENT_ENGINE = os.environ.get("AGENT_ENGINE_RUNTIME", "").lower() == "true"
try:
    root_agent = None if _RUNNING_IN_AGENT_ENGINE else create_agent()
except NotImplementedError:
    # TODO not yet implemented; keep import succeeding so adk runtime gets a clear
    # crash later instead of an ImportError that's hard to diagnose.
    root_agent = None
