"""
Capstone — Deploy the unified Ada with all four Agent Identity auth flows.

  lookup_order        — own SPIFFE identity → GCS
  lookup_incidents    — 2LO Auth Manager → ServiceNow
  file_github_issue   — 3LO Auth Manager → GitHub (after one-time consent)
  get_weather         — API key Auth Manager → OpenWeather

Same canonical single-step SDK pattern as the per-stage labs.
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

SNOW_INSTANCE_URL = os.environ.get("SNOW_INSTANCE_URL", "").rstrip("/")
SNOW_PROVIDER = os.environ.get("SNOW_PROVIDER_NAME", "snow-incidents")
GH_PROVIDER = os.environ.get("GH_PROVIDER_NAME", "github-3lo")
WEATHER_PROVIDER = os.environ.get("WEATHER_PROVIDER_NAME", "openweather")


def grant_baseline_iam(agent_identity: str) -> None:
    print("Phase 3: granting baseline IAM (project scope)")
    for role in [
        "roles/serviceusage.serviceUsageConsumer",
        "roles/aiplatform.expressUser",
        "roles/browser",
        "roles/iamconnectors.user",  # for all three Auth Manager connectors
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
    print("=" * 68)
    print("  Capstone Ada — all four Agent Identity auth flows")
    print("=" * 68)

    print("\nPhase 1: building Ada in-process")
    agent = create_agent()
    app = AdkApp(agent=agent, enable_tracing=True)
    print(f"   ✓ AdkApp wrapping agent name={agent.name}, model={agent.model}")
    print(f"   ✓ tools: lookup_order, lookup_incidents, file_github_issue, get_weather")

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
            "display_name": "ada-capstone",
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
                "SNOW_INSTANCE_URL": SNOW_INSTANCE_URL,
                "SNOW_PROVIDER_NAME": SNOW_PROVIDER,
                "GH_PROVIDER_NAME": GH_PROVIDER,
                "WEATHER_PROVIDER_NAME": WEATHER_PROVIDER,
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

    print("\n" + "=" * 68)
    print("  ✅ Deploy done. Next steps:")
    print("=" * 68)
    print(f'\n   export REASONING_ENGINE_ID="{engine_id}"')
    print(f'   export AGENT_IDENTITY="{agent_identity}"')
    print()
    print("   bash grant_access.sh                     # bucket read for lookup_order")
    print("   bash setup_servicenow_provider.sh        # 2LO connector for ServiceNow")
    print("   bash setup_github_provider.sh            # 3LO connector for GitHub")
    print("   bash setup_openweather_provider.sh       # API-key connector for OpenWeather")
    print("   python consent_github.py                 # one-time GitHub user consent (3LO)")
    print("   python chat.py                           # demo it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
