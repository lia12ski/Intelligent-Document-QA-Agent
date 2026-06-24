from docqa.parsing.schema import ParsedPage
from docqa.parsing.table_extractor import extract_tables_from_page, table_to_markdown


def test_extract_simple_table_from_aligned_text() -> None:
    page = ParsedPage(
        page=2,
        text="项目  要求\n材料  45钢\n硬度  30 HRC",
    )

    tables = extract_tables_from_page(page)

    assert len(tables) == 1
    assert tables[0].rows[1] == ["材料", "45钢"]
    assert "| 项目 | 要求 |" in table_to_markdown(tables[0])

