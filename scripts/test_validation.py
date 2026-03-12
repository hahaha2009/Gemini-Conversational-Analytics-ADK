import os
from google.adk.tools.data_agent import DataAgentCredentialsConfig
from dotenv import load_dotenv

load_dotenv()

try:
    creds_config = DataAgentCredentialsConfig(
        external_access_token_key=os.getenv("AUTH_RESOURCE_ID", "bq-caapi-oauth")
    )
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
