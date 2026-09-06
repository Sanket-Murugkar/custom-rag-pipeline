# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A self-hosted RAG (retrieval-augmented generation) pipeline over PDF and Markdown documents. Everything runs locally/self-hosted — no AWS Bedrock or other managed AI services. The same code path is used for local dev (MinIO) and production (real AWS S3); only env vars differ.

Stack: MinIO/S3 (storage) → pypdf/markdown-it-py (parsing) → custom word-based chunker → sentence-transformers `BAAI/bge-base-en-v1.5` (embeddings) → Qdrant (vector store) → cross-encoder `ms-marco-MiniLM-L-6-v2` (reranking) → Ollama `llama3` (generation) → FastAPI (REST API).

## Commands

```bash
# One-time environment setup
python -m venv .venv
.venv\Scripts\activate            # Windows (this repo is developed on Windows)
pip install -r requirements.txt
cp .env.example .env

# Start infra (MinIO + Qdrant + Ollama)
docker compose up -d
docker exec ollama ollama pull llama3    # once, ~4GB

# Ingestion
python ingest.py                  # incremental — only new/changed files
python ingest.py --force          # re-ingest everything (required after changing
                                   # CHUNK_SIZE, CHUNK_OVERLAP, or EMBED_MODEL)

# Run the API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Query it
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"query": "..."}'

# MinIO bucket management (dev convenience)
python scripts/minio_helper.py list
python scripts/minio_helper.py upload <path>
python scripts/minio_helper.py upload-dir <dir>
python scripts/minio_helper.py delete <key>
python scripts/minio_helper.py url <key>
```

There are no tests, linter, or type-checker configured in this repo currently — don't assume `pytest`/`ruff`/`mypy` exist unless you add them.

## Architecture

The pipeline is split into two independent flows sharing `config/settings.py` (all config loaded from env vars via `.env`):

**Ingestion flow** (`ingest.py` orchestrates, or triggered via `POST /ingest`):
`ingestion/s3_loader.py` (list+download+parse from S3/MinIO, tracks per-file ETags in `.ingestion_state.json` to skip unchanged files) → `ingestion/chunker.py` (word-boundary splitting, `CHUNK_SIZE`/`CHUNK_OVERLAP`) → `ingestion/embedder.py` (sentence-transformers, `passage:` prefix for BGE) → `ingestion/vector_store.py` (`delete_by_source` then `upsert_chunks` into Qdrant — old chunks for a file are purged before re-inserting so stale data never lingers).

**Retrieval flow** (`retrieval/retriever.py`, called from `api/main.py`):
embed query (`ingestion/embedder.embed_query`, `query:` prefix) → vector search in Qdrant (`TOP_K_RETRIEVE=10`, broad recall) → cross-encoder rerank (`retrieval/retriever.py`, `TOP_K_RERANK=3`, precision) → `retrieval/llm.py` builds a context-stuffed prompt and calls Ollama, returning `{answer, sources}`.

**API** (`api/main.py`): thin FastAPI layer — `/ask` wires retrieval→llm, `/ingest` shells out to `ingest.py` as a subprocess (so the API stays responsive during a long ingestion run; `cwd` is pinned to the project root so it works regardless of where uvicorn was launched from), `/health` is a liveness check.

### Key conventions / gotchas

- **MinIO vs AWS S3 is a config-only switch.** `S3_ENDPOINT_URL` set → MinIO-compatible client (path-style addressing forced, since virtual-hosted-style breaks with `localhost`). Empty → real AWS S3. Never branch code on which storage backend is active — `ingestion/s3_loader.py` and `scripts/minio_helper.py` both use the same `_client()`/`_s3_client()` pattern for this.
- **BGE embedding prefixes matter.** Indexing uses `passage: {text}`, querying uses `query: {text}` (`ingestion/embedder.py`). Don't drop these — they're required by the `bge-base-en-v1.5` model for good retrieval quality.
- **Qdrant client version compatibility**: `ingestion/vector_store.py:search()` branches on `hasattr(client, "query_points")` to support both qdrant-client <1.10 (`.search()`) and >=1.10 (`.query_points()`). Keep this shim if touching that function.
- **Ollama response is an object, not a dict**: `response.message.content`, not `response["message"]["content"]` (`retrieval/llm.py`).
- **Qdrant delete requires `FilterSelector` wrapping `Filter`** as `points_selector` — a raw `Filter` fails (`ingestion/vector_store.py:delete_by_source`).
- Models (`SentenceTransformer`, `CrossEncoder`) are loaded once via `@lru_cache(maxsize=1)` module-level singletons — don't re-instantiate per-request.
- Re-run `python ingest.py --force` after changing `CHUNK_SIZE`, `CHUNK_OVERLAP`, or `EMBED_MODEL` since old chunks/embeddings become inconsistent with new settings otherwise.

### Files worth reading before making changes

- `README.md` — full setup/usage walkthrough, service URLs, API examples.
- `config/settings.py` — the single source of truth for all tunables (chunk size, top-K values, model names, hosts).
- `docs/` — contains an interactive HTML walkthrough of this pipeline (published via GitHub Pages) plus concept-explainer docs; these are presentation material, not application code.
