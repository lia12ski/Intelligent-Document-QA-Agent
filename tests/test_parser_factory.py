from docqa.config import Settings
from docqa.parsing.factory import create_parser
from docqa.parsing.local_parser import LocalPdfParser
from docqa.parsing.mineru_parser import MineruParser


def make_settings(parser_provider: str) -> Settings:
    return Settings(
        app_env="test",
        log_level="INFO",
        ocr_provider="tesseract",
        parser_provider=parser_provider,
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


def test_create_local_parser() -> None:
    assert isinstance(create_parser(make_settings("local")), LocalPdfParser)


def test_create_mineru_parser() -> None:
    assert isinstance(create_parser(make_settings("mineru")), MineruParser)


def test_reject_unknown_parser() -> None:
    try:
        create_parser(make_settings("unknown"))
    except ValueError as exc:
        assert "Unsupported PARSER_PROVIDER" in str(exc)
    else:
        raise AssertionError("expected ValueError")
