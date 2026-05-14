"""
Stage 1 — Ada agent definition.

The agent has a single tool: lookup_order. The model is gemini-2.5-flash.
The interesting thing is what's NOT in this file: no credentials, no key paths,
no service-account references. Identity comes from `deploy.py`'s
`identity_type=AGENT_IDENTITY` flag.

Single-step SDK deploy doesn't need a `root_agent` symbol or
`agent_engine_app.py` — `deploy.py` calls `create_agent()` directly,
wraps it in AdkApp, and ships the whole thing pickled.
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
    """Factory function — `deploy.py` calls this to instantiate Ada."""
    # TODO(stage1): Build and return the LlmAgent.
    #   - name="ada"
    #   - model="gemini-2.5-flash"
    #   - instruction=INSTRUCTIONS
    #   - tools=[lookup_order]
    #
    # The reference solution is ../../solutions/stage1/agent/agent.py
    raise NotImplementedError("Implement create_agent in agent.py")
