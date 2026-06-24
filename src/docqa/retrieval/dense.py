from __future__ import annotations

from dataclasses import dataclass

from docqa.parsing.schema import DocumentChunk
from docqa.retrieval.bm25 import RetrievalResult


class DisabledDenseRetriever:
    provider_name = "disabled_dense"

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        _ = (query, top_k)
        return []


@dataclass(frozen=True)
class DenseConfig:
    embedding_model: str
    collection_name: str = "docqa_chunks"


class ChromaDenseRetriever:
    provider_name = "chroma_dense"

    def __init__(self, chunks: list[DocumentChunk], config: DenseConfig) -> None:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Dense retrieval requires chromadb and sentence-transformers. "
                "Install optional dense dependencies before enabling this provider."
            ) from exc

        self._chunks = chunks
        self._model = SentenceTransformer(config.embedding_model)
        self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(config.collection_name)
        self._index_chunks()

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not self._chunks:
            return []
        query_embedding = self._model.encode([query], normalize_embeddings=True)[0].tolist()
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, len(self._chunks)),
            include=["distances"],
        )
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        chunk_by_id = {chunk.chunk_id: chunk for chunk in self._chunks}
        hits: list[RetrievalResult] = []
        for chunk_id, distance in zip(ids, distances):
            chunk = chunk_by_id.get(chunk_id)
            if chunk is None:
                continue
            dense_score = max(0.0, 1.0 - float(distance))
            hits.append(
                RetrievalResult(
                    chunk=chunk,
                    score=dense_score,
                    source="dense",
                    dense_score=dense_score,
                )
            )
        return hits

    def _index_chunks(self) -> None:
        existing = set(self._collection.get(include=[])["ids"])
        chunks = [chunk for chunk in self._chunks if chunk.chunk_id not in existing]
        if not chunks:
            return
        embeddings = self._model.encode(
            [chunk.text for chunk in chunks],
            normalize_embeddings=True,
        ).tolist()
        self._collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "page": chunk.page,
                    "chunk_type": chunk.chunk_type,
                    "clause_id": chunk.clause_id or "",
                    "table_id": chunk.table_id or "",
                }
                for chunk in chunks
            ],
        )


class FaissDenseRetriever:
    provider_name = "faiss_dense"

    def __init__(self, chunks: list[DocumentChunk], config: DenseConfig) -> None:
        try:
            import faiss
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "FAISS dense retrieval requires faiss-cpu and numpy."
            ) from exc

        self._faiss = faiss
        self._np = np
        self._chunks = chunks
        self._model = _load_embedding_model(config.embedding_model)
        embeddings = self._model.encode(
            [chunk.text for chunk in chunks],
            normalize_embeddings=True,
        )
        self._embeddings = np.asarray(embeddings, dtype="float32")
        dimension = int(self._embeddings.shape[1]) if len(self._embeddings) else 0
        self._index = faiss.IndexFlatIP(dimension) if dimension else None
        if self._index is not None:
            self._index.add(self._embeddings)

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not self._chunks or self._index is None:
            return []

        query_embedding = self._model.encode([query], normalize_embeddings=True)
        query_vector = self._np.asarray(query_embedding, dtype="float32")
        scores, indexes = self._index.search(query_vector, min(top_k, len(self._chunks)))
        hits: list[RetrievalResult] = []
        for score, index in zip(scores[0], indexes[0]):
            if index < 0:
                continue
            chunk = self._chunks[int(index)]
            dense_score = max(0.0, float(score))
            hits.append(
                RetrievalResult(
                    chunk=chunk,
                    score=dense_score,
                    source="dense",
                    dense_score=dense_score,
                )
            )
        return hits


class InMemoryDenseRetriever:
    provider_name = "memory_dense"

    def __init__(self, chunks: list[DocumentChunk], config: DenseConfig) -> None:
        self._chunks = chunks
        self._model = _load_embedding_model(config.embedding_model)
        self._embeddings = self._model.encode(
            [chunk.text for chunk in chunks],
            normalize_embeddings=True,
        )

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not self._chunks:
            return []

        query_embedding = self._model.encode([query], normalize_embeddings=True)[0]
        scored = []
        for index, embedding in enumerate(self._embeddings):
            score = _dot(query_embedding, embedding)
            scored.append((score, self._chunks[index]))
        scored.sort(key=lambda item: item[0], reverse=True)

        return [
            RetrievalResult(
                chunk=chunk,
                score=max(0.0, float(score)),
                source="dense",
                dense_score=max(0.0, float(score)),
            )
            for score, chunk in scored[:top_k]
        ]


def _dot(left, right) -> float:
    try:
        return float(left @ right)
    except Exception:
        return sum(float(a) * float(b) for a, b in zip(left, right, strict=False))


def _load_embedding_model(model_path: str):
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_path)
    except Exception as sentence_transformers_error:
        try:
            return _TransformersEmbeddingModel(model_path)
        except Exception as transformers_error:
            raise RuntimeError(
                "Failed to load embedding model with sentence-transformers or transformers. "
                f"sentence-transformers error: {type(sentence_transformers_error).__name__}: "
                f"{sentence_transformers_error}; transformers error: "
                f"{type(transformers_error).__name__}: {transformers_error}"
            ) from transformers_error


class _TransformersEmbeddingModel:
    def __init__(self, model_path: str) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_path)
        self._model = AutoModel.from_pretrained(model_path)
        self._model.eval()

    def encode(self, texts: list[str], normalize_embeddings: bool = True):
        torch = self._torch
        with torch.no_grad():
            encoded = self._tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            output = self._model(**encoded)
            token_embeddings = output.last_hidden_state
            attention_mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
            embeddings = (token_embeddings * attention_mask).sum(dim=1) / attention_mask.sum(dim=1).clamp(min=1e-9)
            if normalize_embeddings:
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            return embeddings.cpu().numpy()
