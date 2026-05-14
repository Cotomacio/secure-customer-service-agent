"""
Talk to deployed Ada via the v1beta1 SDK's stream_query API.

`adk run-remote` does not exist in current adk; this script is the supported
path for talking to a deployed Agent Engine from the command line.

Usage:
    export REASONING_ENGINE_ID=...
    python chat.py                              # default Stage 1 test prompt
    python chat.py "your custom message"
"""

import os
import sys

import vertexai


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
ENGINE_ID = os.environ["REASONING_ENGINE_ID"]
USER_ID = os.environ.get("USER", "stage1-tester")


def render_event(event: dict) -> None:
    """Pull the meaningful bits out of an AdkApp streaming event."""
    if not isinstance(event, dict):
        print(event)
        return
    content = event.get("content") or {}
    for part in content.get("parts", []):
        if part.get("text"):
            print(part["text"])
        elif "function_call" in part:
            fc = part["function_call"]
            print(f"  ↪ calling tool: {fc.get('name')}({fc.get('args')})")
        elif "function_response" in part:
            fr = part["function_response"]
            print(f"  ↩ tool result:  {fr.get('response')}")


def main() -> int:
    message = sys.argv[1] if len(sys.argv) > 1 else "Where is order ACME-78214?"

    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )
    engine = client.agent_engines.get(
        name=(
            f"projects/{PROJECT_ID}/locations/{LOCATION}"
            f"/reasoningEngines/{ENGINE_ID}"
        )
    )

    print(f"\n>>> {message}\n")
    for event in engine.stream_query(message=message, user_id=USER_ID):
        render_event(event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
