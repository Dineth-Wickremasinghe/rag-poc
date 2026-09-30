import uuid

import fitz
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from config import CHUNK_SIZE, EMBEDDING_MODEL, QDRANT_COLLECTION, QDRANT_URL

_model = None
_qdrant = None


def _clients():
    global _model, _qdrant

    if _qdrant is not None:
        return _model, _qdrant

    print("Loading embedding model...")
    _model = SentenceTransformer(EMBEDDING_MODEL)
    _qdrant = QdrantClient(url=QDRANT_URL)

    names = [
        collection.name
        for collection in _qdrant.get_collections().collections
    ]

    if QDRANT_COLLECTION not in names:
        _qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=_model.get_sentence_embedding_dimension(),
                distance=Distance.COSINE,
            ),
        )
        print("Collection created.")
    else:
        print("Collection already exists.")

    return _model, _qdrant


def extract_text(pdf_path):
    document = fitz.open(pdf_path)
    text = ""
    for page in document:
        text += page.get_text()
    document.close()
    return text


def chunk_text(text, chunk_size=CHUNK_SIZE):
    words = text.split()
    return [
        " ".join(words[i:i + chunk_size])
        for i in range(0, len(words), chunk_size)
    ]


def delete_document(file_id):
    _, qdrant = _clients()

    print(f"\nDeleting existing vectors for file: {file_id}")
    qdrant.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="file_id",
                    match=MatchValue(value=file_id),
                )
            ]
        ),
    )
    print("Existing vectors deleted.")


def ingest_document(pdf_path, file_id, file_name, agent, folder_id):
    model, qdrant = _clients()

    print(f"\nProcessing: {file_name}")
    text = extract_text(pdf_path)
    print(f"Extracted {len(text)} characters")

    chunks = chunk_text(text)
    print(f"Created {len(chunks)} chunks")

    embeddings = model.encode(chunks)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist(),
            payload={
                "file_id": file_id,
                "file_name": file_name,
                "agent": agent,
                "folder_id": folder_id,
                "text": chunk,
            },
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]

    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)
    print(f"Inserted {len(points)} vectors into Qdrant.")


if __name__ == "__main__":
    _clients()
    print("rag_ingest.py loaded successfully.")
