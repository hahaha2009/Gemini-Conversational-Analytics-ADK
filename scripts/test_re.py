import subprocess
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
if LOCATION == 'global': LOCATION = 'us-central1'
RE_ID = os.environ.get("REASONING_ENGINE_ID")
AUTH_ID = os.environ.get("AUTH_RESOURCE_ID")

token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()

base_url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{RE_ID}"
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print(f"URL: {base_url}")

# Start session
sess_payload = {
    "userId": "test-ai",
    "sessionState": {
        AUTH_ID: token
    }
}
sess_res = requests.post(f"{base_url}/sessions", headers=headers, json=sess_payload)
sess_info = sess_res.json()
print("Session Output:", sess_info)

sess_name = sess_info.get("name", "")
session_id = sess_name.split("/sessions/")[-1].split("/")[0] if "/sessions/" in sess_name else "test-session"

print(f"Session ID: {session_id}")

query_payload = {
    "input": {
        "user_id": "test-ai",
        "session_id": session_id,
        "new_message": {"role": "user", "parts": [{"text": "ada berapa jumlah customer kita?"}]}
    }
}

q_res = requests.post(f"{base_url}:streamQuery", headers=headers, json=query_payload)
print("Query Response Code:", q_res.status_code)
print("Query Output Dump:", q_res.text[:1000])
