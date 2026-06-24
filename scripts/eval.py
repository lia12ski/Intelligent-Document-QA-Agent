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
from docqa.evaluation.cases import DEFAULT_CASES, FINANCIAL_SAMPLE_CASES, GBT_STANDARD_CASES
from docqa.evaluation.runner import run_evaluation
from docqa.llm.client import build_llm_client
from docqa.retrieval.factory import build_retriever
from docqa.retrieval.manifest import validate_manifest, validate_target_keywords
from docqa.retrieval.store import load_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate QA behavior on fixed cases.")
    parser.add_argument(
        "--case-set",
        choices=["gbt", "gbt-standard", "financial-sample"],
        default="financial-sample",
        help="Evaluation case set to run.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full answer details including source snippets.",
    )
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
    )
    if args.case_set == "financial-sample":
        cases = FINANCIAL_SAMPLE_CASES
    elif args.case_set in {"gbt", "gbt-standard"}:
        cases = GBT_STANDARD_CASES
    else:
        cases = DEFAULT_CASES
    report = run_evaluation(agent, cases)
    data = report.to_dict()
    if not args.verbose:
        for item in data["items"]:
            answer_text = item["answer"].get("answer", "") if isinstance(item["answer"], dict) else str(item["answer"])
            item["answer"] = answer_text
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
