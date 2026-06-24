from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docqa.config import load_settings
from docqa.parsing.chunker import build_chunks
from docqa.parsing.factory import create_parser
from docqa.pdf.detector import detect_pdf
from docqa.retrieval.manifest import build_manifest, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse PDF and build document index.")
    parser.add_argument("--pdf", required=True, help="Path to source PDF.")
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Only detect PDF type and recommended parsing strategy.",
    )
    args = parser.parse_args()

    settings = load_settings()
    detection = detect_pdf(args.pdf)

    output_dir = Path(settings.processed_data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "pdf_detection.json"
    output_path.write_text(
        json.dumps(detection.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(detection.to_dict(), ensure_ascii=False, indent=2))
    print(f"\nDetection result written to: {output_path}")

    if args.detect_only:
        return

    if detection.recommended_strategy == "reject":
        raise RuntimeError("PDF cannot be parsed because detector recommended rejection.")

    document_parser = create_parser(settings)
    parse_result = document_parser.parse(args.pdf, detection, output_dir)
    pages_output_path = output_dir / "pages.json"
    pages_output_path.write_text(
        json.dumps(parse_result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Parsed pages written to: {pages_output_path}")
    if parse_result.warnings:
        print("Warnings:")
        for warning in parse_result.warnings:
            print(f"- {warning}")

    chunk_result = build_chunks(
        parse_result,
        inline_table_keywords=settings.inline_table_keywords,
    )
    chunks_output_path = output_dir / "chunks.json"
    tables_output_path = output_dir / "tables.json"
    chunks_output_path.write_text(
        json.dumps(chunk_result.to_chunks_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tables_output_path.write_text(
        json.dumps(chunk_result.to_tables_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest = build_manifest(
        source_file=args.pdf,
        parser_provider=parse_result.parser_provider,
        strategy=parse_result.strategy,
        page_count=len(parse_result.pages),
        chunk_count=len(chunk_result.chunks),
        table_count=len(chunk_result.tables),
    )
    manifest_path = write_manifest(output_dir, manifest)

    print(f"Chunks written to: {chunks_output_path}")
    print(f"Tables written to: {tables_output_path}")
    print(f"Index manifest written to: {manifest_path}")
    if chunk_result.warnings:
        print("Chunk warnings:")
        for warning in chunk_result.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
