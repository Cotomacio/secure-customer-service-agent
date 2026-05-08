"""Stage 1 reference solution — agent_engine_app.py."""

import os

os.environ["AGENT_ENGINE_RUNTIME"] = "true"

from vertexai import agent_engines

from .agent import create_agent


app = agent_engines.AdkApp(
    agent=create_agent,
    enable_tracing=False,
)
