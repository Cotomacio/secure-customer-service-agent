"""Talk to deployed Stage 3 Ada."""

import os
import sys

import vertexai


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
ENGINE_ID = os.environ["REASONING_ENGINE_ID"]
USER_ID = os.environ.get("USER", "stage3-tester")


def render_event(event: dict) -> None:
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
    default = (
        "File a bug in "
        + os.environ.get("GH_TEST_REPO", "Cotomacio/ada-bug-reports")
        + " titled 'Stage 3 smoke test' with body 'Filed by Ada to verify the GitHub 3LO connector works.'"
    )
    message = sys.argv[1] if len(sys.argv) > 1 else default

    client = vertexai.Client(
        project=PROJECT_ID, location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )
    engine = client.agent_engines.get(
        name=f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}"
    )

    print(f"\n>>> {message}\n")
    for event in engine.stream_query(message=message, user_id=USER_ID):
        render_event(event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
