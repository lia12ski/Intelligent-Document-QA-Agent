from docqa.config import load_settings


def test_default_target_validation_settings(monkeypatch) -> None:
    monkeypatch.setenv("REQUIRE_INDEX_MANIFEST", "true")
    monkeypatch.setenv("TARGET_VALIDATION_ENABLED", "true")
    monkeypatch.setenv(
        "TARGET_DOCUMENT_KEYWORDS",
        "中信证券,财务报表,2025 半年度报告",
    )

    settings = load_settings()

    assert settings.require_index_manifest is True
    assert settings.target_validation_enabled is True
    assert settings.target_document_keywords == ("中信证券", "财务报表", "2025 半年度报告")


def test_retrieval_and_dense_threshold_settings(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVAL_MIN_SCORE", "0.02")
    monkeypatch.setenv("DENSE_MIN_SCORE", "0.5")

    settings = load_settings()

    assert settings.retrieval_min_score == 0.02
    assert settings.dense_min_score == 0.5


def test_query_analyzer_settings(monkeypatch) -> None:
    monkeypatch.setenv("QUERY_TABLE_TERMS", "合同金额,付款节点")
    monkeypatch.setenv("QUERY_OCR_REPLACEMENTS", "仚同=>合同,金額=>金额")
    monkeypatch.setenv("GENERIC_AMOUNT_EXPANSION", "金额 合同金额 付款节点")

    settings = load_settings()

    assert settings.query_table_terms == ("合同金额", "付款节点")
    assert settings.query_ocr_replacements == (("仚同", "合同"), ("金額", "金额"))
    assert settings.generic_amount_expansion == "金额 合同金额 付款节点"
