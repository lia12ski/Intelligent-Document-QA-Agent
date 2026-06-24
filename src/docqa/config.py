from __future__ import annotations

from dataclasses import dataclass
import os
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


@dataclass(frozen=True)
class Settings:
    app_env: str
    log_level: str
    ocr_provider: str
    parser_provider: str
    mineru_base_url: str
    mineru_api_key: str
    mineru_model_version: str
    mineru_poll_interval_seconds: int
    mineru_max_wait_seconds: int
    llm_provider: str
    llm_timeout_seconds: int
    openai_base_url: str
    openai_api_key: str
    openai_model: str
    deepseek_base_url: str
    deepseek_api_key: str
    deepseek_model: str
    ollama_base_url: str
    ollama_model: str
    embedding_model: str
    extra_site_packages: str
    dense_retrieval_enabled: bool
    dense_fail_open: bool
    dense_backend: str
    require_index_manifest: bool
    target_validation_enabled: bool
    target_document_keywords: tuple[str, ...]
    raw_data_dir: str
    processed_data_dir: str
    index_dir: str
    retrieval_min_score: float = 0.01
    dense_min_score: float = 0.4
    inline_table_keywords: tuple[str, ...] = ()
    domain_focus_terms: tuple[str, ...] = ()
    query_table_terms: tuple[str, ...] = ()
    query_numeric_terms: tuple[str, ...] = ()
    query_definition_terms: tuple[str, ...] = ()
    query_generic_phrases: tuple[str, ...] = ()
    query_ocr_replacements: tuple[tuple[str, str], ...] = ()
    generic_amount_expansion: str = ""


def load_settings() -> Settings:
    load_dotenv()
    extra_site_packages = os.getenv("EXTRA_SITE_PACKAGES", "")
    _apply_extra_site_packages(extra_site_packages)
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        ocr_provider=os.getenv("OCR_PROVIDER", "paddleocr"),
        parser_provider=os.getenv("PARSER_PROVIDER", "local"),
        mineru_base_url=os.getenv("MINERU_BASE_URL", "https://mineru.net"),
        mineru_api_key=os.getenv("MINERU_API_KEY", ""),
        mineru_model_version=os.getenv("MINERU_MODEL_VERSION", "vlm"),
        mineru_poll_interval_seconds=int(os.getenv("MINERU_POLL_INTERVAL_SECONDS", "5")),
        mineru_max_wait_seconds=int(os.getenv("MINERU_MAX_WAIT_SECONDS", "600")),
        llm_provider=os.getenv("LLM_PROVIDER", "mock"),
        llm_timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        openai_base_url=os.getenv("OPENAI_BASE_URL", os.getenv("LLM_BASE_URL", "")),
        openai_api_key=os.getenv("OPENAI_API_KEY", os.getenv("LLM_API_KEY", "")),
        openai_model=os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "")),
        deepseek_base_url=os.getenv(
            "DEEPSEEK_BASE_URL",
            os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
        ),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", os.getenv("LLM_API_KEY", "")),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", os.getenv("LLM_MODEL", "deepseek-chat")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL",
            "BAAI/bge-small-zh-v1.5",
        ),
        extra_site_packages=extra_site_packages,
        dense_retrieval_enabled=_env_bool("DENSE_RETRIEVAL_ENABLED", False),
        dense_fail_open=_env_bool("DENSE_FAIL_OPEN", True),
        dense_backend=os.getenv("DENSE_BACKEND", "memory"),
        retrieval_min_score=float(
            os.getenv("RETRIEVAL_MIN_SCORE", "0.01")
        ),
        dense_min_score=float(os.getenv("DENSE_MIN_SCORE", "0.4")),
        require_index_manifest=_env_bool("REQUIRE_INDEX_MANIFEST", True),
        target_validation_enabled=_env_bool("TARGET_VALIDATION_ENABLED", True),
        target_document_keywords=_env_tuple(
            "TARGET_DOCUMENT_KEYWORDS",
            ("中信证券", "财务报表", "2025 半年度报告"),
        ),
        inline_table_keywords=_env_tuple(
            "INLINE_TABLE_KEYWORDS",
            (
                "项目",
                "要求",
                "账面价值",
                "被投资单位名称",
                "本期增加",
                "本期减少",
                "合计",
                "金额",
                "到期日",
                "金融负债",
                "即期偿还",
                "减值准备",
            ),
        ),
        domain_focus_terms=_env_tuple(
            "DOMAIN_FOCUS_TERMS",
            (
                "账面价值",
                "金额",
                "合计",
                "到期日",
                "被投资单位名称",
                "金融负债",
                "财务报表",
                "期间",
            ),
        ),
        query_table_terms=_env_tuple(
            "QUERY_TABLE_TERMS",
            ("表格", "对应", "项目", "账面价值", "合计", "金额", "到期日", "被投资单位"),
        ),
        query_numeric_terms=_env_tuple(
            "QUERY_NUMERIC_TERMS",
            ("多少", "数值", "比例", "金额", "余额"),
        ),
        query_definition_terms=_env_tuple(
            "QUERY_DEFINITION_TERMS",
            ("是什么", "定义", "含义", "指什么", "期间"),
        ),
        query_generic_phrases=_env_tuple(
            "QUERY_GENERIC_PHRASES",
            ("这个标准", "这个", "标准", "请问", "文档中", "文档里", "是否", "规定了"),
        ),
        query_ocr_replacements=_env_replacements(
            "QUERY_OCR_REPLACEMENTS",
            (
                ("价植", "价值"),
                ("价直", "价值"),
                ("帐面", "账面"),
                ("帐戸", "账户"),
                ("賬面", "账面"),
                ("金額", "金额"),
                ("負债", "负债"),
                ("财務", "财务"),
            ),
        ),
        generic_amount_expansion=os.getenv(
            "GENERIC_AMOUNT_EXPANSION",
            "金额 合计 账面价值 金融负债",
        ),
        raw_data_dir=os.getenv("RAW_DATA_DIR", "data/raw"),
        processed_data_dir=os.getenv("PROCESSED_DATA_DIR", "data/processed"),
        index_dir=os.getenv("INDEX_DIR", "data/index"),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _apply_extra_site_packages(path_value: str) -> None:
    for raw_path in path_value.split(os.pathsep):
        path = raw_path.strip()
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


def _env_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_replacements(
    name: str,
    default: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    value = os.getenv(name)
    if not value:
        return default
    replacements: list[tuple[str, str]] = []
    for item in value.split(","):
        if "=>" not in item:
            continue
        source, target = item.split("=>", 1)
        source = source.strip()
        target = target.strip()
        if source and target:
            replacements.append((source, target))
    return tuple(replacements) or default
