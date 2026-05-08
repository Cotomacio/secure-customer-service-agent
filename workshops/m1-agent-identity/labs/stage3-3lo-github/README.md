# Stage 3 — Ada files a GitHub issue on behalf of the engineer (3-legged OAuth)

> *Engineer Pat reviews Ada's findings: "Yes, this is a real bug, file it."*
> Ada must create the GitHub issue **as Pat**, not as herself.

## Why 3-legged?

Stages 1 and 2 had Ada acting on her own authority. Stage 3 is different: Ada acts **on behalf of a specific human user** (Pat). The third party (GitHub) sees Pat's identity. Audit logs show *both* Ada (the agent) and Pat (the user). When Pat leaves the company and her access is revoked at GitHub, Ada immediately stops being able to file issues on her behalf — without Acme touching anything.

This is the most consequential auth flow in M1, and the one with the most moving parts: a consent UI redirect, an LRO with a `consent_nonce`, a callback validation, and a token vault per-user-per-provider.

## Prerequisites

Complete `setup/30_signup_guide.md` § 2 (GitHub OAuth App + test repo) and have these in `.env.local`:

```bash
GH_CLIENT_ID=...
GH_CLIENT_SECRET=...
GH_TEST_REPO=your-username/ada-bug-reports
```

Stages 1 and 2 must be deployed.

## What's in this folder

- `agent.py` — Ada's agent definition with the new GitHub tool
- `tools.py` — `file_github_issue()` wrapping `AuthenticatedFunctionTool` with a 3LO `AuthConfig`
- `frontend_consent.py` — minimal Flask app demonstrating the consent redirect + `FinalizeCredential` callback
- `create_auth_provider.sh` — registers the GitHub 3LO provider
- `requirements.txt`

## Steps

```bash
source ../../.env.local

# 1. Create the 3LO provider in Auth Manager.
#    The script POSTs to iamconnectors.googleapis.com with:
#      authorizationUri = https://github.com/login/oauth/authorize
#      tokenUri = https://github.com/login/oauth/access_token
#      clientId / clientSecret from env
#      scopes: ["public_repo"]
bash create_auth_provider.sh
# It prints the PROVIDER_RESOURCE_NAME and the CALLBACK_URL.

# 2. Update your GitHub OAuth App's "Authorization callback URL" to match
#    the CALLBACK_URL printed above. Save in github.com/settings/developers.

# 3. Implement the TODOs in tools.py and agent.py.

# 4. Run the consent frontend locally (or deploy to Cloud Run for shareable demo).
python frontend_consent.py
# Visit http://localhost:8080 — login as Pat, click "Connect GitHub".
# This drives the LRO -> auth_uri -> consent -> FinalizeCredential cycle.

# 5. Redeploy Ada and ask her to file a bug.
python deploy.py
adk run-remote --reasoning-engine "$REASONING_ENGINE_ID" --user pat@acme.example
> File a bug for issue ACME-78214: "Checkout 500 on Safari iOS 17.4"
```

## The consent flow, step by step

1. Pat asks Ada to file a bug.
2. Ada calls `iamconnectors.connectors.retrieveCredentials` for the `github-3lo` provider, scoped to user `pat@acme.example`.
3. Auth Manager returns an **LRO**. Metadata: `auth_uri`, `consent_nonce`.
4. The frontend intercepts the `adk_request_credential` callback, redirects Pat's browser to `auth_uri`.
5. Pat clicks **Authorize** on GitHub's consent page.
6. GitHub redirects to `<callback_url>?code=...&state=<user_id_validation_state>`.
7. The frontend's callback handler calls `FinalizeCredential` with the `consent_nonce` + Pat's user ID.
8. Auth Manager exchanges the `code` with GitHub's token endpoint, gets back Pat's access token + refresh token, encrypts them, stores in the vault under `(provider=github-3lo, user=pat)`.
9. Pat is redirected back to Ada with credentials now provisioned.
10. Ada retries `retrieveCredentials` — this time it succeeds. Auth Manager injects Pat's bearer token into the outbound `POST /repos/.../issues` call server-side; Ada's process never holds the token.

## Verify

1. **Functional:** the GitHub issue exists in `${GH_TEST_REPO}` and is authored by Pat (not by a service account, not by Ada).
2. **Audit:** Cloud Logs for the `iamconnectors.connectors.retrieveCredentials` call show Ada's SPIFFE ID *and* `pat@acme.example` as the on-behalf-of subject.
3. **No-token-in-Ada check:** Ada's runtime never logs the GitHub access token. The token is decrypted only inside Auth Manager's runtime, server-side.
4. **Revocation drill (the showstopper demo):** Pat goes to `github.com/settings/applications` and revokes the Acme app. Ask Ada to file another bug. Ada gets a fresh LRO — consent flow re-triggers. **This is what "user is in control" looks like.**

> 🔭 **Coming in M6:** the **Usage** tab pivots by 3LO end-user, so you can answer *"which support engineers is Ada actually filing bugs on behalf of?"* — and spot anomalies like one engineer's identity suddenly filing 200x more issues than usual.

## Threats closed

- **T4** (no GitHub client secret in agent or image)
- **T5** (Pat's user token never reaches Ada's code; server-side decryption only — Auth Manager runtime is the only place the plaintext token exists)
- **T7** (audit trail shows Ada + Pat together)

## What's still exposed

- **T9 — over-scoped consent.** If you registered with `repo` instead of `public_repo`, Auth Manager won't object. Scope review is process control, addressed in M4.
- A revoked GitHub grant breaks Ada silently — design `FinalizeCredential` failure handling. Hint: re-trigger the LRO, don't error to the user.

## Status of this scaffold

Solution files deferred. The README is the spec. The frontend consent app is the trickiest piece — when generated, it should be ~80 LOC of Flask + a single `FinalizeCredential` HTTP call. Workshop owner: validate the GitHub OAuth scope choice (`public_repo` vs `repo`) before code-gen.
