# Stage 2 — Ada checks ServiceNow incidents (2-legged OAuth)

> *Customer: "I keep getting a checkout error."* Before bothering an engineer, Ada wants to ask Acme's ServiceNow whether there's a known incident affecting checkout.

## Why 2-legged?

Stage 1 was Ada talking to Google APIs *as herself*. Stage 2 is Ada talking to a third-party (ServiceNow) *as herself* — no end user is delegating authority. This is **machine-to-machine** OAuth: the agent uses a `client_id` + `client_secret` pair to fetch a bearer token via the `client_credentials` grant.

The catch: **we still don't want the secret in Ada's code or container.** That's the whole reason for Auth Manager. The secret is uploaded once to the auth provider; Ada only references it by resource name.

## Prerequisites

Complete `setup/30_signup_guide.md` § 1 (ServiceNow PDI) and have these in your `.env.local`:

```bash
SNOW_INSTANCE_URL=https://devXXXXX.service-now.com
SNOW_CLIENT_ID=...
SNOW_CLIENT_SECRET=...
```

Stage 1 must be working — Ada's reasoning engine + SPIFFE principal already exist.

## What's in this folder

- `agent.py` — Ada's agent definition with the new ServiceNow tool registered
- `tools.py` — `lookup_incidents()` wrapping `AuthenticatedFunctionTool`
- `create_auth_provider.sh` — registers the ServiceNow 2LO provider in Auth Manager
- `grant_connector_access.sh` — binds Ada to `roles/iamconnectors.user`
- `requirements.txt`

## Steps

```bash
source ../../.env.local

# 1. Create the 2LO auth provider in Auth Manager.
#    The script reads SNOW_CLIENT_ID / SNOW_CLIENT_SECRET / SNOW_INSTANCE_URL
#    from your env and POSTs to iamconnectors.googleapis.com.
bash create_auth_provider.sh
# Note the printed PROVIDER_RESOURCE_NAME — you'll reference it in tools.py.

# 2. Grant Ada permission to use auth providers.
bash grant_connector_access.sh

# 3. Implement the TODOs in tools.py and agent.py.
#    The auth provider is referenced by its resource name — never the secret.

# 4. Redeploy Ada with the new tool registered.
python deploy.py

# 5. Verify
adk run-remote --reasoning-engine "$REASONING_ENGINE_ID"
> Are there any active incidents related to checkout?
```

## TODOs

1. **`tools.py` — `lookup_incidents()`.** Wrap a function that calls
   `GET ${SNOW_INSTANCE_URL}/api/now/table/incident?sysparm_query=...&sysparm_limit=5`
   in `AuthenticatedFunctionTool`. The `AuthConfig` should reference the
   auth provider resource name printed by `create_auth_provider.sh`. **Do not
   read `SNOW_CLIENT_SECRET` here** — Auth Manager injects the bearer token server-side, after Ada has handed off the request.
2. **`agent.py`.** Add `lookup_incidents` to Ada's tool list and update her
   instructions: *"If a customer reports an issue, check ServiceNow for known incidents first."*

## Verify

1. Functional: Ada answers *"Are there any active checkout incidents?"* by quoting incident numbers.
2. Outbound check: tail Ada's runtime logs. The bearer token is added server-side by Auth Manager — it should appear in **no** log line written by Ada's code.
3. Container check: `grep` Ada's deployed image for the ServiceNow client secret. Not there.
4. Rotation drill (optional): rotate the client secret in ServiceNow, update the auth provider config, ask Ada the same question. **No agent redeploy** — that's the point.

> 🔭 **Coming in M6:** ServiceNow appears as a distinct provider in the **Tools** tab. Token-fetch latency is reported separately from API-call latency — when ServiceNow is slow, you'll know whether to call the ServiceNow team or the Auth Manager team.

## Threats closed

- **T4** (no client secret in agent code or image)
- **T8** (rotation is a config update on the provider, not a code release)

## What's still exposed

ServiceNow only sees "Acme Commerce's Ada agent" — there is no per-user attribution because no user delegated authority. That's correct for incident lookup but **wrong** for actions like "file a bug *as Pat*". Stage 3 introduces 3LO for per-user delegation.

## Status of this scaffold

Solution files are intentionally deferred to a follow-up iteration of M1 — the workshop owner should validate the framing in `README.md` before generating reference code. The TODO-style starters above are sufficient for instructor-led use.
