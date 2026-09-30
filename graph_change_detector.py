import json

import msal
import requests
from kafka import KafkaProducer

from config import (
    AGENT,
    CLIENT_ID,
    DELTA_STATE_FILE,
    FOLDER_ID,
    GRAPH_AUTHORITY,
    GRAPH_SCOPES,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC,
    require,
)

require("CLIENT_ID", "FOLDER_ID")

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda value: json.dumps(value).encode("utf-8"),
)

app = msal.PublicClientApplication(CLIENT_ID, authority=GRAPH_AUTHORITY)
result = app.acquire_token_interactive(scopes=GRAPH_SCOPES)

if "access_token" not in result:
    print("Authentication failed:")
    print(result)
    raise SystemExit(1)

headers = {"Authorization": f"Bearer {result['access_token']}"}

try:
    with open(DELTA_STATE_FILE, "r", encoding="utf-8") as f:
        delta_url = f.read().strip()
except FileNotFoundError:
    print("No delta state found.")
    print("Run python init_delta.py first.")
    raise SystemExit(1)

if not delta_url:
    print("Delta state file is empty.")
    raise SystemExit(1)

url = delta_url
all_changes = []
new_delta_url = None

while url:
    print("\nCalling Graph delta query...")
    response = requests.get(url, headers=headers)
    print("Status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    data = response.json()
    all_changes.extend(data.get("value", []))

    next_url = data.get("@odata.nextLink")
    if next_url:
        url = next_url
    else:
        new_delta_url = data.get("@odata.deltaLink")
        url = None

print("\n==============================")
print("CHANGES DETECTED")
print("==============================")

if not all_changes:
    print("No changes detected.")

for item in all_changes:
    file_id = item.get("id")
    file_name = item.get("name")

    if "deleted" in item:
        print("\nDeleted:", file_id)
        producer.send(
            KAFKA_TOPIC,
            {
                "agent": AGENT,
                "folder_id": FOLDER_ID,
                "file_id": file_id,
                "file_name": file_name,
                "change_type": "deleted",
            },
        )
        print("Published DELETE event to Kafka.")

    elif "file" in item:
        print("\nFile changed:", file_name)
        producer.send(
            KAFKA_TOPIC,
            {
                "agent": AGENT,
                "folder_id": FOLDER_ID,
                "file_id": file_id,
                "file_name": file_name,
                "change_type": "updated",
            },
        )
        print("Published UPDATE event to Kafka.")

    elif "folder" in item:
        print("\nFolder change ignored:", file_name)

producer.flush()

if new_delta_url:
    with open(DELTA_STATE_FILE, "w", encoding="utf-8") as f:
        f.write(new_delta_url)
    print("\nNew delta link saved.")
else:
    print("\nWARNING: No new delta link returned.")
