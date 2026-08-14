"""Local embedding model wrapper (Ollama)."""

from __future__ import annotations

from functools import lru_cache

import config


@lru_cache(maxsize=1)
def get_embedder():
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=config.EMBED_MODEL, base_url=config.OLLAMA_BASE_URL)


@lru_cache(maxsize=1)
def embedding_dimensions() -> int:
    """Probe the embedding model once to learn its output dimensionality.

    Needed up front because ArcadeDB's LSM_VECTOR index is created with a
    fixed `dimensions` value.
    """
    vector = get_embedder().embed_query("dimension probe")
    return len(vector)


def embed_text(text: str) -> list[float]:
    return get_embedder().embed_query(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return get_embedder().embed_documents(texts)
