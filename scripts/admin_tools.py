"""Admin tools for managing Conversational Analytics agents."""

import logging
import os

from dotenv import load_dotenv
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.protobuf import field_mask_pb2

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
DATASET_ID = os.getenv("BIGQUERY_DATASET_ID")
AGENT_ID = os.getenv("AGENT_ID", os.getenv("AGENT_ORDERS_ID"))


def get_bq_refs(tables: list[str]) -> list[geminidataanalytics.BigQueryTableReference]:
    """Construct BigQuery table references.

    Args:
        tables: List of table IDs.

    Returns:
        List of BigQueryTableReference objects.
    """
    return [
        geminidataanalytics.BigQueryTableReference(
            project_id=PROJECT_ID, dataset_id=DATASET_ID, table_id=table
        )
        for table in tables
    ]


def update_agent_context(
    client: geminidataanalytics.DataAgentServiceClient,
    agent_id: str,
    description: str,
    system_instruction: str,
    tables: list[str],
) -> None:
    """Update an existing Data Agent's context.

    Args:
        client: DataAgentServiceClient instance.
        agent_id: ID of the agent to update.
        description: Description of the agent.
        system_instruction: System instruction for the agent.
        tables: List of BigQuery tables to include.
    """
    if not agent_id:
        logger.warning("AGENT_ID not set, skipping update.")
        return

    logger.info(f"Updating Agent Context: {agent_id}...")
    bq_refs = get_bq_refs(tables)

    datasource_references = geminidataanalytics.DatasourceReferences(
        bq=geminidataanalytics.BigQueryTableReferences(table_references=bq_refs)
    )

    context = geminidataanalytics.Context(
        system_instruction=system_instruction,
        datasource_references=datasource_references,
    )

    agent_path = client.data_agent_path(PROJECT_ID, LOCATION, agent_id)
    agent = geminidataanalytics.DataAgent(
        name=agent_path,
        data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
            published_context=context
        ),
        description=description,
    )

    try:
        # Check if agent exists
        client.get_data_agent(name=agent_path)
        logger.info(f"Agent {agent_id} found, updating...")

        update_mask = field_mask_pb2.FieldMask(
            paths=["description", "data_analytics_agent.published_context"]
        )
        request = geminidataanalytics.UpdateDataAgentRequest(
            data_agent=agent,
            update_mask=update_mask,
        )
        operation = client.update_data_agent(request=request)
        result = operation.result()
        logger.info(f"Agent {agent_id} updated successfully: {result.name}")

    except Exception as e:
        if "not found" in str(e).lower():
            logger.warning(
                f"Agent {agent_id} not found. Please create it first in the console "
                "or update your .env with an existing agent ID."
            )
        elif "permission denied" in str(e).lower() or "403" in str(e):
            logger.error(
                f"Permission denied for agent {agent_id}. Ensure your account has "
                "'roles/geminidataanalytics.dataAgentOwner' on project "
                f"'{PROJECT_ID}'."
            )
            raise
        else:
            logger.error(f"Failed to update agent {agent_id}: {e}", exc_info=True)
            raise


def list_agents(client: geminidataanalytics.DataAgentServiceClient) -> None:
    """List all agents in the project."""
    logger.info("Listing all agents in project...")
    request = geminidataanalytics.ListDataAgentsRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
    )
    try:
        page_result = client.list_data_agents(request=request)
        for agent in page_result:
            agent_id = agent.name.split("/")[-1]
            logger.info(
                f"Agent Found - ID: {agent_id}, DisplayName: {agent.display_name}, Description: {agent.description}"
            )
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")


if __name__ == "__main__":
    if not PROJECT_ID:
        logger.error("GOOGLE_CLOUD_PROJECT not set in environment.")
        exit(1)

    client = geminidataanalytics.DataAgentServiceClient()

    # Sync context for the single CBS agent
    update_agent_context(
        client,
        AGENT_ID,
        "CBS: Customer, Account and Transaction Analysis Agent.",
        (
            "You are an expert data analyst for the CBS system (Customer, Account, and Transaction). "
            "Help users answer questions about banking profiles, account masters, and transaction history."
        ),
        ["cbs_customer_profile", "cbs_account_master", "cbs_banking_transactions"],
    )

    list_agents(client)
