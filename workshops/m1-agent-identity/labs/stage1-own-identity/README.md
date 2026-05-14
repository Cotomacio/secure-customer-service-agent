# Stage 1 — Ada reads the order book (own identity)

> *Customer chats: "Where is my order ACME-78214?"*

## Goal

Stand up Ada with `identity_type=AGENT_IDENTITY`, grant her SPIFFE principal `roles/storage.objectViewer` on `gs://acme-orders-${PROJECT_ID}`, and prove she can read the bucket **without any service-account JSON, env-var key, or Secret Manager entry**.

## What's in this folder

```
stage1-own-identity/
├── deploy.py                    ← single-step SDK deploy; run from here
├── chat.py                      ← talk to deployed Ada via stream_query
├── grant_access.sh              ← bind storage.objectViewer to Ada's SPIFFE principal
├── test_local.py                ← local sanity check (uses your ADC, not Ada's identity)
├── README.md
├── installation_scripts/
│   └── create_venv.sh           ← required Agent Engine base-image workaround
└── agent/                       ← shipped to the engine as a Python subpackage
    ├── __init__.py
    ├── agent.py                    ← TODO: build the LlmAgent
    ├── tools.py                    ← TODO: wrap GCS read in a tool
    └── requirements.txt            ← runtime deps (lower bounds, not pins)
```

| File | Purpose | Has TODOs? |
|---|---|---|
| `agent/tools.py` | Order-lookup tool wrapping `google-cloud-storage` | ✅ |
| `agent/agent.py` | Ada's `LlmAgent` definition | ✅ |
| `agent/requirements.txt` | Runtime deps for the deployed engine | ❌ |
| `installation_scripts/create_venv.sh` | Sets up `/code/.venv` correctly inside the engine container — required for the runtime's compileall step to succeed as appuser | ❌ |
| `deploy.py` | Single-step SDK deploy + baseline IAM grants | ❌ |
| `chat.py` | Talk to the deployed agent via `engine.stream_query()` | ❌ |
| `grant_access.sh` | Bind Ada's principal to `roles/storage.objectViewer` on the bucket | ❌ |
| `test_local.py` | Local sanity check using your ADC | ❌ |

The reference solution is in [`../../solutions/stage1/`](../../solutions/stage1/).

## Steps

```bash
# 0. Setup (once for the whole module — env vars + APIs + bucket)
source ../../.env.local
bash ../../setup/00_check_prereqs.sh
bash ../../setup/10_enable_apis.sh
bash ../../setup/20_create_bucket_and_seed.sh
bash ../../setup/40_enable_audit_logs.sh        # so audit-log verify in step 7 shows the SPIFFE principal

# 1. Implement the TODOs in agent/agent.py and agent/tools.py
#    (See "TODOs at a glance" below)
#    OR fast-path for validation: copy the reference solution
#       cp -r ../../solutions/stage1/agent/.                 agent/
#       cp -r ../../solutions/stage1/installation_scripts/.  installation_scripts/

# 2. Local sanity check using YOUR ADC (not Ada's identity yet)
gcloud auth application-default login          # one-time
python -m venv .venv && source .venv/bin/activate
pip install -r agent/requirements.txt
python test_local.py                            # should print all 5 seeded orders

# 3. Deploy. Single-step SDK pattern — builds AdkApp in-process and ships it
#    alongside the agent/ subpackage in one call. 3–10 min on a healthy org.
#    `tee` captures the full output for debugging.
python deploy.py 2>&1 | tee deploy.log

# 4. Persist the IDs printed at the end
export REASONING_ENGINE_ID=...   # printed by deploy.py
export AGENT_IDENTITY=...         # printed by deploy.py

# 5. Grant Ada bucket-level access (the lesson of Stage 1)
bash grant_access.sh

# 6. Talk to Ada
python chat.py                                  # default Stage 1 test prompt
python chat.py "Where is order ACME-78216?"    # try another order

# 7. Audit verification — prove Ada's SPIFFE identity made the GCS read
gcloud logging read \
  'resource.type="gcs_bucket" AND protoPayload.resourceName=~"acme-orders" AND protoPayload.methodName="storage.objects.get"' \
  --limit=3 --freshness=10m \
  --format='value(timestamp,protoPayload.authenticationInfo.principalSubject)' \
  --project="$GOOGLE_CLOUD_PROJECT"
# principalSubject should start with `principal://agents.global.org-...`
# — NOT a `@developer.gserviceaccount.com` email.
```

## TODOs at a glance

1. **`agent/tools.py` — `lookup_order`.** `storage.Client()` with **no arguments** (ADC → Agent Identity at runtime). Read `orders.csv` and return the row matching `order_id`.
2. **`agent/agent.py` — `create_agent`.** `LlmAgent(name="ada", model="gemini-2.5-flash", instruction=INSTRUCTIONS, tools=[lookup_order])`.

That's it. `deploy.py`, `grant_access.sh`, `chat.py`, and `installation_scripts/create_venv.sh` are pre-written — they're the scaffolding, not the lesson.

## How the deploy works (read once)

`deploy.py` is one script with three phases:

| Phase | What happens |
|---|---|
| **1. Build** | Calls `create_agent()` to get an `LlmAgent` instance, wraps it in `AdkApp(agent=..., enable_tracing=True)`. All in your local Python process. |
| **2. Deploy** | One SDK call: `client.agent_engines.create(agent=app, config={...})`. The SDK pickles the AdkApp via `cloudpickle`, ships `extra_packages=["agent", "installation_scripts/create_venv.sh"]`, and provisions the SPIFFE identity from `config["identity_type"]`. |
| **3. Baseline IAM** | Grants three project-scope roles to the new SPIFFE principal that the runtime needs to start: `serviceusage.serviceUsageConsumer`, `aiplatform.expressUser`, `browser`. |

`grant_access.sh` (run separately) then adds the **resource-scoped** grant that's the actual lesson:

```
roles/storage.objectViewer on gs://acme-orders-${PROJECT_ID}
```

Bound to Ada's specific SPIFFE principal — not a project-wide service account, not a shared role.

## Why the config shape looks the way it does

Every entry in `deploy.py`'s `config={...}` block earns its place:

| Config item | Why it's there |
|---|---|
| `identity_type=AGENT_IDENTITY` | The whole point — provisions the SPIFFE cert and per-agent IAM principal. |
| `requirements=["google-adk[agent-identity]>=1.31.0", ...]` | The `agent-identity` extra is what makes the runtime ADK actually bind the SPIFFE identity. |
| `requirements=["cloudpickle", "pydantic", ...]` | The SDK pre-validates the requirements list and rejects the deploy with `The following requirements are missing: {...}` if either is absent. |
| `extra_packages=["agent", "installation_scripts/create_venv.sh"]` | Ships our `agent/` subpackage so `from agent.tools import lookup_order` resolves at runtime. Also ships the venv-fix script as a regular asset. |
| `build_options={"installation_scripts": ["installation_scripts/create_venv.sh"]}` | Tells the build step to **execute** `create_venv.sh` (the `extra_packages` entry alone only ships the file). Without this, the base image's compileall step hits a `PermissionError` on root-owned site-packages and the container exits before serving — surfaces as the otherwise-opaque "failed to start and cannot serve traffic" error. |
| `env_vars={"GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES": "false"}` | Allows the runtime's Agent Identity token to be shared with the standard GCP SDK clients (e.g. `google-cloud-storage`). Without this some startup paths fail with auth errors. |
| `staging_bucket=gs://...` | Where the SDK uploads the pickled AdkApp before the engine pulls it. |

## Why these IAM roles?

`deploy.py` Phase 3 grants three baseline roles at the project scope:

| Role | Why |
|---|---|
| `roles/serviceusage.serviceUsageConsumer` | Required for any agent to start (quota check on aiplatform). |
| `roles/aiplatform.expressUser` | Inference, sessions, memory. **Note:** not `aiplatform.user`. |
| `roles/browser` | Read project metadata during startup. |

Then `grant_access.sh` adds the resource-scoped grant. That's where Agent Identity actually delivers value: per-agent, per-resource IAM, audit-attributed to the specific SPIFFE ID.

## Verify

1. **Functional check.** `python chat.py` returns Maria's order with `out_for_delivery / Denver`.
2. **Audit check.** Step 7's log query shows `principalSubject` = Ada's SPIFFE URI (only works after `40_enable_audit_logs.sh` ran).
3. **No-key check.** `grep -r "service_account.json\|GOOGLE_APPLICATION_CREDENTIALS" .` finds nothing in `agent/`, `deploy.py`, or `chat.py`.
4. **Replay check (advanced).** Capture a token Ada uses and try to replay it from your laptop. It fails because of DPoP/mTLS binding — **T2**.

> 🔭 **Coming in M6:** the GCS read appears in the Agent Observability **Tools** tab keyed by Ada's SPIFFE ID. Latency, error rate, and call count are sliceable per-tool, plus the parent agent-turn trace in Cloud Trace.

## Threats this stage closes

| Threat | How |
|---|---|
| **T1** long-lived key theft | No key file ever existed |
| **T2** token replay off-host | DPoP + mTLS bind tokens to Ada's cert |
| **T3** cross-agent impersonation | Per-agent SPIFFE ID; not shareable |
| **T6** over-broad shared SA | IAM bound to *this* agent's principal, not a project-wide SA |
| **T7** no per-agent attribution | Audit log shows the SPIFFE ID |

## Troubleshooting

| Symptom | What to check |
|---|---|
| **`failed to start and cannot serve traffic`** in deploy output | The container exited before health-check. Almost always one of: (a) `installation_scripts/create_venv.sh` not in BOTH `extra_packages` and `build_options.installation_scripts`; (b) a custom tracing wrapper that's calling `cloudresourcemanager.projects.get` at startup — the default `enable_tracing=True` is fine, but adding `--trace_to_cloud` to any adk CLI command is not. |
| **`The following requirements are missing: {'cloudpickle', 'pydantic'}`** before Phase 2 | The SDK pre-validates requirements. Both must be explicitly listed. The pre-shipped `deploy.py` has them. |
| **`Request payload size exceeds the limit: 8388608 bytes`** | The SDK auto-bundled too much from your cwd. Confirm the agent code is under `agent/` (not at the lab root) and that `.venv/` plus `deploy.log` aren't being swept in by an over-broad `extra_packages` entry. |
| **`unknown type principal://…`** when running `grant_access.sh` | Don't hand-construct the SPIFFE URI. Use the `AGENT_IDENTITY` printed by `deploy.py` (pulled from the API's `effective_identity`). |
| **`Permission denied`** on the bucket read from inside Ada | You skipped `grant_access.sh`, or `REASONING_ENGINE_ID` was empty when you ran it. Re-run after exporting both IDs from `deploy.py`'s output. |
| **Audit log shows a `gserviceaccount` email instead of a SPIFFE URI** | Engine was created without `identity_type=AGENT_IDENTITY`. Verify by REST: `curl -H "Authorization: Bearer $(gcloud auth print-access-token)" https://us-central1-aiplatform.googleapis.com/v1beta1/projects/$GOOGLE_CLOUD_PROJECT/locations/us-central1/reasoningEngines/$REASONING_ENGINE_ID` and check `spec.identityType`. If wrong, delete and redeploy. |
| **`adk: command not found`** when local-testing | `pip install google-adk` after activating the venv. The deploy itself doesn't shell out to `adk` — only `chat.py` and `test_local.py` need a local install. |
| **Local-changes-blocked `git pull`** when iterating | `git restore workshops/m1-agent-identity/labs/stage1-own-identity/` then re-pull. Local edits to the lab files (e.g. from copying solutions) block fast-forward merges. |
| **Deploy succeeded but `chat.py` returns 403** | IAM hasn't propagated yet. Wait 60s and retry. If it persists, re-check `grant_access.sh` output — it should print the SPIFFE principal and the `objectViewer` role binding. |
| **`Reasoning Engine resource [...]` stays unhealthy across multiple deploys** | The engine got into a stuck state. Delete and recreate: `curl -X DELETE -H "Authorization: Bearer $(gcloud auth print-access-token)" "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/$GOOGLE_CLOUD_PROJECT/locations/us-central1/reasoningEngines/$REASONING_ENGINE_ID?force=true"`, then `unset REASONING_ENGINE_ID AGENT_IDENTITY` and re-run `python deploy.py`. |

## What's still exposed (motivates Stage 2)

Ada can read GCS. But she can't talk to anything *outside* Google Cloud. ServiceNow, GitHub, OpenWeather all require third-party credentials — and we just spent a stage proving credentials don't belong in Ada's code. That's what Stages 2–4 solve via Auth Manager.
