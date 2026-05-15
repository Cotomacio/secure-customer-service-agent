# Stage 4 — Reference solution

Mirrors `labs/stage4-apikey-openweather/`. Same pattern as Stage 2 but with
OpenWeather + API-key auth provider instead of ServiceNow + 2LO.

Note: Stage 4 may hit the same preview-API blocker as Stage 2 if the API-key
auth provider also requires an `Authorization` resource that the current
`gcloud alpha agent-identity connectors authorizations` surface does not
expose a `create` verb for. The codelab cloudnet-agent-gateway demonstrates
API-key providers working via the MCP tool pattern, so the API-key path
*may* auto-create the authorization on first retrieve. Verify by running
the lab.

If Stage 4 hits the same 404 as Stage 2, fall back to Cloud Secret Manager
as the interim production pattern (same security boundary, different storage).
