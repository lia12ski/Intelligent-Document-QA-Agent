from docqa.config import Settings
from docqa.ocr.factory import create_ocr_provider


def make_settings(ocr_provider: str) -> Settings:
    return Settings(
        app_env="test",
        log_level="INFO",
        ocr_provider=ocr_provider,
        parser_provider="local",
        mineru_base_url="",
        mineru_api_key="",
        mineru_model_version="vlm",
        mineru_poll_interval_seconds=1,
        mineru_max_wait_seconds=1,
        llm_provider="mock",
        llm_timeout_seconds=1,
        openai_base_url="",
        openai_api_key="",
        openai_model="",
        deepseek_base_url="",
        deepseek_api_key="",
        deepseek_model="",
        ollama_base_url="",
        ollama_model="",
        embedding_model="mock",
        extra_site_packages="",
        dense_retrieval_enabled=False,
        dense_fail_open=True,
        dense_backend="memory",
        require_index_manifest=True,
        target_validation_enabled=True,
        target_document_keywords=("中信证券", "财务报表", "2025 半年度报告"),
        raw_data_dir="data/raw",
        processed_data_dir="data/processed",
        index_dir="data/index",
    )


def test_reject_unknown_ocr_provider() -> None:
    try:
        create_ocr_provider(make_settings("unknown"))
    except ValueError as exc:
        assert "Unsupported OCR_PROVIDER" in str(exc)
    else:
        raise AssertionError("expected ValueError")
