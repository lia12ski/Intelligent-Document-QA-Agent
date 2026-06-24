from docqa.parsing.mineru_normalizer import pages_from_mineru_content_list


def test_mineru_content_list_to_pages_and_tables() -> None:
    content_list = [
        {
            "type": "text",
            "text": "5.1 键的材料应符合要求",
            "bbox": [1, 2, 3, 4],
            "page_idx": 0,
        },
        {
            "type": "table",
            "table_body": "<table><tr><th>项目</th><th>要求</th></tr><tr><td>材料</td><td>45钢</td></tr></table>",
            "bbox": [10, 20, 30, 40],
            "page_idx": 1,
        },
    ]

    pages = pages_from_mineru_content_list(content_list, "")

    assert len(pages) == 2
    assert pages[0].text == "5.1 键的材料应符合要求"
    assert pages[1].tables[0].rows[1] == ["材料", "45钢"]
    assert "<table>" not in pages[1].text
