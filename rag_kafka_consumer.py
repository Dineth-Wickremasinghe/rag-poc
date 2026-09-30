import json
import os

import msal
import requests
from kafka import KafkaConsumer

from config import (
    CLIENT_ID,
    DOWNLOAD_DIR,
    GRAPH_AUTHORITY,
    GRAPH_SCOPES,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_GROUP_ID,
    KAFKA_TOPIC,
    require,
)
from rag_ingest import delete_document, ingest_document

require("CLIENT_ID")

app = msal.PublicClientApplication(CLIENT_ID, authority=GRAPH_AUTHORITY)
result = app.acquire_token_interactive(scopes=GRAPH_SCOPES)

if "access_token" not in result:
    print("Authentication failed:")
    print(result)
    raise SystemExit(1)

headers = {"Authorization": f"Bearer {result['access_token']}"}

consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    auto_offset_reset="earliest",
    group_id=KAFKA_GROUP_ID,
    value_deserializer=lambda value: json.loads(value.decode("utf-8")),
)


def download_file(file_id, file_name):
    print(f"\nDownloading: {file_name}")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    response = requests.get(
        f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content",
        headers=headers,
        allow_redirects=True,
    )

    if response.status_code == 200:
        with open(file_path, "wb") as f:
            f.write(response.content)
        print(f"Downloaded successfully: {file_name}")
        return file_path

    print(f"Download failed: {response.status_code}")
    print(response.text)
    return None


print("Waiting for RAG file events...")

for message in consumer:
    event = message.value
    agent = event["agent"]
    folder_id = event["folder_id"]
    file_id = event["file_id"]
    file_name = event["file_name"]
    change_type = event["change_type"]

    print("\n==============================")
    print("FILE EVENT RECEIVED")
    print("==============================")
    print("Agent:", agent)
    print("File:", file_name)
    print("File ID:", file_id)
    print("Change:", change_type)

    if change_type == "deleted":
        print("\nDeleting vectors...")
        delete_document(file_id)
        print("Document removed from Qdrant.")

    elif change_type in ["added", "updated"]:
        print("\nRemoving existing vectors...")
        delete_document(file_id)

        file_path = download_file(file_id, file_name)
        if file_path:
            print("\nSending document to RAG ingestion...")
            ingest_document(
                pdf_path=file_path,
                file_id=file_id,
                file_name=file_name,
                agent=agent,
                folder_id=folder_id,
            )
            print("\nRAG ingestion completed successfully.")
        else:
            print("\nRAG ingestion skipped because file download failed.")
