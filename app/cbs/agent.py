from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.data_agent import DataAgentCredentialsConfig, DataAgentToolset
from google.adk.tools.tool_context import ToolContext

import google.auth
import google.auth.transport.requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AGENT_ID = os.getenv("AGENT_ID", "agent-id-placeholder")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-id-placeholder")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash")
AUTH_RESOURCE_ID = os.getenv("AUTH_RESOURCE_ID", "bq-caapi-oauth")

DATA_AGENT_NAME = f"projects/{PROJECT_ID}/locations/global/dataAgents/{AGENT_ID}"

# OAuth Configuration
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
TOKEN_CACHE_KEY = "data_agent_token_cache"


async def bridge_oauth_token(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """Bridge OAuth token from Gemini Enterprise to DataAgentToolset.

    Copies the access token from the Gemini Enterprise location (AUTH_RESOURCE_ID)
    to the DataAgentToolset expected location (TOKEN_CACHE_KEY).

    Fallback: If running locally (terminal), fetches a token from ADC.
    """
    access_token = tool_context.state.get(AUTH_RESOURCE_ID)

    if not access_token:
        # Fallback for local terminal testing (adk run)
        logger.info(f"No token at '{AUTH_RESOURCE_ID}', attempting local ADC fallback...")
        try:
            creds, _ = google.auth.default(scopes=SCOPES)
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)
            access_token = creds.token
        except Exception as e:
            logger.error(f"Failed to fetch local ADC token: {e}")
            return None

    if access_token:
        # Crucial: Ensure the token is in the expected state location for DataAgentToolset
        tool_context.state[AUTH_RESOURCE_ID] = access_token
        
        # Bridging/Setting token for other tools that might use the old cache key
        expiry_time = (datetime.utcnow() + timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        token_data = {
            "token": access_token,
            "refresh_token": "",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "scopes": SCOPES,
            "expiry": expiry_time,
        }
        tool_context.state[TOKEN_CACHE_KEY] = json.dumps(token_data)
        
        logger.info(
            f"OAuth token bridged to '{AUTH_RESOURCE_ID}' and '{TOKEN_CACHE_KEY}'"
        )
    else:
        logger.warning(f"No token found at '{AUTH_RESOURCE_ID}'")

    return None


# Credentials config for OAuth identity passthrough
creds_config = DataAgentCredentialsConfig(
    external_access_token_key=AUTH_RESOURCE_ID,
)

data_agent_toolset = DataAgentToolset(credentials_config=creds_config)

root_agent = Agent(
    name="cbs_analyst",
    model=MODEL_NAME,
    instruction=(
        f"You are the CBS Analyst. Help users analyze data from the CBS system using: {DATA_AGENT_NAME}. "
        "Summarize results concisely and accurately."
    ),
    tools=[data_agent_toolset],
    description="Agent for Customer, Account and Transaction analysis.",
    before_tool_callback=bridge_oauth_token,
)
