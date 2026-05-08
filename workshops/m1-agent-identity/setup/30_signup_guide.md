# M1 — External Signup Guide

You'll need three external accounts before the labs. **Start the ServiceNow signup first** — its provisioning takes the longest.

---

## 1. ServiceNow Personal Developer Instance (Stage 2 — 2LO)

**Time:** 15–30 min including instance provisioning.

1. Go to https://developer.servicenow.com/ and click **Sign in / Register** → register with email.
2. After verifying your email, go to **Account → Manage → Instance** → **Request Instance**.
3. Pick the latest LTS release (any will do for the lab).
4. Wait for the email "Your developer instance is ready." Note the URL: `https://devXXXXX.service-now.com`.

**Create an OAuth client (machine-to-machine / 2LO):**

1. Log into your instance as `admin` (credentials are emailed).
2. Navigate to **System OAuth → Application Registry**.
3. Click **New** → **Create an OAuth API endpoint for external clients**.
4. Name: `ada-acme-incidents`. Leave defaults.
5. Save. Note the **Client ID** and **Client Secret** (click the lock to reveal the secret).
6. Token URL: `https://devXXXXX.service-now.com/oauth_token.do`

**What to record for the lab:**
- Instance URL: `https://devXXXXX.service-now.com`
- Token URL: `https://devXXXXX.service-now.com/oauth_token.do`
- Client ID
- Client Secret

> ⚠️ ServiceNow PDIs hibernate after 10 days of inactivity. If yours has been asleep, wake it from the developer portal before running Stage 2.

---

## 2. GitHub OAuth App (Stage 3 — 3LO)

**Time:** ~5 min.

1. While logged into GitHub, go to **Settings → Developer settings → OAuth Apps → New OAuth App**.
   - Direct link: https://github.com/settings/applications/new
2. Fill in:
   - **Application name:** `Ada — Acme Commerce Support Copilot`
   - **Homepage URL:** any URL you control, or `https://example.com` for the workshop
   - **Authorization callback URL:** *leave a placeholder for now* — you'll replace it with the URL Auth Manager generates when you create the auth provider in Stage 3
3. Click **Register application**.
4. Click **Generate a new client secret**. Copy and store it immediately — GitHub shows it once.

**What to record for the lab:**
- Client ID
- Client Secret

**Recommended scopes** (set during auth-provider creation, not on the GitHub app):
- For workshop: `public_repo` (lets Ada open issues on a public repo you own)
- For "real" use: `repo` (private repos) — but review this with security; broader scope = bigger T9 surface.

**Create a test repo** to receive Ada's bug reports:
```bash
gh repo create ada-bug-reports --public --description "Ada test repo"
```

---

## 3. OpenWeather API key (Stage 4 — API key)

**Time:** ~5 min signup, **+10 min activation delay**.

1. Sign up at https://openweathermap.org/api → **Sign Up**.
2. Verify your email.
3. Go to **API keys** in your profile. A default key is already generated. Optionally create a second one named `ada-acme-stage4`.
4. **Wait ~10 minutes** before testing — new keys take a moment to activate. While you wait, do Stage 1.

**What to record for the lab:**
- API key (32-char hex string)

**Free-tier limits:** 1,000 calls/day, 60/min — plenty for the workshop. The endpoint we'll use is `/data/2.5/weather?q={city}&appid={KEY}`.

---

## Summary — what should be in your `.env.local`

Create `workshops/m1-agent-identity/.env.local` (gitignored) with:

```bash
# Google Cloud
export GOOGLE_CLOUD_PROJECT=your-project
export ORG_ID=your-org-id
export LOCATION=us-central1

# ServiceNow (Stage 2)
export SNOW_INSTANCE_URL=https://devXXXXX.service-now.com
export SNOW_CLIENT_ID=...
export SNOW_CLIENT_SECRET=...   # used only to register the auth provider; never read by Ada at runtime

# GitHub (Stage 3)
export GH_CLIENT_ID=...
export GH_CLIENT_SECRET=...     # same — registration only
export GH_TEST_REPO=your-username/ada-bug-reports

# OpenWeather (Stage 4)
export OPENWEATHER_API_KEY=...  # registration only
```

> The point of M1 is that **none of these secrets reach Ada's runtime**. They are entered into Auth Manager once during provider creation, and Ada accesses them only via `iamconnectors.connectors.retrieveCredentials` calls — Auth Manager injects the actual credentials into outbound requests server-side, after Ada's process has handed the call off. *(Under the hood this rides on Agent Gateway with mTLS+DPoP; M5 is when you make that layer visible and configurable.)*
