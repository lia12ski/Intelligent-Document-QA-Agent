from docqa.agent.query_analyzer import QueryAnalyzerConfig, analyze_query, rewrite_query


def test_analyze_table_query() -> None:
    analysis = analyze_query("2025年6月30日账面价值是多少？")

    assert analysis.intent == "table"


def test_rewrite_query_removes_generic_words() -> None:
    assert rewrite_query("这个标准是否规定了国外认证流程？") == "国外认证流程"


def test_rewrite_query_repairs_common_ocr_errors() -> None:
    analysis = analyze_query("2025年6月30日账面价植是多少？")

    assert analysis.intent == "table"
    assert analysis.rewritten_query == "2025年6月30日账面价值是多少"


def test_rewrite_query_expands_generic_amount_question() -> None:
    assert rewrite_query("金额是多少？") == "金额 合计 账面价值 金融负债"


def test_analyze_count_query() -> None:
    analysis = analyze_query("decoder出现了几次？")

    assert analysis.intent == "count"


def test_query_analyzer_can_use_domain_config() -> None:
    config = QueryAnalyzerConfig(
        table_terms=("合同金额",),
        numeric_terms=("多少",),
        definition_terms=("是什么",),
        generic_phrases=("这个合同",),
        ocr_replacements=(("仚同", "合同"),),
        generic_amount_expansion="金额 合同金额 付款节点",
    )

    analysis = analyze_query("仚同金额是多少？", config)

    assert analysis.intent == "table"
    assert analysis.rewritten_query == "合同金额是多少"


def test_generic_amount_expansion_is_configurable() -> None:
    config = QueryAnalyzerConfig(generic_amount_expansion="金额 合同金额 付款节点")

    assert rewrite_query("金额是多少？", config) == "金额 合同金额 付款节点"
