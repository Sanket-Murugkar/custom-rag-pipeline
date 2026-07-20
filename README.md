# Confluence RAG Pipeline

Self-hosted RAG over PDF and Markdown documents.  
No AWS Bedrock, no managed services — runs entirely on your own infrastructure.

**🔬 [See how it works, step by step](https://sanket-murugkar.github.io/custom-rag-pipeline/)** — an interactive walkthrough of the ingestion and query pipelines, using the real config values and models from this repo.

## Stack

| Layer | Tool | Notes |
|---|---|---|
| Document source (local) | **MinIO** | S3-compatible, runs in Docker |
| Document source (production) | Amazon S3 | Same code, just change env vars |
| PDF parsing | pypdf | |
| Markdown parsing | markdown-it-py | |
| Chunking | Custom word splitter | 500 words, 50 overlap |
| Embeddings | BAAI/bge-base-en-v1.5 | sentence-transformers, local |
| Vector store | Qdrant | Docker, self-hosted |
| Reranking | ms-marco-MiniLM-L-6-v2 | cross-encoder, local |
| LLM | Llama 3 via Ollama | local, no GPU required |
| API | FastAPI | REST |

---

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Python 3.10+
- ~6 GB free disk space (Ollama model + embedding/reranking models)

---

## Quick Start (local — MinIO + all services)

### 1. Start all services

```bash
docker compose up -d
```

This starts:
- **MinIO** on port 9000 (S3 API) and 9001 (web console)
- **minio-init** — creates the `rag-docs` bucket and uploads files from `./sample-docs/`
- **Qdrant** on port 6333
- **Ollama** on port 11434

### 2. Pull the LLM model (once, ~4 GB)

```bash
docker exec ollama ollama pull llama3
```

### 3. Python environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure

```bash
cp .env.example .env
# Defaults in .env.example already point to MinIO — no changes needed for local dev.
```

### 5. Add documents

Drop `.pdf` or `.md` files into `./sample-docs/`.  
The **user-master-service-docs.md** file is already there as a test document.

To upload more files to MinIO at any time:

```bash
# Upload a single file
python scripts/minio_helper.py upload ./my-doc.pdf

# Upload an entire directory
python scripts/minio_helper.py upload-dir ./my-docs/

# Or use the MinIO web console
open http://localhost:9001
# login: minioadmin / minioadmin
```

### 6. Run ingestion

```bash
# Only new or changed files (incremental)
python ingest.py

# Force re-ingest everything
python ingest.py --force
```

### 7. Start the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 8. Ask a question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the password requirements when creating a user?"}'
```

---

## MinIO vs AWS S3

The codebase is identical for both. The only difference is environment variables.

### Local (MinIO) — .env

```env
S3_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET=rag-docs
```

### Production (AWS S3) — .env

```env
S3_ENDPOINT_URL=          # leave blank
AWS_ACCESS_KEY_ID=        # your IAM key (or use an EC2 instance role)
AWS_SECRET_ACCESS_KEY=    # your IAM secret
S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
```

No code changes needed — just swap the env file.

---

## MinIO Helper Script

```bash
python scripts/minio_helper.py list                        # list all files in bucket
python scripts/minio_helper.py upload path/to/file.pdf    # upload a file
python scripts/minio_helper.py upload-dir ./my-docs/      # upload a whole directory
python scripts/minio_helper.py delete old-doc.pdf         # delete a file
python scripts/minio_helper.py url doc.pdf                # get a pre-signed download URL
python scripts/minio_helper.py buckets                    # list all buckets
python scripts/minio_helper.py console                    # print web console URL + creds
```

---

## API Endpoints

### Ask a question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I create a user?"}'

# Response
{
  "answer": "To create a user, send a POST request to /users with ...",
  "sources": ["user-master-service-docs.md"]
}
```

### Trigger ingestion via API

```bash
# Incremental
curl -X POST http://localhost:8000/ingest

# Full re-ingest
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

### Health check

```bash
curl http://localhost:8000/health
```

---

## Project Structure

```
rag-pipeline/
├── config/
│   └── settings.py              # all config from env vars
├── ingestion/
│   ├── s3_loader.py             # fetch + parse PDF/MD from S3 or MinIO
│   ├── chunker.py               # word-boundary chunking
│   ├── embedder.py              # sentence-transformers wrapper
│   └── vector_store.py          # Qdrant client wrapper
├── retrieval/
│   ├── retriever.py             # vector search + cross-encoder rerank
│   └── llm.py                   # Ollama chat wrapper
├── api/
│   └── main.py                  # FastAPI app
├── scripts/
│   ├── minio-init.sh            # runs inside Docker on first boot
│   └── minio_helper.py          # dev CLI for bucket management
├── sample-docs/                 # files here auto-upload to MinIO on `docker compose up`
│   └── user-master-service-docs.md
├── ingest.py                    # manual ingestion entry point
├── docker-compose.yml           # MinIO + Qdrant + Ollama
├── requirements.txt
└── .env.example
```

---

## Service URLs (local)

| Service | URL | Credentials |
|---|---|---|
| MinIO S3 API | http://localhost:9000 | minioadmin / minioadmin |
| MinIO Web Console | http://localhost:9001 | minioadmin / minioadmin |
| Qdrant Dashboard | http://localhost:6333/dashboard | — |
| Ollama API | http://localhost:11434 | — |
| RAG API | http://localhost:8000 | — |
| API Docs (Swagger) | http://localhost:8000/docs | — |

---

## When to re-run ingestion

Run `python ingest.py` whenever:
- New PDFs or Markdown files are added to MinIO / S3
- Existing files are updated
- You change `CHUNK_SIZE` or `CHUNK_OVERLAP` (use `--force`)
- You change the embedding model (use `--force`)

Ingestion is incremental — it tracks each file's ETag in `.ingestion_state.json` and skips unchanged files.

---

## License

[MIT](LICENSE)
