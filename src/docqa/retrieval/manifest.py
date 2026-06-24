from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


MANIFEST_FILENAME = "index_manifest.json"


@dataclass(frozen=True)
class IndexManifest:
    source_file: str
    source_sha256: str
    parser_provider: str
    strategy: str
    page_count: int
    chunk_count: int
    table_count: int
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManifestValidation:
    ok: bool
    message: str


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(
    *,
    source_file: str | Path,
    parser_provider: str,
    strategy: str,
    page_count: int,
    chunk_count: int,
    table_count: int,
) -> IndexManifest:
    source_path = Path(source_file)
    return IndexManifest(
        source_file=str(source_path),
        source_sha256=sha256_file(source_path),
        parser_provider=parser_provider,
        strategy=strategy,
        page_count=page_count,
        chunk_count=chunk_count,
        table_count=table_count,
        generated_at=datetime.now(UTC).isoformat(),
    )


def write_manifest(output_dir: str | Path, manifest: IndexManifest) -> Path:
    path = Path(output_dir) / MANIFEST_FILENAME
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def validate_manifest(processed_dir: str | Path, require_manifest: bool = True) -> ManifestValidation:
    manifest_path = Path(processed_dir) / MANIFEST_FILENAME
    if not manifest_path.exists():
        return ManifestValidation(
            ok=not require_manifest,
            message=(
                "index_manifest.json not found; source PDF consistency cannot be verified. "
                "Run scripts/ingest.py again to create a verifiable index."
            ),
        )

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_file = Path(str(data.get("source_file", "")))
    if not source_file.exists():
        return ManifestValidation(
            ok=False,
            message=f"indexed source PDF is missing: {source_file}",
        )

    expected_sha256 = str(data.get("source_sha256", ""))
    actual_sha256 = sha256_file(source_file)
    if not expected_sha256 or expected_sha256 != actual_sha256:
        return ManifestValidation(
            ok=False,
            message=(
                "indexed source PDF hash mismatch; rerun scripts/ingest.py before answering. "
                f"source_file={source_file}"
            ),
        )

    return ManifestValidation(ok=True, message=f"index source verified: {source_file}")


def validate_target_keywords(
    chunks_path: str | Path,
    expected_keywords: tuple[str, ...],
) -> ManifestValidation:
    if not expected_keywords:
        return ManifestValidation(ok=True, message="target keyword validation skipped")

    path = Path(chunks_path)
    if not path.exists():
        return ManifestValidation(ok=False, message=f"chunk index not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    haystack_parts = [str(data.get("source_file", ""))]
    haystack_parts.extend(str(item.get("text", "")) for item in data.get("chunks", []))
    haystack = "\n".join(haystack_parts).lower()
    missing = [keyword for keyword in expected_keywords if keyword.lower() not in haystack]
    if missing:
        return ManifestValidation(
            ok=False,
            message=(
                "indexed document does not match expected target keywords. "
                f"missing={missing}. Re-ingest the correct target PDF before QA/evaluation."
            ),
        )
    return ManifestValidation(
        ok=True,
        message=f"target keywords verified: {', '.join(expected_keywords)}",
    )
