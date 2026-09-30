# OneDrive → Kafka → RAG Knowledge Base Synchronization

A proof-of-concept for automatically synchronizing agent-specific OneDrive documents with a RAG knowledge base stored in Qdrant.

The system uses **Microsoft Graph Delta Query** to detect document changes, **Apache Kafka** to publish file-change events, and an existing **RAG ingestion pipeline** to update the corresponding Qdrant collection.

## Architecture

```text
┌──────────────┐
│   OneDrive   │
│              │
│ Agent Folder │
└──────┬───────┘
       │
       │ Microsoft Graph
       │ Delta Query
       ▼
┌────────────────────────┐
│ Graph Change Detector  │
│                        │
│ Detects:               │
│ ADD / UPDATE / DELETE  │
└──────────┬─────────────┘
           │
           │ JSON event
           ▼
┌────────────────────────┐
│       Apache Kafka     │
│                        │
│   rag-file-events      │
└──────────┬─────────────┘
           │
           │ File event
           ▼
┌────────────────────────┐
│   Kafka RAG Consumer   │
└──────────┬─────────────┘
           │
           ├── DELETE → Remove vectors
           │
           └── ADD/UPDATE
                    │
                    ▼
             Download document
                    │
                    ▼
              RAG Ingestion
                    │
                    ▼
             Generate embeddings
                    │
                    ▼
                 Qdrant
```

## Features

* Detects OneDrive file changes using Microsoft Graph Delta Query.
* Publishes file-change events to Apache Kafka.
* Supports:

  * File addition
  * File updates
  * File deletion
* Downloads changed documents automatically.
* Removes existing vectors before re-ingestion.
* Extracts text from PDF documents.
* Splits documents into chunks.
* Generates embeddings using `all-MiniLM-L6-v2`.
* Stores document chunks and metadata in Qdrant.
* Associates documents with a specific agent and OneDrive folder.
* Uses a delta checkpoint to avoid repeatedly processing old changes.

## Project Structure

```text
rag-poc/
│
├── config.py
│   └── Loads settings from .env.
│
├── graph_change_detector.py
│   └── Detects OneDrive changes and publishes Kafka events.
│
├── rag_kafka_consumer.py
│   └── Consumes Kafka events and triggers RAG processing.
│
├── graph_rag_pipeline.py
│   └── Optional path that ingests changes directly, without Kafka.
│
├── rag_ingest.py
│   └── Extracts, chunks, embeds and stores documents in Qdrant.
│
├── init_delta.py
│   └── Initializes the Microsoft Graph delta checkpoint.
│
├── docker-compose.yml
│   └── Starts local Kafka and Qdrant.
│
├── requirements.txt
│   └── Python dependencies.
│
├── .env.example
│   └── Template for local configuration. Copy this to .env.
│
├── delta_state.txt
│   └── Generated checkpoint. Do not commit.
│
└── downloads/
    └── Temporary directory for downloaded documents. Do not commit.
```

## Technologies

| Component           | Technology                  |
| ------------------- | --------------------------- |
| Cloud Storage       | Microsoft OneDrive          |
| Change Detection    | Microsoft Graph Delta Query |
| Message Broker      | Apache Kafka                |
| Document Processing | PyMuPDF                     |
| Embeddings          | Sentence Transformers       |
| Embedding Model     | `all-MiniLM-L6-v2`          |
| Vector Database     | Qdrant                      |
| Language            | Python                      |
| Containerization    | Docker                      |

## Prerequisites

Make sure the following are installed:

* Python 3.x
* Docker Desktop
* A Microsoft account with access to the OneDrive folder you want to sync
* A Microsoft Entra app registration (public client) with delegated `User.Read` and `Files.Read` permissions

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd rag-poc
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Environment Configuration

Copy the example file and fill in your own values:

```bash
copy .env.example .env
```

On Linux or macOS:

```bash
cp .env.example .env
```

`.env.example` lists every setting. Only two values are required:

| Variable | What to put |
| --- | --- |
| `CLIENT_ID` | Application (client) ID of your Entra app |
| `FOLDER_ID` | OneDrive item id of the folder to watch |

Everything else has a local default (Kafka on `localhost:9092`, Qdrant on `localhost:6333`, collection `python-agent-kb`, embedding model `all-MiniLM-L6-v2`). Change those in `.env` if your environment is different.

**Do not commit `.env`.** It is listed in `.gitignore`.

### Create the Entra app

1. Open [Microsoft Entra admin center](https://entra.microsoft.com/) → **App registrations** → **New registration**.
2. Choose **Accounts in any organizational directory and personal Microsoft accounts**.
3. Set the redirect URI platform to **Public client/native** and use `http://localhost`.
4. After the app is created, copy **Application (client) ID** into `CLIENT_ID`.
5. Under **Authentication**, set **Allow public client flows** to **Yes**.
6. Under **API permissions**, add delegated Microsoft Graph permissions `User.Read` and `Files.Read`.

For a personal Microsoft account, leave `GRAPH_AUTHORITY` as `https://login.microsoftonline.com/consumers`. For a work or school account, set it to `https://login.microsoftonline.com/<tenant-id>`.

### Find the OneDrive folder id

1. Sign in to [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer) with the account that owns the folder.
2. Run:

```http
GET https://graph.microsoft.com/v1.0/me/drive/root/children
```

3. Copy the `id` of the folder you want to sync into `FOLDER_ID`.

For a nested folder, list that folder's children with the parent id:

```http
GET https://graph.microsoft.com/v1.0/me/drive/items/{parent-id}/children
```

## Kafka and Qdrant

Start both services:

```bash
docker compose up -d
```

Verify the containers are running:

```bash
docker ps
```

Qdrant is available at `http://localhost:6333`. The dashboard is at `http://localhost:6333/dashboard`.

Create the Kafka topic (the name must match `KAFKA_TOPIC` in `.env`):

```bash
docker exec kafka-poc /opt/kafka/bin/kafka-topics.sh \
  --create \
  --topic rag-file-events \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

The ingestion code creates the Qdrant collection on first use. The default collection name is `python-agent-kb`. Vector size follows the embedding model (`all-MiniLM-L6-v2` is 384 dimensions, cosine distance).

## Microsoft Graph Delta Initialization

Before detecting changes, initialize the delta checkpoint:

```bash
python init_delta.py
```

This performs an initial synchronization query and stores the returned delta URL in:

```text
delta_state.txt
```

The checkpoint allows subsequent executions to request only changes that occurred after the previous synchronization point.

## Running the System

The components should be run in the following order.

### 1. Start Kafka and Qdrant

```bash
docker compose up -d
```

### 2. Start the Kafka/RAG consumer

```bash
python rag_kafka_consumer.py
```

The consumer should display:

```text
Waiting for RAG file events...
```

### 3. Run the Graph change detector

```bash
python graph_change_detector.py
```

The change detector checks Microsoft Graph for changes and publishes events to Kafka.

For example:

```text
File changed: howto-logging-cookbook.pdf
Published UPDATE event to Kafka.

New delta link saved.
```

### 4. Kafka consumer processes the event

The consumer receives the event and either:

* downloads and re-ingests the document for `added`/`updated` events, or
* removes the document's vectors for `deleted` events.

## Event Format

Kafka messages use JSON.

Example update event:

```json
{
  "agent": "python-agent",
  "folder_id": "your-folder-id",
  "file_id": "file-id",
  "file_name": "example.pdf",
  "change_type": "updated"
}
```

Example deletion event:

```json
{
  "agent": "python-agent",
  "folder_id": "your-folder-id",
  "file_id": "file-id",
  "file_name": null,
  "change_type": "deleted"
}
```

For deletion events, Microsoft Graph may not return the original filename. The `file_id` is therefore used to identify and remove the document's vectors.

## Qdrant Data

Each document is split into chunks and stored as vectors.

Example payload:

```json
{
  "file_id": "file-id",
  "file_name": "example.pdf",
  "agent": "python-agent",
  "folder_id": "folder-id",
  "text": "Document chunk..."
}
```

The default embedding configuration is:

```text
Model: all-MiniLM-L6-v2
Vector size: 384 (taken from the model)
Distance: COSINE
```

`EMBEDDING_MODEL` and `QDRANT_COLLECTION` in `.env` change this. Use a new collection name if you switch models, because an existing collection keeps its original vector size.

## Change Processing

### Add

```text
OneDrive
   ↓
Graph Delta
   ↓
Kafka
   ↓
Consumer
   ↓
Download PDF
   ↓
Extract text
   ↓
Chunk
   ↓
Generate embeddings
   ↓
Qdrant
```

### Update

Existing vectors belonging to the file are first removed.

The updated document is then downloaded and processed again.

```text
Updated file
     ↓
Graph Delta
     ↓
Kafka
     ↓
Delete old vectors
     ↓
Download updated document
     ↓
Re-ingest
     ↓
Qdrant
```

### Delete

```text
Deleted file
     ↓
Graph Delta
     ↓
Kafka
     ↓
Consumer
     ↓
Delete vectors using file_id
     ↓
Qdrant
```

## Current POC Limitations

This repository is a proof-of-concept and has several areas that can be improved for production deployment:

* Graph change detection is currently triggered manually rather than through Graph change notification webhooks.
* Kafka is running as a single local broker.
* Kafka topic has a single partition.
* Qdrant is running locally.
* Authentication currently uses interactive Microsoft authentication.
* PDF is currently the primary supported document format.
* Document chunking uses a simple word-based strategy.
* Embedding generation is performed locally.
* Error handling and retry mechanisms require further production hardening.
* Delta checkpoint storage currently uses a local file.
* Explicit distinction between newly added and updated files can be improved using persistent file metadata.

## Future Production Architecture

A production implementation could use:

```text
OneDrive
    │
    ▼
Microsoft Graph
    │
    │ Change Notification
    ▼
Event Detection Service
    │
    │ Delta Query
    ▼
Kafka
    │
    ▼
RAG Ingestion Service
    │
    ├── Document Processing
    ├── Embedding Generation
    └── Metadata Management
    │
    ▼
Qdrant
```

Graph change notifications can be used to notify the service that changes may have occurred, while Delta Query can then be used to retrieve the actual changes.

This separates **change notification** from **change reconciliation** and avoids placing document contents directly into Kafka messages.

## Testing

The POC has been tested for:

* File addition
* File modification
* File deletion
* Kafka event publishing
* Kafka event consumption
* PDF downloading
* Text extraction
* Document chunking
* Embedding generation
* Qdrant vector insertion
* Qdrant vector deletion
* Re-ingestion of modified documents

## Security Notes

Do not commit the following files or directories:

```text
.env
delta_state.txt
.venv/
__pycache__/
downloads/
*.pyc
```

`delta_state.txt` contains a Microsoft Graph delta token. `downloads/` contains copies of OneDrive files. Both are ignored by git.

Share `.env.example`, and let each person fill in their own `CLIENT_ID` and `FOLDER_ID`.

## Status

**Proof of Concept — End-to-End Pipeline Working**

The current implementation successfully demonstrates:

```text
OneDrive
   ↓
Microsoft Graph Delta Query
   ↓
Kafka
   ↓
RAG Consumer
   ↓
Qdrant
```

with working **ADD, UPDATE, and DELETE** document synchronization.
