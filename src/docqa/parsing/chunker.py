from __future__ import annotations

import re

from docqa.parsing.clause_extractor import extract_clause_id
from docqa.parsing.normalizer import normalize_lines, normalize_text
from docqa.parsing.schema import ChunkBuildResult, DocumentChunk, ParseResult, ParsedPage, TableBlock
from docqa.parsing.table_extractor import extract_tables, table_to_markdown


_INLINE_TABLE_KEYWORDS = (
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
)


def build_chunks(
    parse_result: ParseResult,
    max_chars: int = 900,
    inline_table_keywords: tuple[str, ...] = _INLINE_TABLE_KEYWORDS,
) -> ChunkBuildResult:
    chunks: list[DocumentChunk] = []
    warnings: list[str] = []

    for page in parse_result.pages:
        page_chunks = _build_page_chunks(
            parse_result.source_file,
            page,
            max_chars,
            inline_table_keywords,
        )
        chunks.extend(page_chunks)

    extracted_tables = extract_tables(parse_result.pages)
    for index, table in enumerate(extracted_tables, start=1):
        markdown = table_to_markdown(table)
        if not markdown:
            continue
        chunks.append(
            DocumentChunk(
                chunk_id=f"page_{table.page}_table_{index}",
                text=markdown,
                page=table.page,
                chunk_type="table",
                source_file=parse_result.source_file,
                section_title="table",
                table_id=f"table_{index}",
                confidence=table.confidence,
            )
        )

    inline_tables = [_chunk_to_table_block(chunk) for chunk in chunks if chunk.chunk_type == "table"]
    tables = [*extracted_tables, *inline_tables]

    if not chunks:
        warnings.append("no chunks were produced; OCR or text extraction may have failed")

    return ChunkBuildResult(
        source_file=parse_result.source_file,
        chunks=chunks,
        tables=tables,
        warnings=warnings,
    )


def _build_page_chunks(
    source_file: str,
    page: ParsedPage,
    max_chars: int,
    inline_table_keywords: tuple[str, ...],
) -> list[DocumentChunk]:
    lines = normalize_lines(page.text)
    if not lines:
        return []

    chunks: list[DocumentChunk] = []
    current_lines: list[str] = []
    current_clause_id: str | None = None
    chunk_index = 1

    for line in lines:
        clause_id = extract_clause_id(line)
        should_flush = False
        if clause_id and current_lines:
            should_flush = True
        elif current_lines and len("\n".join([*current_lines, line])) > max_chars:
            should_flush = True

        if should_flush:
            chunks.append(
                _make_text_chunk(
                    source_file=source_file,
                    page=page.page,
                    chunk_index=chunk_index,
                    lines=current_lines,
                    clause_id=current_clause_id,
                    inline_table_keywords=inline_table_keywords,
                )
            )
            chunk_index += 1
            current_lines = []

        if clause_id:
            current_clause_id = clause_id
        current_lines.append(line)

    if current_lines:
        chunks.append(
            _make_text_chunk(
                source_file=source_file,
                page=page.page,
                chunk_index=chunk_index,
                lines=current_lines,
                clause_id=current_clause_id,
                inline_table_keywords=inline_table_keywords,
            )
        )

    return chunks


def _make_text_chunk(
    source_file: str,
    page: int,
    chunk_index: int,
    lines: list[str],
    clause_id: str | None,
    inline_table_keywords: tuple[str, ...],
) -> DocumentChunk:
    text = normalize_text("\n".join(lines))
    table_like = clause_id is None and _looks_like_inline_table(text, inline_table_keywords)

    if clause_id:
        chunk_type = "clause"
        id_suffix = f"clause_{clause_id.replace('.', '_')}"
        section_title = _section_title(text, clause_id)
        table_id = None
    elif table_like:
        chunk_type = "table"
        id_suffix = f"table_{chunk_index}"
        section_title = "table"
        table_id = f"inline_table_{page}_{chunk_index}"
    else:
        chunk_type = "paragraph"
        id_suffix = f"paragraph_{chunk_index}"
        section_title = None
        table_id = None

    return DocumentChunk(
        chunk_id=f"page_{page}_{id_suffix}",
        text=text,
        page=page,
        chunk_type=chunk_type,
        source_file=source_file,
        clause_id=clause_id,
        section_title=section_title,
        table_id=table_id,
    )


def _section_title(text: str, clause_id: str | None) -> str | None:
    if not clause_id:
        return None
    first_line = text.splitlines()[0].strip()
    if first_line.startswith(clause_id):
        return first_line
    return None


def _looks_like_inline_table(
    text: str,
    inline_table_keywords: tuple[str, ...] = _INLINE_TABLE_KEYWORDS,
) -> bool:
    lines = normalize_lines(text)
    if len(lines) < 4:
        return False

    joined = "".join(lines)
    keyword_hits = sum(1 for keyword in inline_table_keywords if keyword in joined)
    numeric_lines = sum(1 for line in lines if re.search(r"\d", line))
    short_lines = sum(1 for line in lines if len(line) <= 32)
    mostly_numeric_lines = sum(
        1
        for line in lines
        if re.fullmatch(r"[\d,.\-()% ]+", line.replace("，", ",")) is not None
    )

    return (
        (keyword_hits >= 2 and numeric_lines >= 3 and short_lines >= 4)
        or (keyword_hits >= 1 and numeric_lines >= 6 and mostly_numeric_lines >= 3)
    )


def _chunk_to_table_block(chunk: DocumentChunk) -> TableBlock:
    rows = [[line] for line in normalize_lines(chunk.text)]
    if not rows:
        rows = [[chunk.text]]
    return TableBlock(
        page=chunk.page,
        rows=rows,
        bbox=None,
        confidence=chunk.confidence,
        source="inline_table_chunk",
    )
