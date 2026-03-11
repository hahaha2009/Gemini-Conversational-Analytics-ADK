import os
import subprocess
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = "global"
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

# Load Auth Resource ID from environment
AUTH_RESOURCE_ID = os.getenv("AUTH_RESOURCE_ID", "bq-caapi-oauth")


def create_auth_resource(auth_id: str) -> None:
    """Create an OAuth authorization resource in Gemini Enterprise.

    Args:
        auth_id: The authorization resource ID to create.

    Raises:
        ValueError: If OAUTH_CLIENT_ID or OAUTH_CLIENT_SECRET is not set.
    """
    if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
        raise ValueError("OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set")

    logger.info(f"Creating Authorization Resource: {auth_id}...")

    # We use v1alpha for authorizations creation
    url = (
        f"https://{LOCATION}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/authorizations?authorizationId={auth_id}"
    )

    payload = {
        "name": f"projects/{PROJECT_ID}/locations/{LOCATION}/authorizations/{auth_id}",
        "serverSideOauth2": {
            "clientId": OAUTH_CLIENT_ID,
            "clientSecret": OAUTH_CLIENT_SECRET,
            "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?client_id="
            + OAUTH_CLIENT_ID
            + "&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Foauth-redirect&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent",
            "tokenUri": "https://oauth2.googleapis.com/token",
        },
    }

    try:
        token = (
            subprocess.check_output(["gcloud", "auth", "print-access-token"])
            .decode()
            .strip()
        )
    except Exception as e:
        logger.error(f"Failed to get token: {e}")
        return

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

    result = subprocess.run(cmd, capture_output=True, text=True)

    # HTTP 200 or 409 (Already Exists is fine)
    if result.returncode == 0:
        logger.info(f"Response for {auth_id}: {result.stdout}")
    else:
        logger.error(f"Failed to create {auth_id}: {result.stderr}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create OAuth authorization resources for Gemini Enterprise."
    )
    parser.add_argument(
        "--auth-id",
        type=str,
        default=AUTH_RESOURCE_ID,
        help=f"Authorization resource ID (default: {AUTH_RESOURCE_ID})",
    )

    args = parser.parse_args()

    create_auth_resource(args.auth_id)
