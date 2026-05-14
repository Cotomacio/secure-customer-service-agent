"""
Stage 1 — Deploy Ada to Vertex AI Agent Engine with Agent Identity.

The canonical pattern: build the AdkApp in-process and pass it inline to
`client.agent_engines.create(agent=app, config={"identity_type": ...})`.
The SDK pickles the AdkApp and ships it alongside the agent subpackage
in a single operation. Code, identity, and IAM baselines all in one script.

References:
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-identity
  https://docs.cloud.google.com/iam/docs/auth-agent-own-identity
  https://codelabs.developers.google.com/cloudnet-agent-gateway#11
"""

import os
import subprocess
import sys
import time

import vertexai
from vertexai import types
from vertexai.agent_engines import AdkApp

# Make our `agent/` subpackage importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent.agent import create_agent  # noqa: E402


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get(
    "STAGING_BUCKET", f"gs://acme-orders-{PROJECT_ID}-staging"
)


def grant_baseline_iam(agent_identity: str) -> None:
    """Project-scope roles Ada needs to start.

    Bucket-level `roles/storage.objectViewer` is added separately by
    `grant_access.sh` — that's the actual lesson of Stage 1.
    """
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
        if r.returncode == 0:
            print(f"   ✓ {role}")
        else:
            print(f"   ⚠️  failed to grant {role}: {r.stderr.strip()}")
            print(f"      manual fix: gcloud projects add-iam-policy-binding {PROJECT_ID} \\")
            print(f"        --member='{agent_identity}' --role={role} --condition=None")
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
    # Key bits — every one matters and was learned the hard way:
    #   - `google-adk[agent-identity]>=1.31.0`  binds SPIFFE identity at runtime
    #   - `cloudpickle` round-trips the AdkApp through engine staging
    #   - `GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=false`  required for tokens
    #   - `installation_scripts/create_venv.sh` in BOTH extra_packages AND build_options
    #     fixes the base image's compileall PermissionError that otherwise prevents startup
    #     ("failed to start and cannot serve traffic" with no useful logs)
    remote_app = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "ada-stage1",
            "identity_type": types.IdentityType.AGENT_IDENTITY,
            "requirements": [
                "google-cloud-aiplatform[adk,agent_engines]>=1.149.0",
                "google-adk[agent-identity]>=1.31.0",
                "google-cloud-storage>=2.18.0",
                # Both `cloudpickle` and `pydantic` MUST be explicitly listed —
                # the SDK pre-validates requirements and rejects the deploy with
                # `The following requirements are missing: {...}` if either is absent.
                "cloudpickle",
                "pydantic",
            ],
            "staging_bucket": STAGING_BUCKET,
            # `extra_packages` ships the file into the image; `build_options.installation_scripts`
            # tells Agent Engine's build step to EXECUTE it. Both entries are required.
            "extra_packages": ["agent", "installation_scripts/create_venv.sh"],
            "build_options": {
                "installation_scripts": ["installation_scripts/create_venv.sh"],
            },
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
    print("  ✅ Deploy done. Persist these for grant_access.sh:")
    print("=" * 64)
    print(f'\n   export REASONING_ENGINE_ID="{engine_id}"')
    print(f'   export AGENT_IDENTITY="{agent_identity}"')
    print("\nNext: bash grant_access.sh, then adk run-remote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
