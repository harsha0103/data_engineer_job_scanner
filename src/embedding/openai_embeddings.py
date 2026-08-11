"""Turns job description text into vectors for embedd.jobs.description_embedding.

Model is pinned to text-embedding-3-small at 1536 dimensions to match the
column definition in sql/schema.sql (vector(1536)) — changing either one
without the other breaks every insert.
"""

from langchain_openai import OpenAIEmbeddings

_MODEL = "text-embedding-3-small"
_DIMENSIONS = 1536

_embeddings = OpenAIEmbeddings(model=_MODEL, dimensions=_DIMENSIONS)


def embed_text(text: str) -> list[float]:
    return _embeddings.embed_query(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batched form — one API call for many texts instead of one call each."""
    return _embeddings.embed_documents(texts)
