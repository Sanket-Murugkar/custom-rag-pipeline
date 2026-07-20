"""
Wraps sentence-transformers for batch encoding.
Model is loaded once and reused.
"""

from functools import lru_cache
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from config.settings import EMBED_MODEL


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    print(f"Loading embedding model: {EMBED_MODEL}")
    return SentenceTransformer(EMBED_MODEL)


def embed_texts(texts: List[str], batch_size: int = 64) -> np.ndarray:
    """Returns (N, dim) float32 array of embeddings."""
    model = _model()
    # BGE models benefit from a query prefix — use doc prefix for indexing
    prefixed = [f"passage: {t}" for t in texts]
    return model.encode(
        prefixed,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )


def embed_query(query: str) -> np.ndarray:
    """Single query embedding with query prefix."""
    model = _model()
    return model.encode(
        [f"query: {query}"],
        normalize_embeddings=True,
    )[0]
