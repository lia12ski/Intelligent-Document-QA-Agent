from docqa.pdf.detector import PageDetection, classify_pdf

import app


class SettingsStub:
    def __init__(self, parser_provider: str, mineru_api_key: str = "") -> None:
        self.parser_provider = parser_provider
        self.mineru_api_key = mineru_api_key


def test_streamlit_defaults_to_mineru_when_key_is_configured() -> None:
    settings = SettingsStub(parser_provider="local", mineru_api_key="key")

    assert app._default_streamlit_parser_provider(settings) == "mineru"


def test_streamlit_keeps_local_default_without_mineru_key() -> None:
    settings = SettingsStub(parser_provider="local", mineru_api_key="")

    assert app._default_streamlit_parser_provider(settings) == "local"


def test_auto_parse_retries_ocr_for_bad_text_layer() -> None:
    detection = classify_pdf(
        "sample.pdf",
        [PageDetection(page_number=1, text_length=120, image_count=1)],
    )

    assert detection.recommended_strategy == "text"
    assert app._should_retry_with_ocr(
        strategy_override="auto",
        detection=detection,
        chunk_count=4,
        quality_warnings=["bad text layer"],
    )


def test_auto_parse_does_not_retry_ocr_for_clean_chunks() -> None:
    detection = classify_pdf(
        "sample.pdf",
        [PageDetection(page_number=1, text_length=120, image_count=1)],
    )

    assert not app._should_retry_with_ocr(
        strategy_override="auto",
        detection=detection,
        chunk_count=4,
        quality_warnings=[],
    )


def test_text_quality_warning_detects_mixed_script_mojibake() -> None:
    warnings = app._text_quality_warnings(
        {
            "chunks": [
                {
                    "text": (
                        "BERT(चԭTransformerጱ݌ݻᖫᎱ) "
                        "ԅՋԍฎ݌ݻጱ ၸ෭ಡ໢ᬷᕷև"
                    )
                }
            ]
        }
    )

    assert warnings
