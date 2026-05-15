# Web UI — Streamlit chat for Ada, deployed on Cloud Run

A minimal browser chat for talking to any deployed Ada engine (Stage 1, 2, 3, 4, or the capstone). Designed for demos and for colleagues who want to play with Ada without running CLI scripts.

## What it does

- Web chat UI with conversation history
- Streams Ada's responses (text + tool calls + tool results) in real time
- Reads which engine to talk to from `REASONING_ENGINE_ID` env var — point it at any deployed Ada

## What it looks like

```
┌─────────────────────────────────────────────────────────┐
│ 🛒 Ada — Acme Commerce Support                          │
├─────────────────────────────────────────────────────────┤
│  user:  Where is order ACME-78214 and what's the        │
│         weather in Denver?                              │
│                                                         │
│  Ada:   🔧 lookup_order(`order_id`=ACME-78214)          │
│         ↩️ result: {found: True, customer: Maria, ...} │
│         🔧 get_weather(`city`=Denver)                   │
│         ↩️ result: {temp: 78, conditions: clear, ...}  │
│                                                         │
│         Your order to Denver is out for delivery        │
│         and weather looks clear (78°F).                 │
├─────────────────────────────────────────────────────────┤
│ [ Ask Ada about an order, weather, incidents… ]         │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- A deployed Ada (any stage's engine, or the capstone). You need its `REASONING_ENGINE_ID`.
- `gcloud` authenticated with permission to deploy Cloud Run services in your project.
- `$GOOGLE_CLOUD_PROJECT` and `$LOCATION` set.

## Deploy

```bash
cd ~/secure-customer-service-agent/workshops/m1-agent-identity/labs/web-ui

# Point the UI at whichever Ada engine you want it to talk to
export REASONING_ENGINE_ID="<engine id of the Ada to chat with>"

bash deploy.sh
```

`deploy.sh`:

1. Enables Cloud Run + Cloud Build APIs (idempotent)
2. Grants the runtime SA `roles/aiplatform.user` (so it can invoke the Agent Engine)
3. `gcloud run deploy --source .` — Cloud Build builds the Dockerfile and ships
4. Prints the Cloud Run URL

Open the URL in a browser. Chat with Ada.

## Run locally first (optional)

If you want to iterate on the UI before deploying:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_CLOUD_PROJECT=...
export LOCATION=us-central1
export REASONING_ENGINE_ID=...
streamlit run app.py
```

Streamlit serves on `http://localhost:8501` by default.

## Auth model

| Surface | Identity | What it can do |
|---|---|---|
| **Cloud Run URL** | Public (--allow-unauthenticated) | Anyone with the URL can chat. Fine for demos / colleague playground. For production, layer on IAP or Cloud Run IAM. |
| **Cloud Run → Agent Engine** | Cloud Run runtime SA (default compute SA unless overridden) | The deploy script grants this SA `roles/aiplatform.user` on the project. Just enough to invoke the engine. |
| **Agent Engine → backends (GCS, ServiceNow, OpenWeather, GitHub)** | Ada's SPIFFE identity (`AGENT_IDENTITY`) | Set up per-stage. The web UI doesn't change this — Ada still authenticates to backends with the same per-agent IAM you configured during deploy. |

**Important**: the Cloud Run service identity is **not** the same as Ada's SPIFFE identity. Ada's identity is enforced by Agent Engine at the per-engine level. The Cloud Run SA only has permission to *invoke* the engine, not to read GCS/ServiceNow/etc. directly.

## Production hardening (when you're past the demo)

```bash
# Remove the public URL — require IAP authentication
gcloud run services update "$ADA_WEB_SERVICE" \
  --region="$LOCATION" \
  --no-allow-unauthenticated

# Then either:
#   - Add IAP: https://cloud.google.com/iap/docs/enabling-cloud-run
#   - Or grant specific users/groups roles/run.invoker:
gcloud run services add-iam-policy-binding "$ADA_WEB_SERVICE" \
  --region="$LOCATION" \
  --member="user:colleague@acme.example" \
  --role="roles/run.invoker"
```

For multi-user demos where each user should consent to GitHub themselves (per the 3LO flow), you'd also want a Google sign-in / IAP integration so the `user_id` passed to `stream_query` matches a real human's identifier — out of scope for M1's web UI; possibly covered in M5 Agent Gateway when IAP integration becomes the canonical pattern.

## Customizing the agent shown

```bash
# Change the display name
export AGENT_DISPLAY_NAME="Cymbal Concierge"
bash deploy.sh
```

The page title and chat header update automatically.

## Cleanup

```bash
gcloud run services delete "$ADA_WEB_SERVICE" --region="$LOCATION" --quiet
```
