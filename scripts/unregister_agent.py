"""Utility for unregistering agents and their authorizations in Gemini Enterprise."""

import json
import logging
import os
import subprocess
import requests

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
APP_ID = os.getenv("GEMINI_APP_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
AUTH_RESOURCE_ID = os.getenv("AUTH_RESOURCE_ID", "bq-caapi-oauth")

def get_gcloud_token() -> str:
    """Gets the current gcloud access token."""
    try:
        return subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    except subprocess.CalledProcessError as e:
        logger.error("Failed to get gcloud access token. Ensure you are authenticated.")
        raise RuntimeError("Authentication failed") from e

def unregister_agent_and_auth() -> None:
    """Find and delete the CBS agent and its authorization resource."""
    logger.info("Starting unregistration process...")
    token = get_gcloud_token()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Goog-User-Project": PROJECT_ID,
        "Content-Type": "application/json"
    }
    
    # 1. List all agents to find the one we created
    agents_url = (
        f"https://{LOCATION}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/"
        f"engines/{APP_ID}/assistants/default_assistant/agents"
    )
    
    logger.info(f"Fetching agent list from Gemini Enterprise...")
    response = requests.get(agents_url, headers=headers)
    
    if response.status_code == 200:
        agents = response.json().get("agents", [])
        
        # Look for agents using our specific display name or auth resource
        target_auth_string = f"projects/{PROJECT_NUMBER}/locations/global/authorizations/{AUTH_RESOURCE_ID}"
        
        agents_to_delete = []
        for agent in agents:
            display_name = agent.get("displayName", "")
            auth_config = agent.get("authorizationConfig", {})
            auths = auth_config.get("toolAuthorizations", [])
            
            # Match by Display Name OR if they are holding our Auth Resource hostage
            if display_name == "CBS Analyst" or target_auth_string in auths:
                agents_to_delete.append(agent.get("name"))
                
        if not agents_to_delete:
            logger.info("No existing 'CBS Analyst' agents found to delete.")
        
        # Delete the zombie agents
        for agent_name in agents_to_delete:
            logger.info(f"Deleting locked Agent: {agent_name}...")
            delete_agent_url = f"https://{LOCATION}-discoveryengine.googleapis.com/v1alpha/{agent_name}"
            del_resp = requests.delete(delete_agent_url, headers=headers)
            
            if del_resp.status_code == 200:
                logger.info(f"Successfully deleted Agent: {agent_name}")
            else:
                logger.error(f"Failed to delete Agent {agent_name}: {del_resp.text}")
    else:
        logger.error(f"Failed to list agents. HTTP {response.status_code}: {response.text}")


    # 2. Now that agents are clear, delete the Authorization resource
    auth_url = (
        f"https://global-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_NUMBER}/locations/global/authorizations/{AUTH_RESOURCE_ID}"
    )
    
    logger.info(f"Deleting Authorization Resource: {AUTH_RESOURCE_ID}...")
    auth_resp = requests.delete(auth_url, headers=headers)
    
    if auth_resp.status_code == 200:
        logger.info(f"Successfully deleted Authorization: {AUTH_RESOURCE_ID}")
    elif auth_resp.status_code == 404:
        logger.info(f"Authorization {AUTH_RESOURCE_ID} already deleted or not found.")
    else:
        logger.error(f"Failed to delete Authorization. HTTP {auth_resp.status_code}: {auth_resp.text}")
        
    logger.info("Unregistration routine complete! You can now safely run setup_auth.py again.")

if __name__ == "__main__":
    unregister_agent_and_auth()
