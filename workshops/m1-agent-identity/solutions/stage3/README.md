# Stage 3 — Reference solution

Mirrors `labs/stage3-3lo-github/` with the TODOs filled in.

Teaching points to highlight in a debrief:

1. **`agent/tools.py — file_github_issue`.** Same `credential.http.credentials.token` extraction as Stage 2's `lookup_incidents`. The 3LO bearer is structurally identical to a 2LO bearer after consent has been completed.

2. **`agent/__init__.py`.** Same `CredentialManager.register_auth_provider(GcpAuthProvider())` call as Stage 2. The canonical placement that ensures runtime auto-import.

3. **`consent_github.py`.** The 3LO-specific piece. Three sub-steps:
   - Initial `retrieve_credentials` returns LRO with `metadata.auth_uri` + `consent_nonce`
   - Local HTTP server captures `?code=...&state=<nonce>` from GitHub's redirect
   - `FinalizeCredential(consent_nonce, code)` completes the flow

4. **`setup_github_provider.sh`.** Three new `gcloud alpha` flags vs Stage 2: `--three-legged-oauth-authorization-endpoint`, `--three-legged-oauth-token-endpoint`, `--three-legged-oauth-scopes`.

Do not show this folder to attendees during the live lab. Use it for debrief or for self-paced learners who get stuck on the consent flow.
