from docqa.retrieval.tokenizer import tokenize


def test_tokenize_chinese_adds_bigrams_and_filters_common_chars() -> None:
    tokens = tokenize("键的材料有什么要求")

    assert "材料" in tokens
    assert "要求" in tokens
    assert "的" not in tokens


def test_tokenize_financial_question_keeps_domain_terms() -> None:
    tokens = tokenize("被投资单位名称有哪些")

    assert "投资" in tokens
    assert "单位" in tokens
    assert "名称" in tokens
