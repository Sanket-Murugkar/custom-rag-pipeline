"""
Calls Ollama with the retrieved context and returns the answer.
"""

from ollama import Client
from config.settings import OLLAMA_MODEL, OLLAMA_HOST

SYSTEM_PROMPT = """You are a helpful assistant that answers questions using the provided context.
Rules:
- Answer only from the context. Do not use outside knowledge.
- If the context does not contain the answer, say "I couldn't find this in the documentation."
- Be concise and clear.
- Cite the source filename when you use information from it."""


def generate(query: str, chunks: list) -> dict:
    """
    chunks: list of {text, source, rerank_score}
    Returns: {answer, sources}

    Bug 1 fix: ollama>=0.2.0 returns a ChatResponse object, not a dict.
    Access fields as attributes: response.message.content
    (not response["message"]["content"] which raises TypeError).
    """
    if not chunks:
        return {
            "answer":  "No relevant documents found for your query.",
            "sources": [],
        }

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"[{i}] Source: {chunk['source']}\n{chunk['text']}")
    context = "\n\n---\n\n".join(context_parts)

    client   = Client(host=OLLAMA_HOST)
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
    )

    # response is a ChatResponse object — use attribute access
    answer = response.message.content

    return {
        "answer":  answer,
        "sources": sorted({c["source"] for c in chunks}),
    }
