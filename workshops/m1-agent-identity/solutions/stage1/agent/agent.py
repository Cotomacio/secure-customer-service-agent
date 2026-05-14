"""Stage 1 reference solution — agent.py.

The single-step SDK deploy pattern doesn't need a `root_agent` symbol or an
`agent_engine_app.py` wrapper. `deploy.py` calls `create_agent()` in-process
and wraps the result in `AdkApp(agent=...)` which is pickled and shipped.
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
    return LlmAgent(
        name="ada",
        model="gemini-2.5-flash",
        instruction=INSTRUCTIONS,
        tools=[lookup_order],
    )
