# Trustworthy Agents on Google Cloud — Workshop Series

> **This file is the series index.** The original single-doc draft has been replaced by a six-module workshop set (plus one bonus track) under [`workshops/`](workshops/). Each spine module is self-contained and depends only on earlier modules.

## The narrative

**Ada** is the customer-service copilot at **Acme Commerce**. Across the series she:

> M1 gets her credentials → M2 learns to defend against attacks → M3 gets cataloged so colleagues can find her → M4 gets a job description Acme legal can enforce → M5 moves into the secured corporate building → **M6 Acme installs the cameras that show every agent's every move.**
>
> *(Bonus B1: when Ada is asked to write and run code on the fly, she does it in a sealed room with no windows.)*

One protagonist, one company, six modules + one bonus.

## Module map

| # | Module | Status | What it teaches |
|---|---|---|---|
| **M1** | [Agent Identity Foundations](workshops/m1-agent-identity/README.md) | ✅ Drafted (Stage 1 fully runnable; Stages 2–4 specced, code-gen pending) | SPIFFE principal + Auth Manager's four flows: own-identity, 2LO, 3LO, API key |
| **M2** | [Secure Customer Service Agent (Model Armor + IAM data isolation)](workshops/m2-secure-csa/README.md) | 🟡 Drafted (workshop framing wraps existing [`repo/`](repo/) + [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) — validated 10/10 red-team) | Content safety guards, prompt-injection defense, BQ dataset isolation (`customer_service` vs `admin`) |
| **M3** | Agent Registry | ⚪ Planned | Catalog Ada's tools, replace hardcoded URLs with discovery, attach auth-manager bindings to registered resources |
| **M4** | Policies | ⚪ Planned | IAM policies w/ CEL on `mcp.tool.isDestructive`, Semantic Governance NL rules, Model Armor as a policy, DRY_RUN→ENFORCE |
| **M5** | Agent Gateway | ⚪ Planned | All Ada's traffic routed through one mTLS+DPoP-bound enforcement point |
| **M6** | Agent Observability *(capstone)* | ⚪ Planned | OpenTelemetry → Cloud Trace/Logging/Monitoring; the six-tab dashboard (Overview, Evaluation, Models, Tools, Usage, Logs); per-SPIFFE-ID slicing |
| **B1** | *Bonus —* Agent Sandbox | ⚪ Planned | Isolating LLM-generated Python at inference time; threat model for prompt-injected `pandas.to_csv` exfil and cross-tenant TTL bleed |

## Dependency DAG

```
M1 Identity ──► M2 Secure CSA ──► M3 Registry ──► M4 Policies ──► M5 Gateway ──► M6 Observability
                                                                                       ▲
                                                                                       │
                                       (every prior module emits telemetry into M6)────┘

Bonus B1 (Sandbox) ─── insertable any time after M2; light deps on M3/M4 if used
```

**Key design choice — Observability is a capstone, not a horizontal.** Each prior module's labs include forward-pointers (*"in M6 you'll see this in the Tools/Usage/Logs tab as ..."*) to keep telemetry motivated, but the actual dashboard work is taught once at the end after every emitter has been built. Otherwise you're showing students empty dashboards.

**Key design choice — Sandbox is a bonus, not in the spine.** It's about isolating *code the agent generates and executes*, not about hardening Ada's runtime. Different threat model, different audience interest. The 30-min standalone lab can be slotted any time after M2.

## Next steps

1. **Validate M1 Stage 1 end-to-end** by deploying against a real GCP project. The deploy.py is now reconciled against the working [`repo/deploy.py`](repo/deploy.py) (two-step deploy via v1beta1 SDK + `adk deploy`, no `--trace_to_cloud`, expressUser baseline). This is the smoke test for the whole narrative.
2. Decide on M2 packaging — **graft-onto-M1** (attendees grow their M1 Ada) or **start-from-repo** (attendees clone the existing scaffold). The current M2 README assumes start-from-repo. Flagged in M2's status section.
3. Generate Stage 2/3/4 reference solutions for M1 (specs already in their lab READMEs).
4. Outline M3 → M4 → M5 → M6 with the same Ada thread.
5. Write Bonus B1 standalone whenever it fits.

## Source docs

- [Agent Identity overview](https://docs.cloud.google.com/iam/docs/agent-identity-overview)
- [Authenticate using an agent's own authority](https://docs.cloud.google.com/iam/docs/auth-agent-own-identity)
- [Authenticate using 2-legged OAuth with auth manager](https://docs.cloud.google.com/iam/docs/auth-with-2lo)
- [Authenticate using 3-legged OAuth with auth manager](https://docs.cloud.google.com/iam/docs/auth-with-3lo)
- [Authenticate using API key with auth manager](https://docs.cloud.google.com/iam/docs/auth-with-api-key)
- [Agent Identity (Gemini Enterprise Agent Platform)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview)
- [Agent Registry overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry)
- [Policies overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/overview)
- [Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview)
- [Agent Observability overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/observability/overview)
- [Agent Sandbox / code execution overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sandbox/code-execution-overview)
