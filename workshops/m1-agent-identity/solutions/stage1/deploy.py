"""
Stage 1 — Deploy Ada with Agent Identity (canonical single-step SDK pattern).

Source of truth for this pattern:
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-identity
  https://docs.cloud.google.com/iam/docs/auth-agent-own-identity

Why not `adk deploy agent_engine`?
  The ayoisio scaffold uses a two-step `client.agent_engines.create(empty)` +
  `adk deploy agent_engine --agent_engine_id ...` flow. Current adk versions
  generate their own server-side `agent_engine_app.py` that does
  `from .agent import root_agent` and crashes with
  `ValueError: One of 'agent' or 'app' must be provided` if root_agent is None.
  Workarounds for that crash are brittle and adk additionally lies about
  failures by exiting 0. The single-step SDK below sidesteps all of it:
  the AdkApp instance is built in-process and pickled directly.
"""

import os
import subprocess
import sys
import time

import vertexai
from vertexai import types
from vertexai.agent_engines import AdkApp

# Make our `agent/` subpackage importable when running deploy.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent.agent import create_agent  # noqa: E402


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get(
    "STAGING_BUCKET", f"gs://acme-orders-{PROJECT_ID}-staging"
)


def grant_baseline_iam(agent_identity: str) -> None:
    print("Phase 3: granting baseline IAM (project scope)")
    for role in [
        "roles/serviceusage.serviceUsageConsumer",
        "roles/aiplatform.expressUser",
        "roles/browser",
    ]:
        r = subprocess.run(
            [
                "gcloud", "projects", "add-iam-policy-binding", PROJECT_ID,
                f"--member={agent_identity}",
                f"--role={role}",
                "--condition=None",
                "--quiet",
            ],
            capture_output=True, text=True, timeout=60,
        )
        print(f"   {'✓' if r.returncode == 0 else '⚠️'} {role}")
    print("   ⏳ sleeping 30s for IAM propagation")
    time.sleep(30)


def main() -> int:
    print("=" * 64)
    print("  Stage 1 — Ada deploy with Agent Identity (single-step SDK)")
    print("=" * 64)

    print("\nPhase 1: building Ada in-process")
    agent = create_agent()
    app = AdkApp(agent=agent, enable_tracing=True)
    print(f"   ✓ AdkApp wrapping agent name={agent.name}, model={agent.model}")

    print("\nPhase 2: deploying via client.agent_engines.create()")
    print("   → 3–10 min; SDK pickles AdkApp + ships extra_packages in one shot")

    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )

    # Pattern cribbed from https://codelabs.developers.google.com/cloudnet-agent-gateway#11
    remote_app = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "ada-stage1",
            "identity_type": types.IdentityType.AGENT_IDENTITY,
            "requirements": [
                "google-cloud-aiplatform[adk,agent_engines]>=1.149.0",
                "google-adk[agent-identity]>=1.31.0",
                "google-cloud-storage>=2.18.0",
                "cloudpickle",
            ],
            "staging_bucket": STAGING_BUCKET,
            "extra_packages": ["agent"],
            "env_vars": {
                "ORDERS_BUCKET": f"acme-orders-{PROJECT_ID}",
                "GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES": "false",
            },
        },
    )

    engine_id = remote_app.api_resource.name.split("/")[-1]
    effective_identity = remote_app.api_resource.spec.effective_identity
    agent_identity = (
        effective_identity if effective_identity.startswith("principal://")
        else f"principal://{effective_identity}"
    )
    print(f"   ✓ engine id: {engine_id}")
    print(f"   ✓ effective identity: {effective_identity}")

    grant_baseline_iam(agent_identity)

    print("\n" + "=" * 64)
    print("  ✅ Deploy done.")
    print("=" * 64)
    print(f'\n   export REASONING_ENGINE_ID="{engine_id}"')
    print(f'   export AGENT_IDENTITY="{agent_identity}"')
    print("\nNext: bash grant_access.sh, then adk run-remote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
