# Stage 1 — Ada reads the order book (own identity)

> *Customer chats: "Where is my order ACME-78214?"*

## Goal

Stand up Ada with `identity_type=AGENT_IDENTITY`, grant her SPIFFE principal `roles/storage.objectViewer` on `gs://acme-orders-${PROJECT_ID}`, and prove she can read the bucket **without any service-account JSON, env-var key, or Secret Manager entry**.

## What's in this folder

```
stage1-own-identity/
├── deploy.py            ← run from here
├── grant_access.sh
├── test_local.py
├── README.md
└── agent/               ← the agent package adk deploy ships
    ├── __init__.py
    ├── agent.py            ← TODO: build the LlmAgent
    ├── tools.py            ← TODO: wrap GCS read in a tool
    ├── agent_engine_app.py ← AdkApp wrapper (no TODOs)
    └── requirements.txt    ← runtime deps (lower bounds, not pins)
```

| File | Purpose | Has TODOs? |
|---|---|---|
| `agent/tools.py` | Order-lookup tool wrapping `google-cloud-storage` | ✅ |
| `agent/agent.py` | Ada's `LlmAgent` definition | ✅ |
| `agent/agent_engine_app.py` | `AdkApp` wrapper required by `adk deploy` | ❌ |
| `agent/requirements.txt` | Runtime deps (lower bounds, not pins) | ❌ |
| `deploy.py` | Two-step deploy: empty engine + ADK CLI ship | ❌ |
| `grant_access.sh` | Bind Ada's principal to `roles/storage.objectViewer` on the bucket | ❌ |
| `test_local.py` | Local sanity check using your ADC | ❌ |

> **Why is agent code in `agent/` instead of the top level?** The v1beta1 SDK auto-discovers `agent_engine_app.py` if it sits in `deploy.py`'s cwd and tries to bundle the *whole* working dir into the create-engine API call. With `.venv/` plus `deploy.log` being tee'd live, that easily exceeds the 8 MB request payload limit. Putting agent code in a subpackage keeps Phase 3 (engine creation) truly empty; Phase 5's `adk deploy` then ships `agent/` via streamed chunks with no size issue.

The reference solution is in [`../../solutions/stage1/`](../../solutions/stage1/) — same `agent/` subpackage layout.

## Steps

```bash
# 0. Setup (once for the whole module)
source ../../.env.local
bash ../../setup/00_check_prereqs.sh
bash ../../setup/10_enable_apis.sh
bash ../../setup/20_create_bucket_and_seed.sh

# 1. Implement the TODOs in agent/agent.py and agent/tools.py
#    (See "TODOs at a glance" below)
#    OR fast-path for validation: copy the reference solution
#       cp -r ../../solutions/stage1/agent/. agent/

# 2. Local sanity check using YOUR ADC, not Ada's identity yet
gcloud auth application-default login   # one-time
python -m venv .venv && source .venv/bin/activate
pip install -r agent/requirements.txt
python test_local.py                     # should print all 5 orders

# 3. Deploy. This is a TWO-STEP operation:
#      Phase 3 — create empty Agent Engine via v1beta1 SDK with
#                identity_type=AGENT_IDENTITY (3–15 min)
#      Phase 5 — `adk deploy agent_engine` ships the code
#    deploy.py does both. Run it and watch.
#    `tee` captures the full output — invaluable if something fails silently.
python deploy.py 2>&1 | tee deploy.log

# 4. Persist the IDs printed at the end
export REASONING_ENGINE_ID=...   # printed by deploy.py
export AGENT_IDENTITY=...         # printed by deploy.py

# 5. Grant Ada bucket-level access (the lesson of Stage 1)
bash grant_access.sh

# 6. Talk to Ada
python chat.py "Where is order ACME-78214?"
# (or just `python chat.py` for the default prompt)
# Note: `adk run-remote` does not exist in current adk; use chat.py instead.
```

## TODOs at a glance

1. **`agent/tools.py` — `lookup_order`.** `storage.Client()` with **no arguments** (ADC → Agent Identity at runtime). Read `orders.csv` and return the row matching `order_id`.
2. **`agent/agent.py` — `create_agent`.** `LlmAgent(name="ada", model="gemini-2.5-flash", instruction=INSTRUCTIONS, tools=[lookup_order])`.

That's it. `deploy.py`, `agent/agent_engine_app.py`, `grant_access.sh`, and `agent/requirements.txt` are pre-written — they're not the lesson, they're the scaffolding.

## Why two-step deploy?

The single-step path you see in older tutorials —

```python
ReasoningEngine.create(reasoning_engine=ada, identity_type="AGENT_IDENTITY", ...)
```

— **does not work** with Agent Identity GA. The runtime expects a `BaseAgent` instance and rejects the factory pattern with a pydantic `ValidationError`. The path that does work:

1. **Phase 3:** create an **empty** engine via `vertexai.Client(http_options=dict(api_version="v1beta1"))` + `client.agent_engines.create(config={"identity_type": types.IdentityType.AGENT_IDENTITY})`. This is what provisions the SPIFFE identity and X.509 cert.
2. **Phase 5:** ship the code into that engine via `adk deploy agent_engine --agent_engine_id $ENGINE_ID`. ADK CLI handles packaging.

`deploy.py` does both phases. Read it once — it's the canonical Agent Identity bootstrap.

## Why no `--trace_to_cloud`?

You will see other tutorials pass `--trace_to_cloud` to `adk deploy`. **Do not.** Under Agent Identity GA, the tracing instrumentor calls `cloudresourcemanager.projects.get` during cold start, which 401s (the SPIFFE workload credential isn't honored by the resource_manager gRPC client during startup), and Ada fails to start with no useful error in the deploy output. **M6 Observability** shows the right way to enable tracing.

## Why these IAM roles?

`deploy.py` Phase 4 grants three baseline roles at the project scope:

| Role | Why |
|---|---|
| `roles/serviceusage.serviceUsageConsumer` | Required for any agent to start |
| `roles/aiplatform.expressUser` | Inference, sessions, memory (NB: not `aiplatform.user`) |
| `roles/browser` | Read project metadata during startup |

Then `grant_access.sh` adds the **resource-scoped** grant that is the actual lesson of Stage 1:

```
roles/storage.objectViewer on gs://acme-orders-${PROJECT_ID}
```

Bound to Ada's specific SPIFFE principal — not a project-wide service account, not a shared role.

## Verify

1. **Functional check.** Ada returns Maria's order status when asked.
2. **Audit check.** Cloud Logs Explorer, filter on `protoPayload.methodName="storage.objects.get"` AND `resource.labels.bucket_name="acme-orders-${PROJECT_ID}"`. The `protoPayload.authenticationInfo.principalSubject` is the SPIFFE ID, **not** a `@developer.gserviceaccount.com` email.
3. **No-key check.** No `service_account.json` is referenced anywhere in `agent.py`, `tools.py`, or `agent_engine_app.py`. There is no key file in the deployed image.
4. **Replay check (advanced).** Capture a token Ada uses and try to replay it from your laptop. It fails because of DPoP/mTLS binding — this is **T2**.

> 🔭 **Coming in M6:** the GCS read appears in the Agent Observability **Tools** tab keyed by Ada's SPIFFE ID. Latency, error rate, and call count are sliceable per-tool. You'll also see it as a span in Cloud Trace under the parent agent-turn trace — but only after you re-enable tracing the M6-correct way.

## Threats this stage closes

| Threat | How |
|---|---|
| **T1** long-lived key theft | No key file ever existed |
| **T2** token replay off-host | DPoP + mTLS bind tokens to Ada's cert |
| **T3** cross-agent impersonation | Per-agent SPIFFE ID; not shareable |
| **T6** over-broad shared SA | IAM bound to *this* agent's principal, not a project-wide SA |
| **T7** no per-agent attribution | Audit log shows the SPIFFE ID |

## Common pitfalls

- **`Deploy failed: 400 INVALID_ARGUMENT. Request payload size exceeds the limit: 8388608 bytes`** during Phase 3 → `agent_engine_app.py` is at the top level of `stage1-own-identity/` instead of inside `agent/`. The SDK auto-bundled the whole cwd including `.venv/` and exceeded the 8 MB request limit. Move agent code under `agent/` (this layout already does that — verify nobody added a top-level `agent_engine_app.py`).
- **Re-running after a Phase 5 failure** → the engine and IAM grants from Phase 3/4 are still good. Just `export REASONING_ENGINE_ID=<id> AGENT_IDENTITY=<principal>` (printed by the prior run) and re-run `python deploy.py`. Phase 3 will skip, Phase 4 is idempotent, Phase 5 retries.
- **`failed to start and cannot serve traffic`** in Cloud Logs after deploy → you re-added `--trace_to_cloud`. Remove it. Delete the broken engine and redeploy.
- **`Successfully uninstalled google-auth-2.47.0`** in build log → your `requirements.txt` pinned `google-auth==<too-old>`. Use the `>=2.50.0` floor in this folder's `requirements.txt`.
- **`Permission denied` reading the bucket** → you skipped `grant_access.sh`. The `REASONING_ENGINE_ID` doesn't exist until Phase 3 completes.
- **`unknown type principal://…`** → don't hand-construct the SPIFFE URI. Use `AGENT_IDENTITY` printed by `deploy.py` (it pulls `effective_identity` from the API).
- **Audit log shows a `gserviceaccount` email** → you ran `deploy.py` without `identity_type` somehow (or hit a bug). Verify with `gcloud ai reasoning-engines describe ...` that the engine has Agent Identity enabled. If not, delete and recreate.
- **`Failed to update Agent Engine: env_vars ... must also provide source code`** → don't pass env vars to the empty `agent_engines.create()` call. Use the `--env_file` to `adk deploy` instead. (`deploy.py` already does this.)
- **`adk` not found** → `pip install google-adk`. Run from inside the venv.
- **Re-running after a partial failure** → `export REASONING_ENGINE_ID=<id>` before re-running; `deploy.py` skips Phase 3 and re-attempts the code ship.

## What's still exposed (motivates Stage 2)

Ada can read GCS. But she can't talk to anything *outside* Google Cloud. ServiceNow, GitHub, OpenWeather all require third-party credentials — and we just spent a stage proving credentials don't belong in Ada's code. That's what Stages 2–4 solve via Auth Manager.
