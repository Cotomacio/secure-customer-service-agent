# Stage 4 — Ada checks the weather at delivery (API key)

> *Customer in Denver: "Why is my package late?"*
> Acme's logistics team wants Ada to factor weather into ETA explanations. OpenWeather only supports API keys.

## Goal

Stand up a new Ada (`ada-stage4`) that has two tools:

1. **`lookup_order`** — same as Stage 1, reads `orders.csv` from GCS via Ada's own SPIFFE identity.
2. **`get_weather`** — *new* — calls OpenWeather's REST API. Authenticates via an Agent Identity Auth Manager **API-key connector**; the key lives in Auth Manager, not in agent source.

## Why API-key?

Many useful third-party APIs (especially long-tail ones) don't speak OAuth. They authenticate with a static API key. Without Auth Manager, the temptation is to put the key in an env var or Secret Manager and pull it at startup — but that puts the key in agent memory, in `kubectl describe`, in process listings, and one careless `print()` away from a log leak.

Auth Manager's API-key connector keeps the key server-side. Ada's code only holds the connector's resource name. The runtime fetches the key on demand using Ada's SPIFFE identity.

## Prerequisites

Same M1 setup as prior stages. `.env.local` must include:

```bash
export OPENWEATHER_API_KEY='your-32-char-hex-key'
```

(Wrap in single quotes — OpenWeather keys are all hex so this is precautionary, but the habit avoids shell-escape footguns on future provider secrets.)

Stage 1's GCS bucket must still exist.

## What's in this folder

```
stage4-apikey-openweather/
├── deploy.py                              ← single-step SDK deploy
├── chat.py                                ← talk to the deployed agent
├── grant_access.sh                        ← bucket grant
├── setup_openweather_provider.sh          ← create the API-key connector + bind IAM
├── test_local.py                          ← local sanity check (lookup_order only)
├── README.md
├── installation_scripts/
│   └── create_venv.sh
└── agent/
    ├── __init__.py
    ├── agent.py
    ├── tools.py
    └── requirements.txt
```

## Architecture

```
   [ Ada ]
      │
      │   retrieveCredentials("openweather")
      ▼
   [ Auth Manager runtime — iamconnectorcredentials.googleapis.com ]
      │
      │   returns stored API key
      ▼
   [ Ada calls: GET api.openweathermap.org/data/2.5/weather?q=...&appid=KEY ]
```

Ada's container holds the connector resource name (`projects/.../connectors/openweather`) — but never the API key itself.

## Steps

```bash
# 0. M1 setup must be done
source ../../.env.local

# 1. (Optional) Local sanity check on lookup_order
gcloud auth application-default login
python -m venv .venv && source .venv/bin/activate
pip install -r agent/requirements.txt
python test_local.py

# 2. Deploy a new agent (ada-stage4)
python deploy.py 2>&1 | tee deploy.log

# 3. Capture the IDs printed at the end
export REASONING_ENGINE_ID=...
export AGENT_IDENTITY=...

# 4. Bucket grant for lookup_order (same as Stage 1)
bash grant_access.sh

# 5. Create the OpenWeather API-key connector + bind IAM
bash setup_openweather_provider.sh

# 6. Wait for IAM propagation (BETA roles can take 2-5 min)
sleep 180

# 7. Talk to Ada
python chat.py "What's the weather in Denver right now?"
python chat.py "My order ACME-78214 is going to Denver and it's late — could weather be a factor?"
```

## Verify

1. **Functional check.** Ada returns real weather data for Denver (temp, conditions, etc.).
2. **No-key check.** `grep -r "$OPENWEATHER_API_KEY" agent/ deploy.py chat.py` matches nothing. The key lives only in Auth Manager.
3. **Rotation drill.** Regenerate the API key in OpenWeather → update `.env.local` → re-run `bash setup_openweather_provider.sh`. The agent picks up the new key on the next tool call. No agent redeploy. **T8 closed.**
4. **Audit.** Cloud Logs for `iamconnectorcredentials.retrieveCredentials` shows the agent's SPIFFE principal making the call.

> 🔭 **Coming in M6:** OpenWeather call counts and error rates land in the **Usage** tab next to your free-tier daily quota — the dashboard catches a runaway loop *before* it eats your 1,000-call/day budget.

## Threats this stage closes

- **T4** no hardcoded API key in agent source or image
- **T8** key rotation is a provider config change, not a code release

## What's still exposed

OpenWeather still receives the key as a bearer credential on every request. If *they* leak it, you must rotate. Auth Manager makes rotation a one-command operation but doesn't change the third-party trust model.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `404 Requested entity was not found` from `retrieve_credentials` | Same Auth Manager preview-API blocker that affects Stage 2 may also affect API-key connectors if no `Authorization` resource auto-provisions. If you hit this, fall back to Cloud Secret Manager (see "Interim pattern" below). |
| `403 Permission 'iamconnectors.connectors.retrieveCredentials' denied` | BETA-stage role hasn't propagated yet. Wait 3–5 min after `setup_openweather_provider.sh` before testing. |
| `OpenWeather returned 401` from inside `get_weather` | The fetched key is invalid (rotated/revoked at OpenWeather) or hasn't activated yet (new keys take ~10 min). |
| Tool returns weather but LLM ignores it | Check Ada's response — Gemini may have summarized instead of quoting numbers. Try a more specific prompt like *"What's the exact temperature in Denver?"* |

## Interim pattern (if API-key Auth Manager is also preview-blocked)

If `retrieve_credentials` fails the same way as Stage 2:

1. Store the API key in Cloud Secret Manager: `gcloud secrets create openweather-key --data-file=<(echo -n "$OPENWEATHER_API_KEY")`
2. Grant Ada `roles/secretmanager.secretAccessor` on the secret
3. In `tools.py`, replace `_fetch_openweather_api_key` to read from Secret Manager via the `google-cloud-secret-manager` client
4. Same security boundary: secret stays in a managed service, agent fetches per-call, IAM-controlled

Auth Manager is the canonical future path. Secret Manager is the production-ready interim.
