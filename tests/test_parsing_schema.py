from docqa.parsing.schema import ParsedPage, ParseResult, TextBlock


def test_parse_result_serializes_pages_and_blocks() -> None:
    result = ParseResult(
        source_file="sample.pdf",
        parser_provider="local",
        strategy="text",
        pages=[
            ParsedPage(
                page=1,
                text="example text",
                blocks=[
                    TextBlock(
                        text="example text",
                        page=1,
                        bbox=[0.0, 1.0, 2.0, 3.0],
                        source="text_layer",
                    )
                ],
            )
        ],
    )

    data = result.to_dict()

    assert data["page_count"] == 1
    assert data["pages"][0]["blocks"][0]["text"] == "example text"
    assert data["pages"][0]["parse_status"] == "parsed"

