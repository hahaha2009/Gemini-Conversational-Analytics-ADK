"""Reference implementation: CA API with chart support.

This script demonstrates how to call the Conversational Analytics API directly
(via REST) to capture chart responses that the ADK's DataAgentToolset ignores.

The ADK's built-in DataAgentToolset only processes text, schema, and data messages.
This example shows how to also capture chart messages containing Vega-Lite specs.

Key differences from DataAgentToolset:
- Parses `systemMessage.chart.result.vegaConfig` for Vega-Lite specifications
- Parses `systemMessage.chart.result.image` for pre-rendered chart images
- Renders Vega-Lite charts locally using Altair

Usage:
    python docs/examples/chart_with_ca_api.py

Requirements:
    pip install altair requests python-dotenv
"""

import json
import os
import subprocess

import altair as alt
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATA_AGENT_ID = os.getenv("AGENT_ORDERS_ID")
LOCATION = "global"

DATA_AGENT_NAME = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/dataAgents/{DATA_AGENT_ID}"
)
BASE_URL = "https://geminidataanalytics.googleapis.com/v1beta"


def get_access_token() -> str:
    """Get access token from gcloud."""
    return (
        subprocess.check_output(["gcloud", "auth", "print-access-token"])
        .decode()
        .strip()
    )


def render_vega_chart(vega_config: dict, output_path: str = "chart.png"):
    """Render Vega-Lite chart and save as image.

    Args:
        vega_config: The Vega-Lite specification dict.
        output_path: Path to save the rendered chart image.

    Returns:
        The Altair chart object.
    """
    print(f"\n=== Vega-Lite Spec ===")
    print(json.dumps(vega_config, indent=2)[:2000])
    if len(json.dumps(vega_config)) > 2000:
        print("... (truncated)")

    chart = alt.Chart.from_dict(vega_config)
    chart.save(output_path)
    print(f"\nChart saved to: {output_path}")
    return chart


def chat_with_chart_rest(prompt: str):
    """Send a prompt to CA API via REST and handle chart responses.

    Args:
        prompt: The question/prompt to send to the data agent.

    Returns:
        List of parsed messages.
    """
    print(f"\n=== Sending prompt ===")
    print(f"Data Agent: {DATA_AGENT_NAME}")
    print(f"Prompt: {prompt}")

    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Chat endpoint (same as ADK uses)
    chat_url = f"{BASE_URL}/projects/{PROJECT_ID}/locations/{LOCATION}:chat"

    payload = {
        "messages": [{"userMessage": {"text": prompt}}],
        "dataAgentContext": {
            "dataAgent": DATA_AGENT_NAME,
        },
    }

    print(f"\n=== Streaming response ===")

    # Make streaming request
    messages = []
    chart_found = False

    with requests.post(chat_url, json=payload, headers=headers, stream=True) as resp:
        if resp.status_code != 200:
            print(f"[ERROR] HTTP {resp.status_code}: {resp.text[:500]}")
            return messages

        accumulator = ""

        for line in resp.iter_lines():
            if not line:
                continue

            decoded_line = line.decode("utf-8")

            # Handle JSON array streaming format
            if decoded_line == "[{":
                accumulator = "{"
            elif decoded_line == "}]":
                accumulator += "}"
            elif decoded_line == ",":
                continue
            else:
                accumulator += decoded_line

            try:
                data_json = json.loads(accumulator)
            except ValueError:
                continue

            # Check for errors
            if "error" in data_json:
                print(f"[ERROR] {data_json['error']}")
                continue

            if "systemMessage" not in data_json:
                continue

            msg = data_json["systemMessage"]
            messages.append(msg)

            # Process different message types
            if "text" in msg:
                parts = msg["text"].get("parts", [])
                text = "".join(parts)
                if text:
                    print(f"[TEXT] {text[:300]}...")

            if "schema" in msg:
                schema = msg["schema"]
                if "query" in schema and schema["query"].get("question"):
                    print(f"[SCHEMA QUERY] {schema['query']['question']}")
                if "result" in schema:
                    datasources = schema["result"].get("datasources", [])
                    tables = [
                        ds.get("bigqueryTableReference", {}).get("tableId", "?")
                        for ds in datasources
                    ]
                    print(f"[SCHEMA RESULT] Tables: {tables}")

            if "data" in msg:
                data = msg["data"]
                if "query" in data and data["query"].get("question"):
                    print(f"[DATA QUERY] {data['query']['question']}")
                if "generatedSql" in data:
                    print(f"[SQL] {data['generatedSql'][:200]}...")
                if "result" in data:
                    rows = len(data["result"].get("data", []))
                    print(f"[DATA RESULT] {rows} rows returned")

            if "chart" in msg:
                chart_msg = msg["chart"]
                if "query" in chart_msg:
                    instructions = chart_msg["query"].get("instructions", "")
                    if instructions:
                        print(f"[CHART QUERY] {instructions}")

                if "result" in chart_msg:
                    result = chart_msg["result"]

                    # Check for Vega-Lite config
                    if "vegaConfig" in result:
                        print(f"[CHART RESULT] Vega-Lite config received!")
                        chart_found = True
                        render_vega_chart(result["vegaConfig"])

                    # Check for pre-rendered image
                    if "image" in result and result["image"].get("data"):
                        mime_type = result["image"].get("mimeType", "unknown")
                        print(f"[CHART IMAGE] Image blob received: {mime_type}")
                        # Decode base64 and save
                        import base64

                        image_data = base64.b64decode(result["image"]["data"])
                        image_path = "chart_server_rendered.png"
                        with open(image_path, "wb") as f:
                            f.write(image_data)
                        print(f"Server-rendered image saved to: {image_path}")

            if "error" in msg:
                print(f"[ERROR] {msg['error'].get('message', 'Unknown error')}")

            accumulator = ""

    if not chart_found:
        print(
            "\nNo chart was generated. The API may need a more explicit chart request."
        )
        print("Try prompts like: 'Create a bar chart of orders by status'")

    return messages


def main():
    """Run the chart generation test."""
    # Test prompts that should trigger chart generation
    test_prompts = [
        "Create a bar chart showing the number of orders by status",
        "Show me a bar graph of total orders per month",
        "Visualize the distribution of order statuses as a pie chart",
    ]

    print("=" * 60)
    print("CA API Chart Generation Test (REST)")
    print("=" * 60)

    # Try the first prompt
    prompt = test_prompts[0]
    messages = chat_with_chart_rest(prompt)

    print(f"\n=== Summary ===")
    print(f"Total messages received: {len(messages)}")


if __name__ == "__main__":
    main()
