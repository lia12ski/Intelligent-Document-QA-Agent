from __future__ import annotations

from collections import defaultdict
from html.parser import HTMLParser
from typing import Any

from docqa.parsing.schema import ParsedPage, TableBlock, TextBlock


def pages_from_mineru_content_list(
    content_list: list[dict[str, Any]],
    markdown_text: str,
) -> list[ParsedPage]:
    pages_by_number: dict[int, list[TextBlock]] = defaultdict(list)
    tables_by_number: dict[int, list[TableBlock]] = defaultdict(list)

    for item in content_list:
        page = int(item.get("page_idx", 0)) + 1
        item_type = str(item.get("type", "text"))
        bbox = _bbox(item.get("bbox"))

        if item_type == "table":
            rows = _table_rows(item)
            if rows:
                tables_by_number[page].append(
                    TableBlock(
                        page=page,
                        rows=rows,
                        bbox=bbox,
                        confidence=None,
                        source="mineru_content_list",
                    )
                )
            continue

        text = _text_from_item(item)
        if text:
            pages_by_number[page].append(
                TextBlock(
                    text=text,
                    page=page,
                    bbox=bbox or [0.0, 0.0, 0.0, 0.0],
                    confidence=None,
                    source=f"mineru_{item_type}",
                )
            )

    if not pages_by_number and markdown_text.strip():
        return [
            ParsedPage(
                page=1,
                text=markdown_text.strip(),
                blocks=[
                    TextBlock(
                        text=markdown_text.strip(),
                        page=1,
                        bbox=[0.0, 0.0, 0.0, 0.0],
                        confidence=None,
                        source="mineru_markdown",
                    )
                ],
                parse_status="parsed",
                warnings=["MinerU content_list was unavailable; used full.md as single page"],
            )
        ]

    pages: list[ParsedPage] = []
    for page_number in sorted(set(pages_by_number) | set(tables_by_number)):
        blocks = pages_by_number.get(page_number, [])
        tables = tables_by_number.get(page_number, [])
        pages.append(
            ParsedPage(
                page=page_number,
                text="\n".join(block.text for block in blocks),
                blocks=blocks,
                tables=tables,
                parse_status="parsed",
            )
        )

    return pages


def _text_from_item(item: dict[str, Any]) -> str:
    for key in (
        "text",
        "content",
        "title",
        "paragraph",
        "paragraph_content",
        "title_content",
        "equation",
        "code_body",
    ):
        if key in item:
            return _flatten_text(item[key])

    content = item.get("content")
    if isinstance(content, dict):
        return _flatten_text(content)

    return ""


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(filter(None, (_flatten_text(item) for item in value))).strip()
    if isinstance(value, dict):
        if "content" in value:
            return _flatten_text(value["content"])
        return "\n".join(filter(None, (_flatten_text(item) for item in value.values()))).strip()
    return str(value).strip()


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def _table_rows(item: dict[str, Any]) -> list[list[str]]:
    for key in ("table_body", "content"):
        value = item.get(key)
        if isinstance(value, str) and "<table" in value.lower():
            return _HtmlTableParser.parse(value)
    return []


class _HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._in_cell = False

    @classmethod
    def parse(cls, html: str) -> list[list[str]]:
        parser = cls()
        parser.feed(html)
        return [[cell.strip() for cell in row] for row in parser.rows if any(cell.strip() for cell in row)]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        if tag.lower() == "tr":
            self._current_row = []
        elif tag.lower() in {"td", "th"}:
            self._current_cell = []
            self._in_cell = True

    def handle_data(self, data: str) -> None:
        if self._in_cell and self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            self._current_row.append("".join(self._current_cell).strip())
            self._current_cell = None
            self._in_cell = False
        elif tag == "tr" and self._current_row is not None:
            self.rows.append(self._current_row)
            self._current_row = None
