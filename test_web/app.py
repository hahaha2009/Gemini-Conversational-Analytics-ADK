"""Test web app to simulate Gemini Enterprise OAuth passthrough flow."""

import json
import os
import secrets
import traceback

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.protobuf.json_format import MessageToDict

# Load environment from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Allow OAuth scope changes (Google may add scopes like bigquery)
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Configuration
DIRECT_CA_MODE = os.getenv("DIRECT_CA_MODE", "TRUE").upper() == "TRUE"

# Configuration
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
REASONING_ENGINE_ID = os.getenv("REASONING_ENGINE_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
# Reasoning Engines are regional, while CA API is often global.
RE_LOCATION = os.getenv("REASONING_ENGINE_LOCATION") or (
    "us-central1" if LOCATION == "global" else LOCATION
)
AUTH_RESOURCE_ID = os.getenv("AUTH_RESOURCE_ID", "bq-caapi-oauth")
AGENT_ID = os.getenv("AGENT_ID")

if not PROJECT_ID or (not REASONING_ENGINE_ID and not DIRECT_CA_MODE):
    raise ValueError(
        "Required environment variables: GOOGLE_CLOUD_PROJECT, REASONING_ENGINE_ID (or AGENT_ID for direct mode)"
    )

if DIRECT_CA_MODE and not AGENT_ID:
    raise ValueError("AGENT_ID must be set for DIRECT_CA_MODE=TRUE")

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
REDIRECT_URI = "http://localhost:8080/auth/callback"

# Agent Engine API base URL
AGENT_ENGINE_BASE = (
    f"https://{RE_LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}"
    f"/locations/{RE_LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
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

    if DIRECT_CA_MODE:
        # DIRECT CA MODE: Call CA API directly using user's token
        try:
            creds = Credentials(token=access_token)
            gda_client = geminidataanalytics.DataChatServiceClient(credentials=creds)
            agent_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/dataAgents/{AGENT_ID}"
            
            # Construct direct stateless chat request
            request_data = geminidataanalytics.ChatRequest(
                parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
                data_agent_context=geminidataanalytics.DataAgentContext(
                    data_agent=agent_path
                ),
                messages=[
                    geminidataanalytics.Message(
                        user_message=geminidataanalytics.UserMessage(text=message)
                    )
                ]
            )
            
            stream = gda_client.chat(request=request_data)
            response_parts = []
            for msg in stream:
                if msg.system_message:
                    sys_msg = msg.system_message
                    
                    # Handle text response
                    if sys_msg.text and sys_msg.text.parts:
                        # Convert to dict for safer access if direct parts iteration fails
                        text_dict = MessageToDict(sys_msg.text._pb)
                        parts = text_dict.get("parts", [])
                        if parts:
                            response_parts.append(" ".join(parts))
                        
                    # Handle data/SQL
                    if sys_msg.data:
                        if sys_msg.data.generated_sql:
                            # response_parts.append(f"\nSQL: {sys_msg.data.generated_sql}")
                            pass
                        if sys_msg.data.result and sys_msg.data.result.data:
                            response_parts.append(f"\n({len(sys_msg.data.result.data)} rows retrieved):")
                            msg_dict = MessageToDict(sys_msg.data.result._pb)
                            data_rows = msg_dict.get("data", [])
                            for i, row in enumerate(data_rows[:5]):
                                response_parts.append(f"Row {i+1}: {row}")
                    
                    # Handle errors returned in the protocol
                    if sys_msg.error:
                        response_parts.append(f"Error from Agent: {sys_msg.error.text}")
            
            return {
                "response": " ".join(response_parts) or "Direct CA responded, but no visible message found.",
                "session_id": "direct-ca-session",
            }
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Direct CA Chat failed: {e}"}, 500

    # MIDDLEWARE MODE (Default): Call Reasoning Engine (ADK Agent)
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
            # Pass token inside input for Reasoning Engine REST API
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
