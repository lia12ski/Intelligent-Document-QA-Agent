from __future__ import annotations

from collections import defaultdict
from typing import Protocol

from docqa.retrieval.bm25 import RetrievalResult


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        ...


class RrfHybridRetriever:
    def __init__(self, retrievers: list[Retriever], rrf_k: int = 60) -> None:
        self._retrievers = retrievers
        self._rrf_k = rrf_k

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        scores: dict[str, float] = defaultdict(float)
        best_result_by_chunk: dict[str, RetrievalResult] = {}

        for retriever in self._retrievers:
            for rank, result in enumerate(retriever.search(query, top_k=top_k), start=1):
                chunk_id = result.chunk.chunk_id
                scores[chunk_id] += 1.0 / (self._rrf_k + rank)
                if (
                    chunk_id not in best_result_by_chunk
                    or result.score > best_result_by_chunk[chunk_id].score
                ):
                    best_result_by_chunk[chunk_id] = result

        fused = [
            RetrievalResult(
                chunk=result.chunk,
                score=scores[chunk_id],
                source=f"rrf:{result.source}",
                dense_score=result.dense_score,
            )
            for chunk_id, result in best_result_by_chunk.items()
        ]
        fused.sort(key=lambda item: item.score, reverse=True)
        return fused[:top_k]
