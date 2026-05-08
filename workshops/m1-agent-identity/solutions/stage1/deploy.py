"""Stage 1 reference solution — deploy.py.

Mirrors labs/stage1-own-identity/deploy.py exactly — there are no TODOs in
deploy.py. The teaching is in the structure (two-step deploy, no tracing,
expressUser baseline) not in fill-in-the-blanks.
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
EXISTING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID")


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
    print("Phase 3: creating empty Agent Engine with Agent Identity")
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
    engine_id = remote_app.api_resource.name.split("/")[-1]
    spec = getattr(remote_app.api_resource, "spec", None)
    effective_identity = getattr(spec, "effective_identity", None) if spec else None
    print(f"   ✓ engine id: {engine_id}")
    if effective_identity:
        print(f"   ✓ effective identity: {effective_identity}")
    return engine_id, effective_identity


def grant_baseline_iam(agent_identity: str) -> None:
    print("Phase 4: granting baseline IAM (project scope)")
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


def write_runtime_env() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(here, ".env")
    with open(env_path, "w") as f:
        f.write(
            f"GOOGLE_CLOUD_PROJECT={PROJECT_ID}\n"
            f"LOCATION={LOCATION}\n"
            f"ORDERS_BUCKET=acme-orders-{PROJECT_ID}\n"
        )
    return env_path


def deploy_code(engine_id: str, env_file: str) -> None:
    print("Phase 5: deploying code via `adk deploy agent_engine`")
    cmd = [
        "adk", "deploy", "agent_engine",
        "--project", PROJECT_ID,
        "--region", LOCATION,
        "--staging_bucket", f"gs://{STAGING_BUCKET}",
        "--env_file", env_file,
        "--agent_engine_id", engine_id,
        ".",
    ]
    here = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(cmd, cwd=here)


def construct_identity_fallback(engine_id: str) -> str:
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
    return (
        f"principal://agents.global.proj-{project_number}.system.id.goog"
        f"/resources/aiplatform/projects/{project_number}/locations/{LOCATION}"
        f"/reasoningEngines/{engine_id}"
    )


def main() -> int:
    env_file = write_runtime_env()
    if EXISTING_ENGINE_ID:
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
    grant_baseline_iam(agent_identity)
    deploy_code(engine_id, env_file)
    print(f'\nexport REASONING_ENGINE_ID="{engine_id}"')
    print(f'export AGENT_IDENTITY="{agent_identity}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
