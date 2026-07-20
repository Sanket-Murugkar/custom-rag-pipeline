from dotenv import load_dotenv
import os

load_dotenv()

# ── S3 / MinIO ────────────────────────────────────────────────────────────
# Set S3_ENDPOINT_URL to point at MinIO for local dev:
#   S3_ENDPOINT_URL=http://localhost:9000
# Leave blank (or unset) when using real AWS S3 in production.
AWS_REGION        = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET         = os.getenv("S3_BUCKET", "rag-docs")
AWS_ACCESS_KEY    = os.getenv("AWS_ACCESS_KEY_ID",     "minioadmin")
AWS_SECRET_KEY    = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
S3_ENDPOINT_URL   = os.getenv("S3_ENDPOINT_URL", "")    # e.g. http://localhost:9000

# Qdrant
QDRANT_HOST       = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT       = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME   = os.getenv("COLLECTION_NAME", "confluence_docs")

# Embeddings
EMBED_MODEL       = os.getenv("EMBED_MODEL", "BAAI/bge-base-en-v1.5")
EMBED_DIM         = 768          # matches bge-base-en-v1.5

# Chunking
CHUNK_SIZE        = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP     = int(os.getenv("CHUNK_OVERLAP", 50))

# Ollama / LLM
OLLAMA_HOST       = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "llama3")

# Retrieval
TOP_K_RETRIEVE    = 10   # fetch this many from vector DB
TOP_K_RERANK      = 3    # keep this many after reranking
RERANK_MODEL      = "cross-encoder/ms-marco-MiniLM-L-6-v2"
