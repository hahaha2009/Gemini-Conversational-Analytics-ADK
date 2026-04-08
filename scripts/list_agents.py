import os
import logging
from dotenv import load_dotenv
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()

# We specify the target project
PROJECT_ID = "bqexplore-476017" # Since this is the project the user asked for
LOCATION = "global" # CA data agents are typically 'global'

logger.info(f"Listing Data Agents for project: {PROJECT_ID}...")

# Initialize DataChat client
client = geminidataanalytics.DataChatServiceClient()

try:
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"
    # Use standard ListDataAgents or list_data_agents
    # Let's try to find the method name. Usually it's list_data_agents
    # Since we use v1beta, we can try to find if it exists.
    # If it fails, we will search the client's available methods.
    
    # Python client often has list_data_agents(request=...)
    request = geminidataanalytics.ListDataAgentsRequest(parent=parent)
    response = client.list_data_agents(request=request)
    
    print("\n=== Data Agents List ===")
    for agent in response:
        print(f"Name: {agent.name}")
        print(f"Display Name: {agent.display_name}")
        print(f"Description: {agent.description}")
        print("-" * 20)
except AttributeError:
    logger.warning("No list_data_agents method found in client. Let's list available methods:")
    for method in dir(client):
        if not method.startswith("_"):
            print(method)
except Exception as e:
    logger.error(f"An error occurred: {e}")
