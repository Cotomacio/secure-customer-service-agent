# Stage 4 — Ada checks the weather at delivery (API key)

> *Customer in Denver: "Why is my package late?"*
> Acme's logistics team wants Ada to factor weather into ETA explanations. OpenWeather only supports API keys.

## Why this stage exists

Many useful APIs (especially long-tail third parties) don't speak OAuth. They authenticate with a static API key. Without Auth Manager, the temptation is to put the key in an env var or Secret Manager and pull it at startup — but that puts the key in agent memory, in `kubectl describe`, in process listings, and one careless `print()` away from a log leak.

Auth Manager's API-key provider keeps the key server-side: Ada's code only ever holds the **resource name** of the provider. Auth Manager injects the key into the outbound HTTP header server-side — Ada's process never reads the key value.

## Prerequisites

Complete `setup/30_signup_guide.md` § 3 (OpenWeather signup, ~10 min activation delay) and have:

```bash
OPENWEATHER_API_KEY=...
```

Stages 1–3 deployed.

## What's in this folder

- `agent.py` — Ada with the weather tool added
- `tools.py` — `get_weather(city)` referencing the API key auth provider
- `create_auth_provider.sh` — registers the OpenWeather API key provider
- `requirements.txt`

## Steps

```bash
source ../../.env.local

# 1. Create the API key auth provider.
bash create_auth_provider.sh
# Prints PROVIDER_RESOURCE_NAME.

# 2. Implement the TODOs in tools.py and agent.py.
#    Reference the provider by resource name. Do NOT read OPENWEATHER_API_KEY.

# 3. Redeploy and ask Ada about the weather.
python deploy.py
adk run-remote --reasoning-engine "$REASONING_ENGINE_ID"
> What's the weather in Denver right now? Could it delay my package?
```

## TODOs

1. **`tools.py` — `get_weather(city)`.** Wrap a function calling
   `https://api.openweathermap.org/data/2.5/weather?q={city}&units=imperial`
   in `AuthenticatedFunctionTool`. The auth config references the API key provider's resource name; Auth Manager adds `appid={API_KEY}` (or the configured header) server-side at egress.
2. **`agent.py`.** Add `get_weather` to Ada's tool list and instruct her: *"When asked about delivery delays, check the destination weather and explain plainly."*

## Verify

1. Functional: Ada explains Denver weather and connects it to the delivery delay.
2. Container check: `grep` Ada's image for the API key — not there.
3. Rotation drill: regenerate the OpenWeather key, update the auth provider, ask Ada again. No redeploy. **T8 closed.**

> 🔭 **Coming in M6:** OpenWeather call counts and error rates land in the **Usage** tab next to your free-tier daily quota — the dashboard catches a runaway loop *before* it eats your 1,000-call/day budget.

## Threats closed

- **T4** (no API key in code or image)
- **T8** (rotation is a config update, not a release)

## What's still exposed

- OpenWeather still receives the key as a bearer credential. If *they* leak it, you must rotate. Auth Manager helps you rotate fast but doesn't change the third-party trust model.
- Anyone with `iamconnectors.connectors.retrieveCredentials` on the provider can effectively use the key indirectly. M4 (Policies, Principal Access Boundary) constrains this.

## Status of this scaffold

Solution deferred. README is the spec.
