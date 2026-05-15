# Stage 2 — Ada checks ServiceNow incidents (2-legged OAuth)

> *Customer: "I keep getting a checkout error."*
> Before bothering an engineer, Ada checks ServiceNow for a known incident.

> **Status: validated end-to-end.** Uses Agent Identity Auth Manager's
> 2-legged OAuth flow via ADK's `AuthenticatedFunctionTool` +
> `GcpAuthProviderScheme`. The four wiring details that must all be
> correct (any one wrong and it silently breaks) are called out in the
> **"How the tool wiring works"** section below — read them before
> implementing the TODOs.

## Goal

Stand up a new Ada (`ada-stage2`) that has two tools:

1. **`lookup_order`** — same as Stage 1, reads `orders.csv` from GCS via Ada's own SPIFFE identity.
2. **`lookup_incidents`** — *new* — calls ServiceNow's REST API for active incidents using a 2-legged OAuth flow brokered by Agent Identity Auth Manager. Ada's source and image contain **zero** ServiceNow credentials.

## Why 2-legged?

Stage 1 was Ada talking to a Google API *as herself*. Stage 2 is Ada talking to a third-party (ServiceNow) *as herself* — no end user delegating. Machine-to-machine: the agent uses a `client_id` + `client_secret` to fetch a bearer token via the `client_credentials` grant.

The catch: we still don't want the secret in Ada's code or container. That's what Auth Manager is for. The ServiceNow credentials are uploaded once to an Auth Manager connector; Ada only references it by resource name. The runtime fetches a fresh bearer token at every tool call.

## Prerequisites

You must have completed M1 setup (`source ../../.env.local` and the three `setup/*.sh` scripts) AND signed up for a ServiceNow Personal Developer Instance with an Inbound OAuth Integration. The signup walkthrough is in [`../../setup/30_signup_guide.md`](../../setup/30_signup_guide.md).

`.env.local` must include:

```bash
export SNOW_INSTANCE_URL=https://devXXXXX.service-now.com
export SNOW_CLIENT_ID=...
export SNOW_CLIENT_SECRET=...
```

Stage 1's GCS bucket (`gs://acme-orders-${PROJECT_ID}`) must still exist — Stage 2 reuses it.

## What's in this folder

```
stage2-2lo-servicenow/
├── deploy.py                              ← single-step SDK deploy
├── chat.py                                ← talk to the deployed agent
├── grant_access.sh                        ← bucket grant (mirror of Stage 1)
├── setup_servicenow_provider.sh           ← create the Auth Manager connector + bind IAM
├── test_local.py                          ← local sanity check (lookup_order only)
├── README.md
├── installation_scripts/
│   └── create_venv.sh
└── agent/                                 ← shipped to the engine as a Python subpackage
    ├── __init__.py
    ├── agent.py                              ← LlmAgent w/ both tools + AuthenticatedFunctionTool
    ├── tools.py                              ← lookup_order + lookup_incidents
    └── requirements.txt
```

## Architecture

```
   [ Ada (deployed) ]
         │
         │   retrieveCredentials("snow-incidents")        ── routed via Auth Manager
         ▼
   [ Auth Manager runtime — iamconnectorcredentials.googleapis.com ]
         │
         │   client_credentials grant
         ▼
   [ ServiceNow OAuth /oauth_token.do ]
         │
         │   short-lived bearer token (returned to Auth Manager)
         ▼
   [ Auth Manager injects token as Authorization: Bearer ... ]
         │
         ▼
   [ ServiceNow /api/now/table/incident ]
```

Ada never sees the ServiceNow client_secret. She never sees the OAuth token in her runtime logs. She only knows the resource name of the Auth Manager connector and a function signature with a `_credential=None` kwarg that ADK fills in for her at call time.

## Steps

```bash
# 0. Verify M1 setup is done (Stage 1 prereqs apply)
source ../../.env.local
bash ../../setup/00_check_prereqs.sh        # gcloud, python, billing
bash ../../setup/10_enable_apis.sh          # incl. iamconnectorcredentials (new)
bash ../../setup/20_create_bucket_and_seed.sh   # idempotent — skipped if bucket exists

# 1. (Optional) Quick local sanity check of the GCS tool
gcloud auth application-default login
python -m venv .venv && source .venv/bin/activate
pip install -r agent/requirements.txt
python test_local.py

# 2. Deploy a new agent (ada-stage2). Single-step SDK pattern, same as Stage 1.
python deploy.py 2>&1 | tee deploy.log

# 3. Capture the IDs printed at the end
export REASONING_ENGINE_ID=...   # printed by deploy.py
export AGENT_IDENTITY=...         # printed by deploy.py

# 4. Bucket grant for lookup_order
bash grant_access.sh

# 5. Create the ServiceNow auth provider in Auth Manager + grant Ada access to it
bash setup_servicenow_provider.sh

# 6. Talk to Ada
python chat.py "Is there an active incident affecting checkout?"
python chat.py "Where is order ACME-78214?"
python chat.py                           # default: tries both tools at once
```

## TODOs at a glance

If running this as a fill-in-the-blanks workshop, the two functions worth implementing yourself are in `agent/tools.py`:

1. **`lookup_order(order_id)`** — same pattern as Stage 1: `storage.Client()` with no args, read CSV, return row.
2. **`lookup_incidents(query, limit, _credential=None)`** — the new pattern:
   - `_credential` is injected by ADK's `AuthenticatedFunctionTool`. Read `_credential.access_token`.
   - GET `{SNOW_INSTANCE_URL}/api/now/table/incident?sysparm_query=...&sysparm_limit=...` with `Authorization: Bearer {token}`.
   - Return a JSON dict shaped for the LLM (the `result` array plus a `count`).

Everything else — `deploy.py`, `chat.py`, the two shell scripts, `installation_scripts/create_venv.sh` — is scaffolding, not the lesson.

## How the tool wiring works (read this carefully — four details all matter)

Four wiring details must be exactly right. Get any one wrong and the tool fails silently:

| Detail | Where | Why |
|---|---|---|
| **Parameter name is `credential` — no leading underscore** | `agent/tools.py` function signature | ADK's `AuthenticatedFunctionTool` calls `self._ignore_params.append("credential")` to strip the parameter from the LLM-facing function declaration. `_credential` (underscore) doesn't match — Gemini sees it and rejects the function with `INVALID_ARGUMENT: parameters._credential schema didn't specify the schema type`. |
| **Read `credential.http.credentials.token`** | `agent/tools.py` body | The `credential` ADK injects is an `AuthCredential` object, not a token string. Access via `credential.http.credentials.token` (per the canonical `adk-python contributing/samples/gcp_auth` sample). Render as `f"{http.scheme.title()} {token}"` for the `Authorization` header. |
| **Register `GcpAuthProvider` in `agent/__init__.py`, not `agent.py`** | `agent/__init__.py` | `CredentialManager.register_auth_provider()` mutates class-level state. The deployed runtime only auto-imports modules referenced by the pickled `LlmAgent` — `agent.tools` is referenced (via the function tool), but `agent.agent` is not. Putting the registration in `__init__.py` guarantees it runs whenever any agent submodule loads. If you put it in `agent.py`, the runtime crashes at first tool call with `ValueError: No auth provider registered for custom auth scheme 'gcpAuthProviderScheme'`. |
| **Wrap with `AuthenticatedFunctionTool`, not a plain function tool** | `agent/agent.py` | The tool needs `auth_config=AuthConfig(auth_scheme=GcpAuthProviderScheme(name="projects/.../connectors/{name}"))` so ADK knows which connector to fetch credentials from. ADK handles the LRO + 2LO consent_pending polling for you — don't call `retrieve_credentials` directly. |

## How the deploy works (read once)

Same three-phase shape as Stage 1, with one new env var:

| Phase | What happens |
|---|---|
| **1. Build** | `create_agent()` builds an `LlmAgent` with `[lookup_order, AuthenticatedFunctionTool(lookup_incidents)]`. The auth-config references the Auth Manager connector by resource name. |
| **2. Deploy** | `client.agent_engines.create(agent=AdkApp(...), config={...})`. The runtime env now includes `SNOW_INSTANCE_URL` and `SNOW_PROVIDER_NAME` so `tools.py` and `agent.py` can resolve them at runtime. |
| **3. Baseline IAM** | Same three project-scope roles as Stage 1. |

`setup_servicenow_provider.sh` (run separately, after deploy) is the auth-provider half:

| Step | Effect |
|---|---|
| `gcloud alpha agent-identity connectors create snow-incidents ...` | Uploads the ServiceNow client_id, client_secret, and token endpoint to Auth Manager. From this moment forward Ada can reference the connector by resource name without ever holding the secret. |
| `gcloud alpha agent-identity connectors add-iam-policy-binding ... --role=roles/iamconnectors.user` | Authorizes Ada's specific SPIFFE principal to call `retrieveCredentials` on this connector. No other agent or user can fetch this token. |

## Why these specific config bits

| Where | What | Why |
|---|---|---|
| `agent/agent.py` | `CredentialManager.register_auth_provider(GcpAuthProvider())` | One-time registration so ADK knows how to resolve Auth Manager connector references. |
| `agent/agent.py` | `AuthenticatedFunctionTool(func=..., auth_config=AuthConfig(auth_scheme=GcpAuthProviderScheme(name=...)))` | The wrapper that makes ADK call `retrieveCredentials` before invoking the function, and inject the token as `_credential`. |
| `agent/agent.py` | Resource name `projects/{P}/locations/{L}/connectors/{NAME}` | Canonical Auth Manager resource shape. Note `connectors/` (not `authProviders/`). |
| `agent/tools.py` | `_credential=None` kwarg | ADK convention. The underscore signals it's framework-managed and shouldn't be exposed to the LLM as a function parameter. |
| `setup/10_enable_apis.sh` | `iamconnectorcredentials.googleapis.com` | The *runtime* half of Auth Manager. Separate API from `iamconnectors.googleapis.com` (admin). Both must be enabled. |

## Verify

1. **Functional check (incidents).** `python chat.py "any active checkout incidents?"` returns ServiceNow incident numbers, descriptions, and states.
2. **Functional check (orders).** `python chat.py "where is ACME-78214?"` works exactly as in Stage 1.
3. **Combined query.** `python chat.py` with the default prompt asks about both at once — Ada should call both tools.
4. **No-secret check.** `grep -r "$SNOW_CLIENT_SECRET" agent/ deploy.py chat.py` should match nothing. The secret lives in Auth Manager, not in shipped code.
5. **Audit check.** `gcloud logging read 'protoPayload.serviceName="iamconnectorcredentials.googleapis.com"' --limit=5 --freshness=10m` shows `retrieveCredentials` calls attributed to Ada's SPIFFE principal.

> 🔭 **Coming in M6:** ServiceNow calls will appear in the **Tools** tab as a separate provider, with token-fetch latency split out from API-call latency — diagnose *"is ServiceNow slow or is Auth Manager slow?"*

## Threats this stage closes

| Threat | How |
|---|---|
| **T4** hardcoded secret leak | ServiceNow client_secret lives in Auth Manager, never in agent source/image/env |
| **T8** stale unrotated keys | Rotate the secret at ServiceNow → re-run `setup_servicenow_provider.sh` → done. No agent redeploy needed. |

## Troubleshooting

| Symptom | What to check |
|---|---|
| **`403: PERMISSION_DENIED` on retrieveCredentials** | Either `setup_servicenow_provider.sh` didn't bind Ada's SPIFFE principal to `roles/iamconnectors.user`, or IAM hasn't propagated yet. Wait 30s. Verify with `gcloud alpha agent-identity connectors get-iam-policy snow-incidents --location=us-central1`. |
| **`401` from ServiceNow itself** | The OAuth client in ServiceNow is misconfigured — wrong grant type (must be Client Credentials), wrong role on the OAuth Application User, or the secret in `.env.local` doesn't match what's stored in ServiceNow. Re-test the OAuth token endpoint manually: `curl -X POST "$SNOW_INSTANCE_URL/oauth_token.do" -d "grant_type=client_credentials&client_id=$SNOW_CLIENT_ID&client_secret=$SNOW_CLIENT_SECRET"`. |
| **`gcloud alpha` command not found** | `gcloud components install alpha` (Cloud Shell may need this once). |
| **Ada says "No credential injected by Auth Manager"** | `AuthenticatedFunctionTool` is not invoking ADK's credential injection. Verify `CredentialManager.register_auth_provider(GcpAuthProvider())` runs at module import time, and the resource name in `GcpAuthProviderScheme(name=...)` matches the actual connector. |
| **Tool returns ServiceNow data but the LLM ignores it** | The ServiceNow REST response shape may be too noisy. Check that `lookup_incidents` returns a small, well-shaped dict (see the solution). |
| **`gcloud alpha agent-identity connectors create` fails with INVALID_ARGUMENT** | Token endpoint format. It must be the full URL ending in `/oauth_token.do`. |

## What's still exposed (motivates Stage 3)

ServiceNow sees "Ada acting on behalf of Acme Commerce" — there's no per-user attribution because no end user delegated authority. That's correct for incident lookup. But for actions like "file a bug **as Pat**", the third-party system needs Pat's identity. Stage 3 introduces 3-legged OAuth for per-user delegation via GitHub.
