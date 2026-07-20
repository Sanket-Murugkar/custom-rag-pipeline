"""
Manual ingestion script.

Usage:
    python ingest.py               # process only new/changed files
    python ingest.py --force       # re-ingest everything
"""

import argparse

from ingestion.s3_loader    import load_documents
from ingestion.chunker      import chunk_document
from ingestion.embedder     import embed_texts
from ingestion.vector_store import ensure_collection, delete_by_source, upsert_chunks


def run(force: bool = False):
    ensure_collection()

    docs_processed = 0
    chunks_total   = 0

    for doc in load_documents(force=force):
        source = doc["source"]
        print(f"\nProcessing: {source}")

        # Remove stale chunks for this file before re-inserting
        delete_by_source(source)

        chunks = chunk_document(doc)
        if not chunks:
            print(f"  No chunks extracted — skipping")
            continue

        texts      = [c["text"] for c in chunks]
        embeddings = embed_texts(texts)
        upsert_chunks(chunks, embeddings)

        print(f"  Stored {len(chunks)} chunks")
        docs_processed += 1
        chunks_total   += len(chunks)

    print(f"\nDone. {docs_processed} document(s) ingested, {chunks_total} total chunks stored.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-ingest all files")
    args = parser.parse_args()
    run(force=args.force)
