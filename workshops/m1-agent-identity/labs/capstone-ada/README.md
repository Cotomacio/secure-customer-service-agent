# Capstone — Ada with all four Agent Identity auth flows

> *"Hi, I'm Maria. My order ACME-78214 to Denver was supposed to arrive yesterday
> and it's still not here. Is there a known shipping issue, and could weather
> there be a factor?"*

A single deployable Ada that demonstrates **every** Agent Identity / Auth
Manager pattern in M1, in one realistic customer-service scenario.

| Tool | Auth pattern | Lives where |
|---|---|---|
| `lookup_order` | Ada's own SPIFFE identity (ADC) | GCS bucket read |
| `lookup_incidents` | 2-legged OAuth via Auth Manager | ServiceNow REST API |
| `file_github_issue` | 3-legged OAuth via Auth Manager (post-consent) | GitHub Issues API |
| `get_weather` | API key via Auth Manager | OpenWeatherMap REST API |

The capstone is the **demo agent**. Stages 1–4 are individual labs that
teach each pattern in isolation; the capstone composes them.

---

## What you'll see in the demo

1. **A customer message** about a late order
2. **Ada calls four backends in parallel** — order DB, ServiceNow, weather service, all using different auth flows
3. **A synthesized response** that quotes specific facts from each tool
4. **Cloud Audit Logs** showing every external call was made *by Ada's specific SPIFFE principal* — never a shared service account, never a hardcoded key

Then optionally: "*Engineer, please file a bug ticket for the checkout issue*" and Ada files a GitHub issue **as the engineer** (3LO consent flow).

---

## Prerequisites

Everything needed for Stages 1–4. Specifically your `.env.local` must have:

```bash
export GOOGLE_CLOUD_PROJECT=...
export ORG_ID=...
export LOCATION=us-central1

# ServiceNow (2LO)
export SNOW_INSTANCE_URL=https://devXXXXX.service-now.com
export SNOW_CLIENT_ID=...
export SNOW_CLIENT_SECRET='...'        # single-quote to survive shell metachars

# GitHub (3LO)
export GH_CLIENT_ID=...
export GH_CLIENT_SECRET='...'
export GH_TEST_REPO=Cotomacio/ada-bug-reports
# In your GitHub OAuth App settings, set the callback URL to:
#   http://localhost:8080/callback

# OpenWeather (API key)
export OPENWEATHER_API_KEY='...'
```

Plus the M1 setup scripts already run once (APIs enabled, GCS bucket seeded).

---

## Deploy + configure (run once)

```bash
cd ~/secure-customer-service-agent/workshops/m1-agent-identity/labs/capstone-ada
source ../../.env.local
python -m venv .venv && source .venv/bin/activate
pip install -r agent/requirements.txt

unset REASONING_ENGINE_ID AGENT_IDENTITY
python deploy.py 2>&1 | tee deploy.log
```

After deploy.py prints the IDs, finish setup:

```bash
export REASONING_ENGINE_ID=<from deploy output>
export AGENT_IDENTITY=<from deploy output>

bash grant_access.sh                  # bucket grant
bash setup_servicenow_provider.sh     # 2LO connector
bash setup_openweather_provider.sh    # API-key connector
bash setup_github_provider.sh         # 3LO connector (does NOT yet authorize a user)
python consent_github.py              # one-time browser consent so Ada can file as you

sleep 180   # IAM propagation for the BETA Connector User role
```

> ⚠️ **GitHub OAuth App callback URL.** Before running `consent_github.py`,
> open https://github.com/settings/developers → your OAuth App → **Edit**
> → set the **Authorization callback URL** to `http://localhost:8080/callback`
> and save. The consent helper opens that local port to capture the redirect.

---

## Run the demo

```bash
# The flagship multi-tool scenario
python chat.py

# Specific examples
python chat.py "Where is order ACME-78214?"
python chat.py "Are there any active ServiceNow incidents?"
python chat.py "What's the weather in Denver right now?"
python chat.py "Please file a bug in Cotomacio/ada-bug-reports titled 'Checkout 500 on iOS', body referring to INC0010001"
```

The default prompt (no argument) is the multi-tool Maria scenario. Watch
the `↪ calling tool: ...` lines — multiple tools fire in parallel, each
authenticating with a different mechanism, all attributed to Ada's single
SPIFFE principal.

---

## Architecture in one diagram

```
                                ┌────────────────────────────────────┐
                                │  Ada (Agent Engine, ada-capstone)  │
                                │  SPIFFE: principal://...           │
                                └─┬────────┬─────────┬─────────┬─────┘
   ADC / DPoP-bound token         │        │         │         │
                                  │        │         │         │     retrieveCredentials()
                                  ▼        ▼         ▼         ▼
                              ┌──────┐ ┌──────────────────────────────────┐
                              │ GCS  │ │  Agent Identity Auth Manager     │
                              │      │ │  (iamconnectors)                 │
                              │orders│ │                                  │
                              │ .csv │ │  ┌─────────────┐ ┌─────────────┐ │
                              └──────┘ │  │ snow-2lo    │ │ github-3lo  │ │
                                       │  │ client+secret│ │ user OAuth  │ │
                                       │  └──────┬──────┘ └──────┬──────┘ │
                                       │         │               │        │
                                       │  ┌─────────────┐        │        │
                                       │  │ openweather │        │        │
                                       │  │ API key     │        │        │
                                       │  └──────┬──────┘        │        │
                                       └─────────┼───────────────┼────────┘
                                                 │               │
                            inject token         ▼               ▼
                                ┌──────────────────┐   ┌──────────────────┐
                                │ ServiceNow REST  │   │ GitHub Issues API│
                                │ /api/now/...     │   │ as logged-in user│
                                └──────────────────┘   └──────────────────┘
                                       │
                                       ▼
                                ┌──────────────────┐
                                │  api.openweather │
                                │  /weather?...    │
                                └──────────────────┘
```

**Zero secrets in Ada's container.** Every third-party credential lives in
Auth Manager. Ada fetches them via `iamconnectorcredentials.retrieveCredentials`
at call time, using only her SPIFFE identity.

---

## What customers/colleagues need to know

If you're handing this to a colleague to deploy themselves, the only
"manual" friction step is the GitHub OAuth consent — and that's
inherent to 3LO (the user *must* grant the agent permission via a
browser at least once). `consent_github.py` automates the rest.

After consent, the demo runs hands-off. Re-running `chat.py` doesn't
re-prompt for consent until the user revokes the GitHub OAuth grant.

---

## Cleanup (when you're done)

```bash
ENGINE_ID=$REASONING_ENGINE_ID
curl -X DELETE -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/$GOOGLE_CLOUD_PROJECT/locations/us-central1/reasoningEngines/${ENGINE_ID}?force=true"

# Optionally delete the three connectors too
for c in snow-incidents github-3lo openweather; do
  gcloud alpha agent-identity connectors delete "$c" \
    --location=us-central1 --project="$GOOGLE_CLOUD_PROJECT" --quiet
done
```

The 3 individual stage labs (`stage1-own-identity/`, etc.) remain
deployable separately for self-paced learning.
