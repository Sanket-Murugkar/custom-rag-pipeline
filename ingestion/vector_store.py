"""
Qdrant wrapper — handles collection setup, upsert, and search.
"""

import uuid
from typing import List
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, FilterSelector,
)

from config.settings import (
    QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME, EMBED_DIM
)


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection():
    client   = _client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
        print(f"Created collection: {COLLECTION_NAME}")
    else:
        print(f"Collection exists: {COLLECTION_NAME}")


def delete_by_source(source: str):
    """Remove all chunks that belong to a given S3 key (for re-ingestion).

    Bug 3 fix: client.delete() requires a FilterSelector wrapping the Filter,
    not a raw Filter object directly as points_selector.
    """
    client = _client()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=source))]
            )
        ),
    )


def upsert_chunks(chunks: List[dict], embeddings):
    """
    chunks:     list of {text, source, chunk_index}
    embeddings: np.ndarray of shape (len(chunks), EMBED_DIM)
    """
    client = _client()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embeddings[i].tolist(),
            payload={
                "text":        chunk["text"],
                "source":      chunk["source"],
                "chunk_index": chunk["chunk_index"],
            },
        )
        for i, chunk in enumerate(chunks)
    ]
    # Upsert in batches of 100 to avoid payload-size limits
    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points[i : i + batch_size],
        )


def search(query_vector, top_k: int = 10) -> List[dict]:
    """
    Compatible with both qdrant-client <1.10 (client.search)
    and >=1.10 (client.query_points, which replaced client.search).
    """
    client = _client()

    # qdrant-client >= 1.10 removed .search() in favour of .query_points()
    if hasattr(client, "query_points"):
        from qdrant_client.models import Query
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector.tolist(),
            limit=top_k,
            with_payload=True,
        )
        results = response.points
    else:
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector.tolist(),
            limit=top_k,
            with_payload=True,
        )

    return [
        {
            "text":   r.payload["text"],
            "source": r.payload["source"],
            "score":  r.score,
        }
        for r in results
    ]