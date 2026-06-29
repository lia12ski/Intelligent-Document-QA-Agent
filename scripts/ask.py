from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docqa.agent.qa_agent import QaAgent
from docqa.agent.query_analyzer import QueryAnalyzerConfig
from docqa.config import load_settings
from docqa.llm.client import build_llm_client
from docqa.retrieval.factory import build_retriever
from docqa.retrieval.manifest import validate_manifest, validate_target_keywords
from docqa.retrieval.store import load_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question against the document index.")
    parser.add_argument("question", help="Question to answer.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of evidence chunks to return.")
    parser.add_argument("--show-prompt", action="store_true", help="Include the grounding prompt in output.")
    args = parser.parse_args()

    settings = load_settings()
    chunks_path = Path(settings.processed_data_dir) / "chunks.json"
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"Chunk index not found: {chunks_path}. Run scripts/ingest.py first."
        )
    validation = validate_manifest(
        settings.processed_data_dir,
        require_manifest=settings.require_index_manifest,
    )
    if not validation.ok:
        raise RuntimeError(validation.message)
    if settings.target_validation_enabled:
        target_validation = validate_target_keywords(
            chunks_path,
            settings.target_document_keywords,
        )
        if not target_validation.ok:
            raise RuntimeError(target_validation.message)

    chunks = load_chunks(chunks_path)
    retriever = build_retriever(chunks, settings)
    agent = QaAgent(
        retriever,
        min_score=settings.retrieval_min_score,
        llm_client=build_llm_client(settings),
        show_prompt=args.show_prompt,
        focus_terms=settings.domain_focus_terms,
        query_config=QueryAnalyzerConfig(
            table_terms=settings.query_table_terms,
            numeric_terms=settings.query_numeric_terms,
            definition_terms=settings.query_definition_terms,
            generic_phrases=settings.query_generic_phrases,
            ocr_replacements=settings.query_ocr_replacements,
            generic_amount_expansion=settings.generic_amount_expansion,
        ),
        dense_min_score=settings.dense_min_score,
        all_chunks=chunks,
    )
    answer = agent.answer(args.question, top_k=args.top_k)
    print(json.dumps(answer.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
