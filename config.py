import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def get(name, default=""):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def get_int(name, default):
    raw = get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f"{name} must be an integer.")
    if value <= 0:
        raise SystemExit(f"{name} must be greater than 0.")
    return value


def require(*names):
    missing = [name for name in names if not get(name)]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"Missing required setting(s): {joined}. "
            "Copy .env.example to .env and fill them in."
        )


CLIENT_ID = get("CLIENT_ID")
FOLDER_ID = get("FOLDER_ID")
AGENT = get("AGENT", "python-agent")
GRAPH_AUTHORITY = get(
    "GRAPH_AUTHORITY",
    "https://login.microsoftonline.com/consumers",
)
GRAPH_SCOPES = ["User.Read", "Files.Read"]
DELTA_STATE_FILE = get("DELTA_STATE_FILE", "delta_state.txt")
DOWNLOAD_DIR = get("DOWNLOAD_DIR", "downloads")
KAFKA_BOOTSTRAP_SERVERS = get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = get("KAFKA_TOPIC", "rag-file-events")
KAFKA_GROUP_ID = get("KAFKA_GROUP_ID", "rag-ingestion-consumer")
QDRANT_URL = get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = get("QDRANT_COLLECTION", "python-agent-kb")
EMBEDDING_MODEL = get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE = get_int("CHUNK_SIZE", 500)
