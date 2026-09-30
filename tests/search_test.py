import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL, QDRANT_COLLECTION, QDRANT_URL

print("Loading embedding model...")
model = SentenceTransformer(EMBEDDING_MODEL)
qdrant = QdrantClient(url=QDRANT_URL)

query = "How do I work with IP addresses in Python?"
print("\nQuery:", query)

query_vector = model.encode(query).tolist()
results = qdrant.query_points(
    collection_name=QDRANT_COLLECTION,
    query=query_vector,
    limit=3,
).points

print("\n========== RESULTS ==========")

for result in results:
    print("\nScore:", result.score)
    print("File:", result.payload["file_name"])
    print("Text:")
    print(result.payload["text"])
