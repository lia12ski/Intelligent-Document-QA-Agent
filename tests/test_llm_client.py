from docqa.config import Settings
from docqa.llm.client import OpenAICompatibleClient, build_llm_client


def make_settings(llm_provider: str = "deepseek") -> Settings:
    return Settings(
        app_env="test",
        log_level="INFO",
        ocr_provider="mock",
        parser_provider="local",
        mineru_base_url="",
        mineru_api_key="",
        mineru_model_version="vlm",
        mineru_poll_interval_seconds=1,
        mineru_max_wait_seconds=1,
        llm_provider=llm_provider,
        llm_timeout_seconds=1,
        openai_base_url="",
        openai_api_key="",
        openai_model="",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_api_key="test-key",
        deepseek_model="deepseek-chat",
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


def test_build_deepseek_client() -> None:
    client = build_llm_client(make_settings("deepseek"))

    assert isinstance(client, OpenAICompatibleClient)
    assert client.provider_name == "deepseek"
    assert client.model == "deepseek-chat"


def test_mock_llm_provider_is_disabled() -> None:
    assert build_llm_client(make_settings("mock")) is None
