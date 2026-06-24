from docqa.parsing.clause_extractor import extract_clause_id, is_clause_heading


def test_extract_numeric_clause_id() -> None:
    assert extract_clause_id("5.1 键的材料") == "5.1"


def test_extract_top_level_clause_id() -> None:
    assert extract_clause_id("6 检验规则") == "6"


def test_non_clause_line() -> None:
    assert extract_clause_id("本标准规定了键的技术条件") is None
    assert not is_clause_heading("本标准规定了键的技术条件")


def test_do_not_treat_year_or_decimal_as_clause() -> None:
    assert extract_clause_id("2025 年1 月1 日至6 月30 日") is None
    assert extract_clause_id("7.19") is None
