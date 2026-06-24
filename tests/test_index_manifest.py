import json
from pathlib import Path
import shutil
import uuid

import pytest

from docqa.retrieval.manifest import (
    build_manifest,
    validate_manifest,
    validate_target_keywords,
    write_manifest,
)


@pytest.fixture()
def workspace_tmp_path():
    path = Path(".test_tmp") / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_validate_manifest_warns_when_missing(workspace_tmp_path) -> None:
    result = validate_manifest(workspace_tmp_path)

    assert result.ok is False
    assert "cannot be verified" in result.message


def test_validate_manifest_can_allow_missing_manifest_for_legacy_indexes(workspace_tmp_path) -> None:
    result = validate_manifest(workspace_tmp_path, require_manifest=False)

    assert result.ok is True
    assert "cannot be verified" in result.message


def test_validate_manifest_accepts_matching_source_hash(workspace_tmp_path) -> None:
    source = workspace_tmp_path / "sample.pdf"
    source.write_bytes(b"pdf bytes")
    manifest = build_manifest(
        source_file=source,
        parser_provider="local",
        strategy="text",
        page_count=1,
        chunk_count=2,
        table_count=0,
    )
    write_manifest(workspace_tmp_path, manifest)

    result = validate_manifest(workspace_tmp_path)

    assert result.ok is True
    assert "index source verified" in result.message


def test_validate_manifest_rejects_changed_source_file(workspace_tmp_path) -> None:
    source = workspace_tmp_path / "sample.pdf"
    source.write_bytes(b"first version")
    manifest = build_manifest(
        source_file=source,
        parser_provider="local",
        strategy="text",
        page_count=1,
        chunk_count=2,
        table_count=0,
    )
    write_manifest(workspace_tmp_path, manifest)
    source.write_bytes(b"changed version")

    result = validate_manifest(workspace_tmp_path)

    assert result.ok is False
    assert "hash mismatch" in result.message


def test_validate_manifest_rejects_missing_source_file(workspace_tmp_path) -> None:
    source = workspace_tmp_path / "missing.pdf"
    manifest_path = workspace_tmp_path / "index_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_file": str(source),
                "source_sha256": "abc",
                "parser_provider": "local",
                "strategy": "text",
                "page_count": 1,
                "chunk_count": 1,
                "table_count": 0,
                "generated_at": "2026-06-24T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    result = validate_manifest(workspace_tmp_path)

    assert result.ok is False
    assert "source PDF is missing" in result.message


def test_validate_target_keywords_accepts_expected_document(workspace_tmp_path) -> None:
    chunks_path = workspace_tmp_path / "chunks.json"
    chunks_path.write_text(
        json.dumps(
            {
                "source_file": "agent开发作业样本.pdf",
                "chunks": [{"text": "中信证券股份有限公司 2025 半年度报告 财务报表"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = validate_target_keywords(
        chunks_path,
        ("中信证券", "财务报表", "2025 半年度报告"),
    )

    assert result.ok is True


def test_validate_target_keywords_rejects_wrong_document(workspace_tmp_path) -> None:
    chunks_path = workspace_tmp_path / "chunks.json"
    chunks_path.write_text(
        json.dumps(
            {
                "source_file": "gbt-standard.pdf",
                "chunks": [{"text": "GB/T 1568 规定了键的技术条件"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = validate_target_keywords(
        chunks_path,
        ("中信证券", "财务报表", "2025 半年度报告"),
    )

    assert result.ok is False
    assert "does not match expected target keywords" in result.message
