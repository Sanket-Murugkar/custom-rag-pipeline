"""
FastAPI app.

Endpoints:
  POST /ask        — answer a question from the docs
  POST /ingest     — trigger manual ingestion (optionally force re-ingest)
  GET  /health     — liveness check
"""

import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from retrieval.retriever import retrieve
from retrieval.llm       import generate

app = FastAPI(title="Confluence RAG API", version="1.0.0")

# Bug 7 fix: resolve the project root once at import time so the
# subprocess always runs ingest.py from the correct directory,
# regardless of where uvicorn was launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AskRequest(BaseModel):
    query: str


class AskResponse(BaseModel):
    answer:  str
    sources: list[str]


class IngestRequest(BaseModel):
    force: bool = False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    chunks = retrieve(req.query)
    result = generate(req.query, chunks)
    return AskResponse(**result)


@app.post("/ingest")
def ingest(req: IngestRequest = IngestRequest()):
    """
    Runs ingestion in a subprocess so the API stays responsive.
    cwd is set to PROJECT_ROOT so relative imports in ingest.py resolve correctly.
    """
    cmd = [sys.executable, "ingest.py"]
    if req.force:
        cmd.append("--force")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(PROJECT_ROOT),   # Bug 7 fix
        )
        return {
            "status": "done" if result.returncode == 0 else "error",
            "output": result.stdout[-3000:],
            "errors": result.stderr[-1000:] if result.stderr else None,
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": "Ingestion timed out after 10 minutes."}
