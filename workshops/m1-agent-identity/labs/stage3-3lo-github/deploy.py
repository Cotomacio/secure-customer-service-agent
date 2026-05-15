"""Stage 3 — Deploy Ada with Agent Identity + GitHub 3LO.

Same canonical single-step SDK pattern as Stages 1/2/4. The GitHub
client_id/secret live in an Agent Identity Auth Manager 3LO connector;
Ada's source holds only the connector resource name. User consent (one-
time) creates an authorization record that future tool calls reuse.
"""

import os
import subprocess
import sys
import time

import vertexai
from vertexai import types
from vertexai.agent_engines import AdkApp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent.agent import create_agent  # noqa: E402


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET", f"gs://acme-orders-{PROJECT_ID}-staging")
GH_PROVIDER_NAME = os.environ.get("GH_PROVIDER_NAME", "github-3lo")


def grant_baseline_iam(agent_identity: str) -> None:
    print("Phase 3: granting baseline IAM (project scope)")
    for role in [
        "roles/serviceusage.serviceUsageConsumer",
        "roles/aiplatform.expressUser",
        "roles/browser",
        "roles/iamconnectors.user",
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
    print("  Stage 3 — Ada deploy with Agent Identity + GitHub 3LO")
    print("=" * 64)

    print("\nPhase 1: building Ada in-process")
    agent = create_agent()
    app = AdkApp(agent=agent, enable_tracing=True)
    print(f"   ✓ AdkApp wrapping agent name={agent.name}, model={agent.model}")
    print(f"   ✓ tools: lookup_order, file_github_issue (auth_provider={GH_PROVIDER_NAME})")

    print("\nPhase 2: deploying via client.agent_engines.create()")
    print("   → 3–10 min")

    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )

    remote_app = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "ada-stage3",
            "identity_type": types.IdentityType.AGENT_IDENTITY,
            "requirements": [
                "google-cloud-aiplatform[adk,agent_engines]>=1.149.0",
                "google-adk[agent-identity]>=1.31.0",
                "google-cloud-storage>=2.18.0",
                "cloudpickle",
                "pydantic",
                "requests>=2.32.0",
            ],
            "staging_bucket": STAGING_BUCKET,
            "extra_packages": ["agent", "installation_scripts/create_venv.sh"],
            "build_options": {"installation_scripts": ["installation_scripts/create_venv.sh"]},
            "env_vars": {
                "ORDERS_BUCKET": f"acme-orders-{PROJECT_ID}",
                "GH_PROVIDER_NAME": GH_PROVIDER_NAME,
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
    print("  ✅ Deploy done. Next:")
    print("=" * 64)
    print(f'\n   export REASONING_ENGINE_ID="{engine_id}"')
    print(f'   export AGENT_IDENTITY="{agent_identity}"')
    print("\n   bash grant_access.sh             # bucket read for lookup_order")
    print("   bash setup_github_provider.sh    # 3LO connector for GitHub")
    print("   python consent_github.py         # one-time browser consent")
    print("   python chat.py 'File a bug ...' ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
