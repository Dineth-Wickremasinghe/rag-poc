import msal
import requests

from config import (
    CLIENT_ID,
    DELTA_STATE_FILE,
    FOLDER_ID,
    GRAPH_AUTHORITY,
    GRAPH_SCOPES,
    require,
)

require("CLIENT_ID", "FOLDER_ID")

app = msal.PublicClientApplication(CLIENT_ID, authority=GRAPH_AUTHORITY)
result = app.acquire_token_interactive(scopes=GRAPH_SCOPES)

if "access_token" not in result:
    print("Authentication failed:")
    print(result)
    raise SystemExit(1)

headers = {"Authorization": f"Bearer {result['access_token']}"}
url = f"https://graph.microsoft.com/v1.0/me/drive/items/{FOLDER_ID}/delta"
delta_url = None

while url:
    print("\nCalling Graph delta query...")
    response = requests.get(url, headers=headers)
    print("Status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    data = response.json()
    for item in data.get("value", []):
        print("Found:", item.get("name"), "| ID:", item.get("id"))

    next_url = data.get("@odata.nextLink")
    if next_url:
        url = next_url
    else:
        delta_url = data.get("@odata.deltaLink")
        url = None

if delta_url:
    with open(DELTA_STATE_FILE, "w", encoding="utf-8") as f:
        f.write(delta_url)

    print("\n================================")
    print("INITIAL DELTA COMPLETE")
    print("================================")
    print("\nDelta checkpoint saved.")
else:
    print("\nERROR: No delta link returned.")
    raise SystemExit(1)
