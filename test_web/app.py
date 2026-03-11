"""Test web app to simulate Gemini Enterprise OAuth passthrough flow."""

import json
import os
import secrets

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from google_auth_oauthlib.flow import Flow

# Load environment from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Allow OAuth scope changes (Google may add scopes like bigquery)
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Configuration
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REASONING_ENGINE_ID = os.getenv("REASONING_ENGINE_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
AUTH_RESOURCE_ID = os.getenv("AUTH_RESOURCE_ID", "bq-caapi-oauth")

if not PROJECT_ID or not REASONING_ENGINE_ID:
    raise ValueError(
        "Required environment variables: GOOGLE_CLOUD_PROJECT, REASONING_ENGINE_ID"
    )

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
REDIRECT_URI = "http://localhost:8080/auth/callback"

# Agent Engine API base URL
AGENT_ENGINE_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}"
    f"/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
)


def get_oauth_flow():
    """Create OAuth flow with client configuration."""
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )


@app.route("/")
def index():
    """Landing page - show login or redirect to chat."""
    if "access_token" in session:
        return redirect(url_for("chat"))
    return render_template("index.html")


@app.route("/auth/login")
def login():
    """Initiate Google OAuth flow."""
    flow = get_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["oauth_state"] = state
    # Store the PKCE code verifier
    if hasattr(flow, "code_verifier"):
        session["code_verifier"] = flow.code_verifier
    return redirect(authorization_url)


@app.route("/auth/callback")
def callback():
    """Handle OAuth callback."""
    flow = get_oauth_flow()
    # Restore the code verifier if it was saved
    if "code_verifier" in session:
        flow.code_verifier = session.pop("code_verifier")

    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session["access_token"] = credentials.token
    session["token_expiry"] = (
        credentials.expiry.isoformat() if credentials.expiry else None
    )

    # Get user info
    userinfo_response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=10,
    )
    if userinfo_response.ok:
        userinfo = userinfo_response.json()
        session["user_email"] = userinfo.get("email", "unknown")
    else:
        session["user_email"] = "unknown"

    return redirect(url_for("chat"))


@app.route("/chat")
def chat():
    """Chat interface."""
    if "access_token" not in session:
        return redirect(url_for("index"))

    return render_template(
        "chat.html",
        user_email=session.get("user_email", "unknown"),
        token_expiry=session.get("token_expiry"),
        reasoning_engine_id=REASONING_ENGINE_ID,
        auth_resource_id=AUTH_RESOURCE_ID,
    )


@app.route("/api/query", methods=["POST"])
def query():
    """Send query to Agent Engine with OAuth token in session state."""
    if "access_token" not in session:
        return {"error": "Not authenticated"}, 401

    data = request.get_json()
    message = data.get("message", "")

    if not message:
        return {"error": "Message is required"}, 400

    access_token = session["access_token"]
    user_email = session.get("user_email", "test-user")

    # Get GCP access token for API calls
    try:
        import subprocess

        gcp_token = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception as e:
        return {"error": f"Failed to get GCP token: {e}"}, 500

    headers = {
        "Authorization": f"Bearer {gcp_token}",
        "Content-Type": "application/json",
    }

    # Step 1: Create session with OAuth token in state
    # This simulates what Gemini Enterprise does
    session_payload = {
        "userId": user_email,
        "sessionState": {
            AUTH_RESOURCE_ID: access_token,  # Key part - token passed in state
        },
    }

    create_session_url = f"{AGENT_ENGINE_BASE}/sessions"
    session_response = requests.post(
        create_session_url,
        headers=headers,
        json=session_payload,
        timeout=30,
    )

    if not session_response.ok:
        return {"error": f"Failed to create session: {session_response.text}"}, 500

    # Extract session ID from operation response
    operation = session_response.json()
    # Session ID is in the operation name: .../sessions/SESSION_ID/operations/...
    session_name = operation.get("name", "")
    parts = session_name.split("/sessions/")
    if len(parts) < 2:
        return {"error": f"Could not parse session ID from: {session_name}"}, 500

    session_id = parts[1].split("/")[0]

    # Step 2: Query the agent
    query_url = f"{AGENT_ENGINE_BASE}:streamQuery"
    query_payload = {
        "input": {
            "message": message,
            "user_id": user_email,
            "session_id": session_id,
        },
        "sessionState": {
            AUTH_RESOURCE_ID: access_token,
        }
    }

    query_response = requests.post(
        query_url,
        headers=headers,
        json=query_payload,
        timeout=120,
    )

    if not query_response.ok:
        return {"error": f"Query failed: {query_response.text}"}, 500

    # Parse streaming response (newline-delimited JSON)
    response_text = ""
    for line in query_response.text.strip().split("\n"):
        if line:
            try:
                event = json.loads(line)
                content = event.get("content", {})
                parts = content.get("parts", [])
                for part in parts:
                    if "text" in part:
                        response_text += part["text"]
            except json.JSONDecodeError:
                continue

    return {
        "response": response_text or "No response from agent",
        "session_id": session_id,
    }


@app.route("/auth/logout")
def logout():
    """Clear session and logout."""
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Allow OAuth over HTTP for localhost
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    print(f"\nTest Web App Starting...")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Reasoning Engine: {REASONING_ENGINE_ID}")
    print(f"  Auth Resource ID: {AUTH_RESOURCE_ID}")
    print(f"\nOpen http://localhost:8080 in your browser\n")
    app.run(host="0.0.0.0", port=8080, debug=True)
