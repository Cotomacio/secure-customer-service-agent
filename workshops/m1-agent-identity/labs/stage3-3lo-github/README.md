# Stage 3 — Ada files a GitHub issue on behalf of the engineer (3-legged OAuth)

> *Engineer Pat reviews Ada's findings: "Yes, this is a real bug, file it."*
> Ada must create the GitHub issue **as Pat**, not as herself.

## Goal

Stand up a new Ada (`ada-stage3`) that has two tools:

1. **`lookup_order`** — same as Stage 1, reads `orders.csv` from GCS via Ada's own SPIFFE identity (carries forward as a regression check).
2. **`file_github_issue`** — *new* — creates a GitHub issue using a 3-legged OAuth grant brokered by Agent Identity Auth Manager. The issue is filed on behalf of the consenting user, not under a service account.

## Why 3-legged?

Stages 1 (own identity) and 2 (2LO) had Ada acting on her own authority. Stage 3 is structurally different: Ada acts **on behalf of a specific human user**.

- The third party (GitHub) sees Pat's identity, applies Pat's permissions, sends Pat the notifications.
- Audit logs show both Ada (the agent that performed the action) AND Pat (the user who authorized it).
- When Pat leaves Acme and her access is revoked at GitHub, Ada immediately stops being able to file on her behalf — without anyone touching Acme's infrastructure.

3LO is the most consequential auth flow in M1 and the one with the most moving parts: a consent UI redirect, an LRO with a `consent_nonce`, a callback validation, and a token vault per-user-per-provider.

## Prerequisites

- Stages 1, 2, or 4 already deployed (proves your M1 setup works) — recommended but not strictly required
- GitHub OAuth App registered (per `../../setup/30_signup_guide.md` § 2)
- A test repo for Ada to file issues in (e.g., `Cotomacio/ada-bug-reports`)

`.env.local` must include:

```bash
export GH_CLIENT_ID=...
export GH_CLIENT_SECRET='...'                  # single-quote — secrets often contain shell metachars
export GH_TEST_REPO=Cotomacio/ada-bug-reports
```

> ⚠️ **Critical GitHub OAuth App setting:** in your OAuth App's settings at
> https://github.com/settings/developers, the **Authorization callback URL**
> must be exactly `http://localhost:8080/callback`. The `consent_github.py`
> helper opens that local port to capture the redirect. Set this before
> running the consent step.

## What's in this folder

```
stage3-3lo-github/
├── deploy.py                       ← single-step SDK deploy
├── chat.py                         ← talk to deployed Ada
├── consent_github.py               ← one-time browser consent flow (3LO)
├── grant_access.sh                 ← bucket grant
├── setup_github_provider.sh        ← create the 3LO connector + bind IAM
├── test_local.py                   ← local sanity check (lookup_order only)
├── README.md
├── installation_scripts/
│   └── create_venv.sh
└── agent/
    ├── __init__.py                    ← CredentialManager registration
    ├── agent.py                       ← LlmAgent with both tools
    ├── tools.py                       ← lookup_order + file_github_issue
    └── requirements.txt
```

## Architecture

```
   Step 1 — one-time consent (run consent_github.py)
   ─────────────────────────────────────────────────
   [ User browser ] ──► [ github.com/login/oauth/authorize ]
              ▲                       │
              │                       ▼ user clicks "Authorize"
              │              [ Redirect to localhost:8080/callback?code=... ]
              │                       │
              │                       ▼
              └────  consent_github.py  ──► FinalizeCredential(code, nonce)
                                       │
                                       ▼
                            [ Auth Manager vault — per-user authorization stored ]

   Step 2 — Ada runs in production using the stored credential
   ─────────────────────────────────────────────────────────────
   [ Ada ] ──► retrieveCredentials("github-3lo", user_id=Pat)
                  │
                  ▼
       [ Auth Manager runtime returns Pat's bearer ]
                  │
                  ▼
       [ POST api.github.com/repos/.../issues w/ Authorization: Bearer ... ]
                  │
                  ▼
       [ Issue created — author = Pat (not Ada, not a service account) ]
```

## Steps

```bash
# 0. M1 setup must be done
source ../../.env.local

# 1. Optional: local sanity on lookup_order
python -m venv .venv && source .venv/bin/activate
pip install -r agent/requirements.txt
python test_local.py

# 2. Deploy ada-stage3
unset REASONING_ENGINE_ID AGENT_IDENTITY
python deploy.py 2>&1 | tee deploy.log

# 3. Capture IDs
export REASONING_ENGINE_ID=...
export AGENT_IDENTITY=...

# 4. Grant bucket (for lookup_order)
bash grant_access.sh

# 5. Create the GitHub 3LO connector + bind Ada's principal
bash setup_github_provider.sh

# 6. One-time user consent (you authorize Ada to act as you on GitHub)
#    BEFORE this, set the callback URL in your GitHub OAuth App to
#    http://localhost:8080/callback
python consent_github.py

# 7. Wait for IAM propagation (BETA role)
sleep 180

# 8. Talk to Ada
python chat.py "File a bug in $GH_TEST_REPO titled 'Stage 3 smoke test'"
```

## How the consent flow works (read once)

3LO can't be wired purely with config — the *user* has to grant the OAuth app permission via their browser. ADK's `AuthenticatedFunctionTool` discovers this via the LRO's `consent_pending` metadata and the agent returns `"Pending User Authorization"` placeholder unless someone has already consented.

The `consent_github.py` helper automates the consent flow once:

1. Calls `retrieve_credentials` with no prior authorization → API returns an LRO whose metadata contains `auth_uri` (the GitHub consent page) and `consent_nonce`.
2. Spins up a tiny HTTP server on `localhost:8080`.
3. Opens `auth_uri` in your browser. You click "Authorize" on GitHub.
4. GitHub redirects to `localhost:8080/callback?code=...&state=<nonce>`.
5. Helper extracts the `code`, calls `FinalizeCredential(consent_nonce, code)`.
6. Auth Manager stores the access token + refresh token under your user_id.

From now on, when Ada calls `file_github_issue`, ADK fetches your stored token from Auth Manager and uses it. **No re-authorization needed** until you revoke the grant at github.com/settings/applications.

## TODOs at a glance

If running as a fill-in-the-blanks workshop, the lesson is in:

1. **`agent/tools.py — file_github_issue(repo, title, body, credential=None)`** — same `credential.http.credentials.token` extraction as Stage 2. Note the **lower-case `credential`** parameter name (ADK's `_ignore_params` strips it from the LLM schema).
2. **`agent/agent.py — create_agent()`** — wrap `file_github_issue` with `AuthenticatedFunctionTool(func=..., auth_config=AuthConfig(auth_scheme=GcpAuthProviderScheme(name="projects/.../connectors/github-3lo")))`.

Everything else (`agent/__init__.py` registration, scripts) is scaffolding from the proven Stages 1/2 pattern.

## Verify

1. **Functional check.** `python chat.py "File a bug ..."` returns an issue number + URL. Open the URL — issue author is **you**, not a service account.
2. **No-secret check.** `grep -r "$GH_CLIENT_SECRET" agent/ deploy.py chat.py` finds nothing.
3. **Audit attribution.** Cloud Logs for `iamconnectorcredentials.retrieveCredentials` show Ada's SPIFFE principal as the caller, with the GitHub user_id as the subject.
4. **Revocation test.** Go to https://github.com/settings/applications, revoke Ada's app. Re-run chat.py — you'll get a `"Pending User Authorization"` response (the credential is gone). Re-run `consent_github.py` to restore.

## Threats this stage closes

| Threat | How |
|---|---|
| **T4** hardcoded secret leak | GitHub client_secret lives in Auth Manager, never in agent |
| **T5** agent reads user token | Pat's token is decrypted only inside Auth Manager runtime; Ada's process holds the connector resource name, not the token |
| **T7** attribution / repudiation | Cloud Audit shows both Ada (SPIFFE) and Pat (GitHub user_id) |

## What's still exposed

- **T9 over-scoped consent.** If you registered the OAuth App with `repo` when `public_repo` would suffice, Auth Manager won't push back. Scope review is process control, addressed in M4 (Policies).
- A revoked grant breaks Ada silently — design `file_github_issue` callers to re-trigger consent gracefully when they get a "Pending" response.

## Troubleshooting

| Symptom | Check |
|---|---|
| `consent_github.py` says `Expected auth_uri + consent_nonce in LRO metadata` | The `iamconnectorcredentials_v1alpha` LRO metadata field names may differ in your installed SDK version. The helper prints the actual metadata; paste those field names and we'll adjust. |
| `403 Permission denied` on connector | BETA role hasn't propagated yet. Wait 180s. |
| Browser opens consent page but `Authorization callback URL is not valid` from GitHub | Set the callback URL in your GitHub OAuth App settings to **exactly** `http://localhost:8080/callback` (no trailing slash, http not https). |
| Chat returns `"Pending User Authorization"` placeholder | Consent flow not completed. Run `consent_github.py`. |
| Tool returns `Credential missing http.credentials.token` | Consent completed but the user_id in `chat.py` ($USER) doesn't match the user_id `consent_github.py` used. Set `USER_ID` explicitly in both or use the same `$USER` environment variable. |

## What's still exposed (motivates Stage 4)

Stage 3 demonstrated user-delegated authority. But the patterns for OAuth-less APIs (a static API key) still need to be solved — that's Stage 4.

## Status

This stage uses the **canonical ADK + Auth Manager wiring** validated end-to-end in Stage 2. The 3LO consent flow (`consent_github.py`) is best-effort against the `iamconnectorcredentials_v1alpha` API surface; if any field name differs in your SDK version, the helper prints actionable diagnostics.
