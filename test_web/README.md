# Test Web App

Simple Flask app to test OAuth passthrough to Agent Engine.

## Setup

```bash
cd test_web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Prerequisites

1. OAuth redirect URI configured in Google Cloud Console:
   - Add `http://localhost:8080/auth/callback` to your OAuth client

2. Agent deployed to Agent Engine with the token bridge callback

3. Environment variables in `../.env`:
   - `OAUTH_CLIENT_ID`
   - `OAUTH_CLIENT_SECRET`
   - `GOOGLE_CLOUD_PROJECT`
   - `ORDERS_REASONING_ENGINE_ID`
   - `AUTH_RESOURCE_ORDERS`

## Run

```bash
python app.py
```

### Accessing from outside Cloudtop

If you are running this app on a Cloudtop instance but want to access it from your local laptop's browser (e.g. your MacBook), you should use SSH local port forwarding. This ensures the `http://localhost:8080/auth/callback` OAuth configuration still works perfectly.

Run this command **from your local laptop's terminal** (replace `cloudtop-ynd-glinux` with your actual Cloudtop hostname):

```bash
ssh -L 8080:localhost:8080 cloudtop-ynd-glinux.c.googlers.com
```

Once connected, open [http://localhost:8080](http://localhost:8080) in your *local* laptop's browser.

## How It Works

1. Login with Google OAuth
2. App captures your access token
3. When you send a query:
   - Creates Agent Engine session with token in `sessionState["bq-caapi-oauth"]`
   - Calls `:streamQuery`
   - Agent's bridge callback copies token to `data_agent_token_cache`
   - DataAgentToolset uses your token for BigQuery queries
4. Results displayed in chat
