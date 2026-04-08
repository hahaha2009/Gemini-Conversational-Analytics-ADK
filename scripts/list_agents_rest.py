import requests
import google.auth
import google.auth.transport.requests

# Project context
PROJECT_ID = "bqexplore-476017"

print(f"Retrieving access token for project {PROJECT_ID}...")

# 1. Get credentials
# Using standard google-auth library
creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
auth_req = google.auth.transport.requests.Request()
creds.refresh(auth_req)

token = creds.token
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "X-Goog-User-Project": PROJECT_ID
}

# 2. Check locations
locations = ["global", "us-central1"]

print("\n=== Listing Engines using Discovery Engine API ===")

for loc in locations:
    url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_ID}/locations/{loc}/collections/default_collection/engines"
    print(f"\nChecking location: {loc} ({url})")
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            engines = data.get("engines", [])
            for eng in engines:
                print(f"\n  Display Name: {eng.get('displayName')}")
                print(f"  Name (Resource Name): {eng.get('name')}")
                print(f"  Create Time: {eng.get('createTime')}")
        else:
            print(f"  Failed with status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")
