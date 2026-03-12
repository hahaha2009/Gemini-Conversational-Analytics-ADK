from __future__ import annotations

import logging
import os
import argparse
from dotenv import load_dotenv
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
AGENT_ID = os.getenv("AGENT_ID")

def query_direct(prompt: str) -> None:
    """Query the BigQuery Data Agent (CA API) directly using the chat method.

    Args:
        prompt: The natural language query.
    """
    if not PROJECT_ID or not AGENT_ID:
        logger.error("GOOGLE_CLOUD_PROJECT and AGENT_ID must be set in .env")
        return

    logger.info(f"Querying CA Agent Directly: {AGENT_ID}...")
    
    # Initialize DataChat client
    client = geminidataanalytics.DataChatServiceClient()
    
    # Construct agent path
    agent_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/dataAgents/{AGENT_ID}"
    
    # Construct the request for stateless chat
    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
        data_agent_context=geminidataanalytics.DataAgentContext(
            data_agent=agent_path
        ),
        messages=[
            geminidataanalytics.Message(
                user_message=geminidataanalytics.UserMessage(
                    text=prompt
                )
            )
        ]
    )

    try:
        stream = client.chat(request=request)
        
        print("\n=== Result ===")
        for message in stream:
            # Handle the response messages correctly using SystemMessage structure
            if message.system_message:
                sys_msg = message.system_message
                
                # Check for text response
                if sys_msg.text and sys_msg.text.parts:
                    print(f"Message: {' '.join(sys_msg.text.parts)}")
                
                # Check for data/SQL
                if sys_msg.data:
                    if sys_msg.data.generated_sql:
                        print(f"SQL Generated: \n{sys_msg.data.generated_sql}")
                    
                    if sys_msg.data.result and sys_msg.data.result.data:
                        print(f"Data: {len(sys_msg.data.result.data)} rows retrieved")
                        # Print actual data rows
                        print("-" * 20)
                        for i, row in enumerate(sys_msg.data.result.data):
                            # Convert Struct to a readable format
                            row_dict = dict(row)
                            print(f"Row {i+1}: {row_dict}")
                        print("-" * 20)
                
                # Check for errors
                if sys_msg.error:
                    print(f"Error: {sys_msg.error.text}")
            
    except Exception as e:
        logger.error(f"Failed to query CA agent: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query CA Agent Directly.")
    parser.add_argument("prompt", type=str, help="The query prompt.")
    args = parser.parse_args()

    query_direct(args.prompt)
