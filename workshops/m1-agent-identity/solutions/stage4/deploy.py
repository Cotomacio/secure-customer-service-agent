"""
Stage 4 — Deploy Ada with Agent Identity + OpenWeather API key (Auth Manager).

Same canonical single-step SDK pattern as Stages 1–2. The agent has two tools:
  - lookup_order        (Stage 1's GCS read; carries forward)
  - get_weather         (new: OpenWeather REST via API-key auth provider)

The OpenWeather API key never reaches the agent's container. It lives in an
Agent Identity Auth Manager connector; the tool fetches it per-call via
iamconnectorcredentials.

References:
  https://docs.cloud.google.com/iam/docs/auth-with-api-key
  https://docs.cloud.google.com/iam/docs/agent-identity-overview
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
STAGING_BUCKET = os.environ.get(
    "STAGING_BUCKET", f"gs://acme-orders-{PROJECT_ID}-staging"
)
WEATHER_PROVIDER_NAME = os.environ.get("WEATHER_PROVIDER_NAME", "openweather")


def grant_baseline_iam(agent_identity: str) -> None:
    print("Phase 3: granting baseline IAM (project scope)")
    for role in [
        "roles/serviceusage.serviceUsageConsumer",
        "roles/aiplatform.expressUser",
        "roles/browser",
        "roles/iamconnectors.user",  # for retrieve_credentials on the API-key connector
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
    print("  Stage 4 — Ada deploy with Agent Identity + OpenWeather API key")
    print("=" * 64)

    print("\nPhase 1: building Ada in-process")
    agent = create_agent()
    app = AdkApp(agent=agent, enable_tracing=True)
    print(f"   ✓ AdkApp wrapping agent name={agent.name}, model={agent.model}")
    print(f"   ✓ tools: lookup_order, get_weather (auth_provider={WEATHER_PROVIDER_NAME})")

    print("\nPhase 2: deploying via client.agent_engines.create()")
    print("   → 3–10 min; SDK pickles AdkApp + ships extra_packages in one shot")

    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )

    remote_app = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "ada-stage4",
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
            "build_options": {
                "installation_scripts": ["installation_scripts/create_venv.sh"],
            },
            "env_vars": {
                "ORDERS_BUCKET": f"acme-orders-{PROJECT_ID}",
                "WEATHER_PROVIDER_NAME": WEATHER_PROVIDER_NAME,
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
    print("\n   bash grant_access.sh                # bucket read for lookup_order")
    print("   bash setup_openweather_provider.sh  # create+bind the OpenWeather API-key provider")
    print("   python chat.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
