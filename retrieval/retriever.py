"""
Retrieves top-K chunks from Qdrant then reranks with a cross-encoder.
"""

from functools import lru_cache
from typing import List

from sentence_transformers import CrossEncoder

from ingestion.embedder     import embed_query
from ingestion.vector_store import search
from config.settings        import TOP_K_RETRIEVE, TOP_K_RERANK, RERANK_MODEL


@lru_cache(maxsize=1)
def _reranker() -> CrossEncoder:
    print(f"Loading reranker: {RERANK_MODEL}")
    return CrossEncoder(RERANK_MODEL)


def retrieve(query: str) -> List[dict]:
    """
    Returns top TOP_K_RERANK chunks most relevant to the query.
    Each chunk: {text, source, score}
    """
    # 1. Embed query
    q_vec = embed_query(query)

    # 2. Vector search — broad recall
    candidates = search(q_vec, top_k=TOP_K_RETRIEVE)

    if not candidates:
        return []

    # 3. Rerank for precision
    reranker = _reranker()
    pairs    = [(query, c["text"]) for c in candidates]
    scores   = reranker.predict(pairs)

    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    return [
        {**chunk, "rerank_score": float(score)}
        for chunk, score in ranked[:TOP_K_RERANK]
    ]
