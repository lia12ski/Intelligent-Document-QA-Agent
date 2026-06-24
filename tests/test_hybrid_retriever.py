from docqa.parsing.schema import DocumentChunk
from docqa.retrieval.bm25 import Bm25Retriever, RetrievalResult
from docqa.retrieval.hybrid import RrfHybridRetriever


class StaticRetriever:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        _ = query
        return self._results[:top_k]


def test_rrf_merges_duplicate_chunks() -> None:
    chunk = DocumentChunk(
        chunk_id="page_1_table_1",
        text="被投资单位名称",
        page=1,
        chunk_type="table",
        source_file="sample.pdf",
    )
    retriever = RrfHybridRetriever(
        [
            StaticRetriever([RetrievalResult(chunk=chunk, score=10.0, source="bm25")]),
            StaticRetriever([RetrievalResult(chunk=chunk, score=0.8, source="dense", dense_score=0.8)]),
        ]
    )

    results = retriever.search("被投资单位名称")

    assert len(results) == 1
    assert results[0].chunk.chunk_id == "page_1_table_1"
    assert results[0].source.startswith("rrf:")


def test_hybrid_can_wrap_bm25() -> None:
    chunk = DocumentChunk(
        chunk_id="page_1",
        text="金融负债 到期日",
        page=1,
        chunk_type="paragraph",
        source_file="sample.pdf",
    )
    results = RrfHybridRetriever([Bm25Retriever([chunk])]).search("金融负债")

    assert results
