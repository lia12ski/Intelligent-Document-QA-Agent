from docqa.config_suggestion import (
    DomainConfigPromptInput,
    build_domain_config_prompt,
    format_env_suggestions,
    parse_env_suggestions,
)
from docqa.evaluation.cases import EvaluationCase
from docqa.parsing.schema import DocumentChunk


def test_build_domain_config_prompt_includes_chunks_and_questions() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text="被投资单位名称\n2025年6月30日\n账面价值\n合计\n100",
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
        )
    ]
    cases = [
        EvaluationCase(
            case_id="book_value",
            question="2025年6月30日账面价值是多少？",
            expected_behavior="返回账面价值",
        )
    ]

    prompt = build_domain_config_prompt(
        DomainConfigPromptInput(
            business_scene="财报文档问答",
            chunks=chunks,
            cases=cases,
        )
    )

    assert "财报文档问答" in prompt
    assert "page_1_table_1" in prompt
    assert "2025年6月30日账面价值是多少" in prompt
    assert "TARGET_DOCUMENT_KEYWORDS" in prompt


def test_parse_and_format_env_suggestions() -> None:
    raw = """
    下面是配置：
    TARGET_DOCUMENT_KEYWORDS=中信证券,财务报表
    INLINE_TABLE_KEYWORDS=项目,合计,账面价值
    QUERY_OCR_REPLACEMENTS=价植=>价值,帐面=>账面
    UNKNOWN_KEY=ignored
    """

    suggestions = parse_env_suggestions(raw)
    formatted = format_env_suggestions(suggestions)

    assert suggestions["TARGET_DOCUMENT_KEYWORDS"] == "中信证券,财务报表"
    assert "UNKNOWN_KEY" not in suggestions
    assert "INLINE_TABLE_KEYWORDS=项目,合计,账面价值" in formatted
    assert "QUERY_OCR_REPLACEMENTS=价植=>价值,帐面=>账面" in formatted
