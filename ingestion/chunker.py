"""
Splits raw document text into overlapping chunks.
Uses word-boundary splitting so chunks don't cut mid-word.
"""

from typing import List
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP


def _word_chunks(text: str, size: int, overlap: int) -> List[str]:
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        end   = min(start + size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += size - overlap
    return chunks


def chunk_document(doc: dict) -> List[dict]:
    """
    Takes a doc dict {key, text, source, etag} and returns a list of
    chunk dicts {text, source, chunk_index}.
    """
    chunks = _word_chunks(doc["text"], CHUNK_SIZE, CHUNK_OVERLAP)
    return [
        {
            "text":        chunk,
            "source":      doc["source"],
            "chunk_index": i,
        }
        for i, chunk in enumerate(chunks)
        if chunk.strip()
    ]
