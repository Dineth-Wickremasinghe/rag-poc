import os

import msal
import requests

from config import (
    AGENT,
    CLIENT_ID,
    DELTA_STATE_FILE,
    DOWNLOAD_DIR,
    FOLDER_ID,
    GRAPH_AUTHORITY,
    GRAPH_SCOPES,
    require,
)
from rag_ingest import delete_document, ingest_document

require("CLIENT_ID", "FOLDER_ID")

app = msal.PublicClientApplication(CLIENT_ID, authority=GRAPH_AUTHORITY)
result = app.acquire_token_interactive(scopes=GRAPH_SCOPES)

if "access_token" not in result:
    print("Authentication failed:")
    print(result)
    raise SystemExit(1)

headers = {"Authorization": f"Bearer {result['access_token']}"}


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

    print("\nName:", file_name)
    print("ID:", file_id)

    if "deleted" in item:
        print("Change: DELETED")
        delete_document(file_id)
        print("Qdrant vectors deleted.")

    elif "file" in item:
        print("Change: FILE ADDED/UPDATED")
        delete_document(file_id)

        file_path = download_file(file_id, file_name)
        if file_path:
            print("Sending file to RAG ingestion...")
            ingest_document(
                pdf_path=file_path,
                file_id=file_id,
                file_name=file_name,
                agent=AGENT,
                folder_id=FOLDER_ID,
            )
            print("RAG ingestion completed.")

    elif "folder" in item:
        print("Change: FOLDER")

if new_delta_url:
    with open(DELTA_STATE_FILE, "w", encoding="utf-8") as f:
        f.write(new_delta_url)
    print("\nNew delta link saved.")
else:
    print("\nWARNING: No new delta link returned.")
