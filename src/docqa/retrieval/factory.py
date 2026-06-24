from __future__ import annotations

import sys

from docqa.config import Settings
from docqa.parsing.schema import DocumentChunk
from docqa.retrieval.bm25 import Bm25Retriever
from docqa.retrieval.dense import (
    ChromaDenseRetriever,
    DenseConfig,
    DisabledDenseRetriever,
    FaissDenseRetriever,
    InMemoryDenseRetriever,
)
from docqa.retrieval.hybrid import RrfHybridRetriever


def build_retriever(chunks: list[DocumentChunk], settings: Settings) -> RrfHybridRetriever:
    sparse = Bm25Retriever(chunks)
    dense = _build_dense_retriever(chunks, settings)
    return RrfHybridRetriever([sparse, dense])


def _build_dense_retriever(chunks: list[DocumentChunk], settings: Settings):
    if not settings.dense_retrieval_enabled:
        return DisabledDenseRetriever()

    try:
        config = DenseConfig(embedding_model=settings.embedding_model)
        if settings.dense_backend == "faiss":
            return FaissDenseRetriever(chunks, config)
        if settings.dense_backend == "memory":
            return InMemoryDenseRetriever(chunks, config)
        if settings.dense_backend == "chroma":
            return ChromaDenseRetriever(chunks, config)
        raise ValueError(f"Unsupported DENSE_BACKEND: {settings.dense_backend}")
    except Exception as exc:
        if not settings.dense_fail_open:
            raise
        print(
            "Warning: dense retrieval disabled after initialization failure: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return DisabledDenseRetriever()
