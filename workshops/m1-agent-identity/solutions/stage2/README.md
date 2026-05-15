# Stage 2 — Reference solution

Mirrors `labs/stage2-2lo-servicenow/`. Teaching points to highlight when reviewing:

1. **`agent/tools.py` — `lookup_incidents(query, limit, _credential=None)`.** The `_credential` kwarg is the ADK convention for a credential injected by `AuthenticatedFunctionTool`. The function reads `_credential.access_token` and uses it as the OAuth bearer in the outbound ServiceNow REST call. The ServiceNow client_id and client_secret never appear in this file.

2. **`agent/agent.py`.** Two patterns side by side: `lookup_order` is registered as a plain function tool, `lookup_incidents` is wrapped in `AuthenticatedFunctionTool(func=..., auth_config=AuthConfig(auth_scheme=GcpAuthProviderScheme(name="projects/.../connectors/snow-incidents")))`. The resource-name format `projects/{p}/locations/{l}/connectors/{name}` is the canonical reference shape.

3. **`setup_servicenow_provider.sh`.** Two `gcloud alpha agent-identity connectors` calls: one to create-or-update the connector with the ServiceNow OAuth credentials, one to grant Ada's SPIFFE principal `roles/iamconnectors.user` on the new resource. Idempotent.

4. **`deploy.py`.** Same single-step SDK pattern as Stage 1, with `SNOW_INSTANCE_URL` and `SNOW_PROVIDER_NAME` passed into the runtime via `env_vars` so the tool can construct its REST URL and reference the auth provider.

Do not show this folder to attendees during the lab. Show it during the debrief or for self-paced learners who get stuck.
