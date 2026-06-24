from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docqa.config import load_settings
from docqa.config_suggestion import (
    DomainConfigPromptInput,
    build_domain_config_prompt,
    format_env_suggestions,
    parse_env_suggestions,
)
from docqa.evaluation.cases import FINANCIAL_SAMPLE_CASES, GBT_STANDARD_CASES
from docqa.llm.client import build_llm_client
from docqa.retrieval.store import load_chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use an LLM to suggest domain keyword configuration from parsed chunks.",
    )
    parser.add_argument(
        "--business-scene",
        default="财报文档问答",
        help="Business scene, e.g. 财报文档问答 / 合同审查 / 合规制度问答.",
    )
    parser.add_argument(
        "--chunks",
        default=None,
        help="Path to chunks.json. Defaults to PROCESSED_DATA_DIR/chunks.json.",
    )
    parser.add_argument(
        "--case-set",
        choices=["financial-sample", "gbt-standard"],
        default="financial-sample",
        help="Evaluation cases used as typical questions in the prompt.",
    )
    parser.add_argument(
        "--output",
        default="domain_config.suggested.env",
        help="Output file for suggested .env config.",
    )
    parser.add_argument("--max-chunks", type=int, default=10)
    parser.add_argument("--max-chunk-chars", type=int, default=700)
    parser.add_argument(
        "--dry-run-prompt",
        action="store_true",
        help="Print the prompt only; do not call LLM.",
    )
    args = parser.parse_args()

    settings = load_settings()
    chunks_path = Path(args.chunks) if args.chunks else Path(settings.processed_data_dir) / "chunks.json"
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunk index not found: {chunks_path}. Run scripts/ingest.py first.")

    chunks = load_chunks(chunks_path)
    cases = FINANCIAL_SAMPLE_CASES if args.case_set == "financial-sample" else GBT_STANDARD_CASES
    prompt = build_domain_config_prompt(
        DomainConfigPromptInput(
            business_scene=args.business_scene,
            chunks=chunks,
            cases=cases,
            max_chunks=args.max_chunks,
            max_chunk_chars=args.max_chunk_chars,
        )
    )

    if args.dry_run_prompt:
        print(prompt)
        return

    llm_client = build_llm_client(settings)
    if llm_client is None:
        raise RuntimeError(
            "LLM_PROVIDER is disabled. Set LLM_PROVIDER=deepseek/openai/ollama and configure the key, "
            "or run with --dry-run-prompt to inspect the prompt."
        )

    raw_response = llm_client.generate(prompt)
    suggestions = parse_env_suggestions(raw_response)
    if not suggestions:
        raise RuntimeError("LLM did not return recognizable .env config lines.")

    output_path = Path(args.output)
    output_path.write_text(format_env_suggestions(suggestions), encoding="utf-8")
    print(f"Suggested config written to: {output_path}")
    print("Review manually, then validate with scripts/ingest.py and scripts/eval.py before copying to .env.")


if __name__ == "__main__":
    main()
