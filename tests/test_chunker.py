from docqa.parsing.chunker import build_chunks
from docqa.parsing.schema import ParsedPage, ParseResult


def test_build_clause_and_paragraph_chunks() -> None:
    result = ParseResult(
        source_file="sample.pdf",
        parser_provider="local",
        strategy="text",
        pages=[
            ParsedPage(
                page=1,
                text="前言\n5 技术要求\n5.1 键的材料应符合要求\n5.2 表面质量应符合要求",
            )
        ],
    )

    chunks = build_chunks(result).chunks

    assert any(chunk.chunk_type == "paragraph" for chunk in chunks)
    assert any(chunk.clause_id == "5.1" for chunk in chunks)
    assert any(chunk.clause_id == "5.2" for chunk in chunks)


def test_build_chunks_marks_inline_financial_tables() -> None:
    result = ParseResult(
        source_file="sample.pdf",
        parser_provider="local",
        strategy="text",
        pages=[
            ParsedPage(
                page=1,
                text=(
                    "被投资单位名称\n"
                    "2024年12月31日\n"
                    "本期增加\n"
                    "本期减少\n"
                    "2025年6月30日\n"
                    "账面价值\n"
                    "合计\n"
                    "9,607,514,080.96\n"
                    "449,995,947.17\n"
                    "270,808,595.80\n"
                    "9,786,701,432.33"
                ),
            )
        ],
    )

    chunk_result = build_chunks(result)

    assert any(chunk.chunk_type == "table" for chunk in chunk_result.chunks)
    assert chunk_result.tables
