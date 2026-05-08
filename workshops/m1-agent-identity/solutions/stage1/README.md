# Stage 1 — Reference solution

Files mirror `labs/stage1-own-identity/` but with the `# TODO`s implemented.

The teaching points to highlight when reviewing:

1. **`storage.Client()` takes no arguments.** Never construct it with explicit credentials, key paths, or env-var lookups. ADC + Agent Identity is the contract.
2. **`identity_type="AGENT_IDENTITY"` in `deploy.py` is the entire module in one line.** Without it, Ada deploys with a default service account and everything else in the workshop is meaningless.
3. **`grant_access.sh` constructs the `principal://...spiffe...` URI from env vars.** This format is identical across M2–M5 — bind it in your head now.

Do not show this folder to attendees during the lab. Show it during the debrief or for self-paced learners who get stuck.
