"""Utility for registering A2A agents in Gemini Enterprise."""

import json
import logging
import os
import subprocess

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


def register_agent(
    display_name: str,
    description: str,
    reasoning_engine_resource: str,
    auth_resource: str | None = None,
) -> None:
    """Register an ADK agent with Gemini Enterprise via REST API.

    Args:
        display_name: The name to display in the UI.
        description: A brief description of the agent.
        reasoning_engine_resource: The full resource name of the deployed Agent Engine.
        auth_resource: The full path to an authorization resource.
    """
    logger.info(f"Registering {display_name}...")

    # We use curl to call the REST API as it's easier to handle the v1alpha endpoint
    try:
        token = (
            subprocess.check_output(["gcloud", "auth", "print-access-token"])
            .decode()
            .strip()
        )
    except subprocess.CalledProcessError as e:
        logger.error("Failed to get gcloud access token. Ensure you are authenticated.")
        raise RuntimeError("Authentication failed") from e

    url = (
        f"https://{LOCATION}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/"
        f"engines/{APP_ID}/assistants/default_assistant/agents"
    )

    # Construct payload for ADK Agent (Agent Engine)
    payload = {
        "displayName": display_name,
        "description": description,
        "adkAgentDefinition": {
            "provisionedReasoningEngine": {"reasoningEngine": reasoning_engine_resource}
        },
    }

    if auth_resource:
        payload["authorizationConfig"] = {"toolAuthorizations": [auth_resource]}

    cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Content-Type: application/json",
        "-H",
        f"X-Goog-User-Project: {PROJECT_ID}",
        url,
        "-d",
        json.dumps(payload),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        response_json = json.loads(result.stdout)
        if "error" in response_json:
            logger.error(
                f"Registration failed for {display_name}: {response_json['error']}"
            )
        else:
            logger.info(
                f"Successfully registered {display_name}: {response_json.get('name')}"
            )
    else:
        logger.error(
            f"Failed to execute registration command for {display_name}: {result.stderr}"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Register the CBS agent with Gemini Enterprise."
    )
    parser.add_argument(
        "--resource-name",
        required=True,
        help="Reasoning Engine resource name for the CBS Agent",
    )

    args = parser.parse_args()

    register_agent(
        "CBS Analyst",
        "Expert in Customer, Account, and Transaction analysis.",
        args.resource_name,
        auth_resource=f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/authorizations/{AUTH_RESOURCE_ID}",
    )
