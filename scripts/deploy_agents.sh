#!/bin/bash

# Deployment script for ADK Agents to Vertex AI Agent Engine

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== ADK Agent Deployment Script ===${NC}"
echo ""

# Load environment variables from root .env
if [ -f .env ]; then
    echo -e "${GREEN}Loading environment variables from .env${NC}"
    export $(cat .env | xargs)
else
    echo -e "${RED}ERROR: .env file not found in project root${NC}"
    exit 1
fi

# Verify required environment variables
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo -e "${RED}ERROR: GOOGLE_CLOUD_PROJECT not set${NC}"
    exit 1
fi

if [ -z "$OAUTH_CLIENT_ID" ] || [ -z "$OAUTH_CLIENT_SECRET" ]; then
    echo -e "${RED}ERROR: OAuth credentials not set${NC}"
    exit 1
fi

echo -e "${GREEN}Environment loaded${NC}"
echo "  Project: $GOOGLE_CLOUD_PROJECT"
echo ""

PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
# NOTE: While CA API uses 'global', Reasoning Engine deployment MUST be regional (e.g., us-central1)
LOCATION=${GOOGLE_CLOUD_LOCATION:-us-central1}
if [ "$LOCATION" == "global" ]; then
    LOCATION="us-central1"
fi

deploy_agent() {
    local agent_dir=$1
    local display_name=$2
    
    echo -e "${YELLOW}Deploying $display_name...${NC}"
    
    # Use a folder INSIDE the project directory to satisfy ADK security checks
    local temp_dir="deploy_staging_${display_name// /_}"
    mkdir -p "$temp_dir"

    .venv/bin/adk deploy agent_engine "$agent_dir" \
        --project="$PROJECT_ID" \
        --region="$LOCATION" \
        --display_name="$display_name" \
        --temp_folder="$temp_dir" \
        --env_file="$(pwd)/.env"
    
    echo -e "${GREEN}$display_name deployment command finished.${NC}"
    echo -e "${YELLOW}IMPORTANT: Check if a 'Reasoning Engine' ID was printed above.${NC}"
}

echo -e "${YELLOW}=== Deploying CBS Agent ===${NC}"
deploy_agent "app/cbs" "CBS Analyst"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Note the Reasoning Engine ID from the output above"
echo "2. Update .env with REASONING_ENGINE_ID"
echo "3. Register with Gemini Enterprise: .venv/bin/python scripts/register_agents.py"
