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
from docqa.retrieval.manifest import validate_manifest, validate_target_keywords


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate processed index provenance and target document identity.")
    parser.add_argument(
        "--allow-missing-manifest",
        action="store_true",
        help="Warn instead of failing when index_manifest.json is missing.",
    )
    args = parser.parse_args()

    settings = load_settings()
    chunks_path = Path(settings.processed_data_dir) / "chunks.json"
    checks = []

    manifest_check = validate_manifest(
        settings.processed_data_dir,
        require_manifest=not args.allow_missing_manifest and settings.require_index_manifest,
    )
    checks.append({"name": "manifest", **manifest_check.__dict__})

    target_check = validate_target_keywords(
        chunks_path,
        settings.target_document_keywords if settings.target_validation_enabled else (),
    )
    checks.append({"name": "target_keywords", **target_check.__dict__})

    ok = all(item["ok"] for item in checks)
    print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
