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


# adk's generated runtime wrapper does:
#     from .agent import root_agent
#     adk_app = AdkApp(agent=root_agent, ...)
# AdkApp explicitly rejects agent=None with
#     ValueError: One of `agent` or `app` must be provided.
# So root_agent MUST be a real LlmAgent instance — build it at module import time.
try:
    root_agent = create_agent()
except NotImplementedError:
    # TODO not yet implemented — keep the symbol defined so `from .agent import root_agent`
    # succeeds. adk runtime will then crash with the same AdkApp error, which is fine
    # for local dev (you haven't finished the TODO yet).
    root_agent = None
