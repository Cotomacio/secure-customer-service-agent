"""
One-time user consent helper for the GitHub 3-legged OAuth connector.

3LO recap:
  1. Tool tries to fetch credential → API returns LRO with metadata
     containing `auth_uri` (the user-facing GitHub consent page) and
     `consent_nonce` (we pass back to FinalizeCredential).
  2. User opens auth_uri in browser → authorizes Ada's GitHub OAuth App.
  3. GitHub redirects to `continue_uri?code=...&state=<nonce>`.
  4. Our local http server captures the code → call FinalizeCredential.
  5. Auth Manager stores the access token; future tool calls find it.

Run once per user_id. The authorization persists until the user revokes
the OAuth grant at github.com/settings/applications.
"""

import http.server
import os
import socketserver
import sys
import threading
import time
import webbrowser
from urllib.parse import parse_qs, urlparse

from google.cloud import iamconnectorcredentials_v1alpha as icc


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("LOCATION", "us-central1")
GH_PROVIDER = os.environ.get("GH_PROVIDER_NAME", "github-3lo")
USER_ID = os.environ.get("USER", "ada-engineer")
CONNECTOR = f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/{GH_PROVIDER}"
CALLBACK_PORT = int(os.environ.get("GH_CONSENT_CALLBACK_PORT", "8080"))
CONTINUE_URI = f"http://localhost:{CALLBACK_PORT}/callback"


captured: dict = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return  # silence default access log

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_error(404)
            return
        qs = parse_qs(parsed.query)
        captured["code"] = qs.get("code", [None])[0]
        captured["state"] = qs.get("state", [None])[0]
        captured["error"] = qs.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if captured["error"]:
            self.wfile.write(f"<h1>Error: {captured['error']}</h1>".encode())
        else:
            self.wfile.write(b"""
            <html><body style="font-family: system-ui; padding: 40px;">
            <h1>Ada is now authorized</h1>
            <p>You can close this tab.</p>
            </body></html>""")


def main() -> int:
    print("GitHub 3LO consent helper")
    print(f"  Connector:    {CONNECTOR}")
    print(f"  User ID:      {USER_ID}")
    print(f"  Callback URL: {CONTINUE_URI}")
    print()
    print(
        "Your GitHub OAuth App's 'Authorization callback URL' must include\n"
        f"    {CONTINUE_URI}\n"
        "(https://github.com/settings/developers → your OAuth App → Edit)"
    )
    print()

    client = icc.IAMConnectorCredentialsServiceClient()

    print("→ Initiating credential retrieval (expecting consent_pending)...")
    request = icc.RetrieveCredentialsRequest(
        connector=CONNECTOR,
        user_id=USER_ID,
        continue_uri=CONTINUE_URI,
    )
    operation = client.retrieve_credentials(request=request)

    metadata = operation.metadata
    auth_uri = getattr(metadata, "auth_uri", None) or getattr(metadata, "uri_consent_required", None)
    consent_nonce = getattr(metadata, "consent_nonce", None)
    if not auth_uri or not consent_nonce:
        print("Expected auth_uri + consent_nonce in LRO metadata; got:")
        print(f"   metadata = {metadata}")
        print(f"   (operation = {operation}, done={operation.done()})")
        return 1

    handler_server = socketserver.TCPServer(("0.0.0.0", CALLBACK_PORT), CallbackHandler)
    threading.Thread(target=handler_server.serve_forever, daemon=True).start()
    print(f"→ Listening on {CONTINUE_URI}")

    print(f"\n→ Opening GitHub consent page in your browser:")
    print(f"   {auth_uri}\n")
    try:
        webbrowser.open(auth_uri)
    except Exception:
        pass
    print("   (If the browser didn't open, copy/paste the URL above.)")
    print()
    print("Waiting for you to authorize on GitHub...")

    for _ in range(300):
        if captured.get("code") or captured.get("error"):
            break
        time.sleep(1)
    handler_server.shutdown()

    if captured.get("error"):
        print(f"GitHub returned error: {captured['error']}")
        return 1
    if not captured.get("code"):
        print("Timed out waiting for GitHub callback.")
        return 1
    print(f"✓ Captured authorization code ({len(captured['code'])} chars)")

    print("\n→ Calling FinalizeCredential...")
    finalize_request = icc.FinalizeCredentialRequest(
        name=f"{CONNECTOR}/authorizations/{USER_ID}",
        consent_nonce=consent_nonce,
        code=captured["code"],
    )
    try:
        client.finalize_credential(request=finalize_request)
    except Exception as e:
        print(f"FinalizeCredential failed: {type(e).__name__}: {e}")
        return 1

    print("\n✓ Authorization stored. Ada can now file issues on your behalf.")
    print(f"  Try: python chat.py 'File a test issue in ${os.environ.get('GH_TEST_REPO', '<your-repo>')}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
