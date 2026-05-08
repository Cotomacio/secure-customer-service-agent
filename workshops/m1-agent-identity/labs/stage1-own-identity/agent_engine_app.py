"""
Stage 1 — Agent Engine wrapper.

Required by `adk deploy agent_engine`. Wraps Ada in an AdkApp instance using
LAZY initialization (factory function, not instance) to avoid pickle issues
with the GCS client at import time.

We deliberately do NOT enable tracing here. Under Agent Identity GA, tracing
triggers a resource_manager 401 at startup and Ada fails to serve. M6
Observability shows the right way to re-enable it.
"""

import os

os.environ["AGENT_ENGINE_RUNTIME"] = "true"

from vertexai import agent_engines

from agent import create_agent


app = agent_engines.AdkApp(
    agent=create_agent,
    enable_tracing=False,
)
