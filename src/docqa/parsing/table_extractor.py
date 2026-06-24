from __future__ import annotations

import re

from docqa.parsing.schema import ParsedPage, TableBlock


_TABLE_SPLIT_RE = re.compile(r"\s{2,}|\t+|\|")


def extract_tables_from_page(page: ParsedPage) -> list[TableBlock]:
    candidate_rows: list[list[str]] = []

    for line in _raw_non_empty_lines(page.text):
        row = [cell.strip() for cell in _TABLE_SPLIT_RE.split(line) if cell.strip()]
        has_numeric_or_unit = any(any(char.isdigit() for char in cell) for cell in row)
        if len(row) >= 2 and (has_numeric_or_unit or _looks_like_table_header(row)):
            candidate_rows.append(row)
        else:
            if len(candidate_rows) >= 2:
                break
            candidate_rows = []

    if len(candidate_rows) < 2:
        return []

    return [
        TableBlock(
            page=page.page,
            rows=candidate_rows,
            bbox=None,
            confidence=None,
            source="rule_table_extractor",
        )
    ]


def extract_tables(pages: list[ParsedPage]) -> list[TableBlock]:
    tables: list[TableBlock] = []
    for page in pages:
        tables.extend(page.tables)
        tables.extend(extract_tables_from_page(page))
    return tables


def table_to_markdown(table: TableBlock) -> str:
    if not table.rows:
        return ""

    max_cols = max(len(row) for row in table.rows)
    rows = [row + [""] * (max_cols - len(row)) for row in table.rows]
    header = rows[0]
    separator = ["---"] * max_cols
    body = rows[1:]

    def fmt(row: list[str]) -> str:
        return "| " + " | ".join(row) + " |"

    return "\n".join([fmt(header), fmt(separator), *[fmt(row) for row in body]])


def _looks_like_table_header(row: list[str]) -> bool:
    joined = " ".join(row)
    keywords = ["项目", "名称", "尺寸", "公差", "材料", "要求", "代号", "规格"]
    return any(keyword in joined for keyword in keywords)


def _raw_non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r\n", "\n").splitlines() if line.strip()]
