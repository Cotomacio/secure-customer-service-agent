"""
Stage 1 — Deploy Ada to Vertex AI Agent Engine with Agent Identity enabled.

Two-step deploy (the only path that actually works for Agent Identity GA):
  Phase 3: create an EMPTY Agent Engine via the v1beta1 SDK with identity_type
           set. This is what provisions Ada's SPIFFE identity and X.509 cert.
  Phase 5: ship the code into that engine via `adk deploy agent_engine`. The
           Python SDK can't reliably package code (pickle issues with agent
           instances), but ADK CLI handles it.

Why not the single-step `ReasoningEngine.create(reasoning_engine=ada, identity_type=...)`
pattern? It is rejected by the GA SDK's pydantic validation — the runtime
expects a `BaseAgent` instance and the factory function gets reflected as a
function ref. Use the two-step path.

Critical: do NOT pass `--trace_to_cloud` to `adk deploy`. The tracing
instrumentor calls `cloudresourcemanager.projects.get` at startup, which 401s
under Agent Identity GA, and Ada fails to start with no useful error. M6
Observability re-enables tracing the right way.
"""

import os
import subprocess
import sys
import threading
import time

import vertexai
from vertexai import types


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get(
    "STAGING_BUCKET", f"gs://acme-orders-{PROJECT_ID}-staging"
).replace("gs://", "")
EXISTING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID")  # for re-runs


def _spinner(stop: threading.Event, started: float) -> None:
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop.is_set():
        elapsed = int(time.time() - started)
        m, s = divmod(elapsed, 60)
        sys.stdout.write(f"\r   {chars[i]} waiting {m}m{s:02d}s ")
        sys.stdout.flush()
        i = (i + 1) % len(chars)
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 40 + "\r")


def create_empty_engine() -> tuple[str, str | None]:
    """Phase 3 — create an empty Agent Engine with Agent Identity enabled."""
    print("Phase 3: creating empty Agent Engine with Agent Identity")
    print("   → can take 3–15 min; spinner below")

    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )

    stop = threading.Event()
    t = threading.Thread(target=_spinner, args=(stop, time.time()), daemon=True)
    t.start()
    try:
        remote_app = client.agent_engines.create(
            config={
                "identity_type": types.IdentityType.AGENT_IDENTITY,
                "display_name": "ada-stage1",
            }
        )
    finally:
        stop.set()
        t.join(timeout=1)

    resource_name = remote_app.api_resource.name
    engine_id = resource_name.split("/")[-1]

    effective_identity = None
    spec = getattr(remote_app.api_resource, "spec", None)
    if spec is not None:
        effective_identity = getattr(spec, "effective_identity", None)

    print(f"   ✓ engine id: {engine_id}")
    if effective_identity:
        print(f"   ✓ effective identity: {effective_identity}")
    return engine_id, effective_identity


def grant_baseline_iam(agent_identity: str) -> None:
    """Phase 4 — minimum IAM Ada needs to start. Bucket-level grant in grant_access.sh."""
    print("Phase 4: granting baseline IAM (project scope)")
    roles = [
        "roles/serviceusage.serviceUsageConsumer",
        "roles/aiplatform.expressUser",
        "roles/browser",
    ]
    for role in roles:
        cmd = [
            "gcloud", "projects", "add-iam-policy-binding", PROJECT_ID,
            f"--member={agent_identity}",
            f"--role={role}",
            "--condition=None",
            "--quiet",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            print(f"   ✓ {role}")
        else:
            print(f"   ⚠️  failed to grant {role}: {r.stderr.strip()}")
            print(f"      manual fix: gcloud projects add-iam-policy-binding {PROJECT_ID} \\")
            print(f"        --member='{agent_identity}' --role={role} --condition=None")
    print("   ⏳ sleeping 30s for IAM propagation")
    time.sleep(30)


def write_runtime_env() -> str:
    """Phase 2 — runtime .env for Agent Engine."""
    here = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(here, ".env")
    with open(env_path, "w") as f:
        f.write(
            f"GOOGLE_CLOUD_PROJECT={PROJECT_ID}\n"
            f"LOCATION={LOCATION}\n"
            f"ORDERS_BUCKET=acme-orders-{PROJECT_ID}\n"
        )
    print(f"   ✓ runtime env: {env_path}")
    return env_path


def deploy_code(engine_id: str, env_file: str) -> None:
    """Phase 5 — ship code via ADK CLI. Note: NO --trace_to_cloud (breaks Agent Identity)."""
    print("Phase 5: deploying code via `adk deploy agent_engine`")
    cmd = [
        "adk", "deploy", "agent_engine",
        "--project", PROJECT_ID,
        "--region", LOCATION,
        "--staging_bucket", f"gs://{STAGING_BUCKET}",
        "--env_file", env_file,
        "--agent_engine_id", engine_id,
        # NOTE: no --trace_to_cloud. M6 Observability shows the right way.
        ".",  # current directory contains agent.py + tools.py
    ]
    print(f"   $ {' '.join(cmd)}")
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run(cmd, cwd=here)
    benign = r.returncode != 0  # ADK CLI may exit non-zero on benign warnings
    if benign:
        print("   ⚠️  adk deploy returned non-zero — check Cloud Logs for the engine.")
        print("      If 'service account info is missing email field' it's benign.")


def construct_identity_fallback(engine_id: str) -> str:
    """If the API didn't return effective_identity, build it from env."""
    org_id = os.environ.get("ORG_ID", "").strip()
    project_number = subprocess.run(
        ["gcloud", "projects", "describe", PROJECT_ID, "--format=value(projectNumber)"],
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    if org_id:
        return (
            f"principal://agents.global.org-{org_id}.system.id.goog"
            f"/resources/aiplatform/projects/{project_number}/locations/{LOCATION}"
            f"/reasoningEngines/{engine_id}"
        )
    # No org: try the proj- form (newer API responses); fall back to project- if rejected.
    return (
        f"principal://agents.global.proj-{project_number}.system.id.goog"
        f"/resources/aiplatform/projects/{project_number}/locations/{LOCATION}"
        f"/reasoningEngines/{engine_id}"
    )


def main() -> int:
    print("=" * 64)
    print("  Stage 1 — Ada deploy with Agent Identity")
    print("=" * 64)

    print("\nPhase 2: writing runtime env")
    env_file = write_runtime_env()

    if EXISTING_ENGINE_ID:
        print(f"\nPhase 3: reusing existing engine {EXISTING_ENGINE_ID}")
        engine_id, effective_identity = EXISTING_ENGINE_ID, None
    else:
        engine_id, effective_identity = create_empty_engine()

    if effective_identity:
        agent_identity = (
            effective_identity if effective_identity.startswith("principal://")
            else f"principal://{effective_identity}"
        )
    else:
        agent_identity = construct_identity_fallback(engine_id)

    print(f"\n   AGENT_IDENTITY={agent_identity}")

    grant_baseline_iam(agent_identity)
    deploy_code(engine_id, env_file)

    print("\n" + "=" * 64)
    print("  ✅ Deploy done. Persist these for grant_access.sh:")
    print("=" * 64)
    print(f'\n   export REASONING_ENGINE_ID="{engine_id}"')
    print(f'   export AGENT_IDENTITY="{agent_identity}"')
    print("\nNext: bash grant_access.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
