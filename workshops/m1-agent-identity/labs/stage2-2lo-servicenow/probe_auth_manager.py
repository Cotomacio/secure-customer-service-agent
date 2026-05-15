"""
Probe the iamconnectorcredentials Python client to figure out exactly which
RetrieveCredentialsRequest shape the API accepts for 2-legged OAuth.

Run from the lab dir with the venv active:
    source .venv/bin/activate
    source ../../.env.local
    python probe_auth_manager.py
"""

import os
import sys

from google.cloud import iamconnectorcredentials_v1alpha


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
PROVIDER = os.environ.get("SNOW_PROVIDER_NAME", "snow-incidents")
CONNECTOR = f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/{PROVIDER}"


def try_combo(label: str, **kwargs) -> None:
    print(f"\n--- {label} ---")
    print(f"    kwargs: {kwargs}")
    client = iamconnectorcredentials_v1alpha.IAMConnectorCredentialsServiceClient()
    request = iamconnectorcredentials_v1alpha.RetrieveCredentialsRequest(
        connector=CONNECTOR, **kwargs
    )
    try:
        op = client.retrieve_credentials(request=request)
    except Exception as e:  # noqa: BLE001
        print(f"    ❌ initial call raised: {type(e).__name__}: {e}")
        return
    try:
        resp = op.result(timeout=15)
    except Exception as e:  # noqa: BLE001
        print(f"    ❌ op.result raised: {type(e).__name__}: {e}")
        # Surface LRO metadata if available
        if hasattr(op, "metadata"):
            try:
                print(f"    metadata: {op.metadata}")
            except Exception:
                pass
        return
    print(f"    ✓ got response: type={type(resp).__name__}")
    if hasattr(resp, "token"):
        print(f"    token length: {len(resp.token or '')}")
    if hasattr(resp, "header"):
        print(f"    header: {resp.header!r}")
    if hasattr(resp, "scopes"):
        print(f"    scopes: {list(resp.scopes)}")


def main() -> int:
    print(f"Connector: {CONNECTOR}")
    print(f"Probing with this account (ADC):")
    import subprocess
    print(f"  {subprocess.check_output(['gcloud','auth','list','--filter=status:ACTIVE','--format=value(account)']).decode().strip()}")

    # Try common 2LO variants
    try_combo("user_id=''",              user_id="")
    try_combo("user_id='ada-agent'",     user_id="ada-agent")
    try_combo("user_id='' + force",      user_id="", force_refresh=True)
    try_combo("user_id='' + scopes",     user_id="", scopes=["useraccount"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
