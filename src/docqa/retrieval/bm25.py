from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math

from docqa.parsing.schema import DocumentChunk
from docqa.retrieval.tokenizer import tokenize


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    score: float
    source: str = "bm25"
    dense_score: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "score": round(self.score, 4),
            "source": self.source,
            "dense_score": self.dense_score,
            "chunk": self.chunk.to_dict(),
        }


class Bm25Retriever:
    def __init__(self, chunks: list[DocumentChunk], k1: float = 1.5, b: float = 0.75) -> None:
        self._chunks = chunks
        self._k1 = k1
        self._b = b
        self._documents = [tokenize(chunk.text) for chunk in chunks]
        self._doc_lengths = [len(document) for document in self._documents]
        self._avg_doc_length = (
            sum(self._doc_lengths) / len(self._doc_lengths) if self._doc_lengths else 0.0
        )
        self._term_frequencies = [Counter(document) for document in self._documents]
        self._doc_frequencies = Counter(
            token for document in self._documents for token in set(document)
        )

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        query_tokens = tokenize(query)
        if not query_tokens or not self._chunks:
            return []

        scored: list[RetrievalResult] = []
        for index, chunk in enumerate(self._chunks):
            score = self._score(query_tokens, index)
            if score > 0:
                scored.append(RetrievalResult(chunk=chunk, score=score, source="bm25"))

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _score(self, query_tokens: list[str], doc_index: int) -> float:
        score = 0.0
        doc_length = self._doc_lengths[doc_index]
        term_frequency = self._term_frequencies[doc_index]
        total_docs = len(self._documents)

        if self._avg_doc_length == 0:
            return 0.0

        for token in query_tokens:
            frequency = term_frequency.get(token, 0)
            if frequency == 0:
                continue
            document_frequency = self._doc_frequencies.get(token, 0)
            idf = math.log(1 + (total_docs - document_frequency + 0.5) / (document_frequency + 0.5))
            denominator = frequency + self._k1 * (
                1 - self._b + self._b * doc_length / self._avg_doc_length
            )
            score += idf * (frequency * (self._k1 + 1)) / denominator

        return score
