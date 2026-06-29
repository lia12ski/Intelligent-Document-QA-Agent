from docqa.pdf.detector import PageDetection, classify_pdf

import app


def test_safe_pdf_name_keeps_ascii_name() -> None:
    assert app._safe_pdf_name("Quarterly Report 2026.pdf") == "Quarterly_Report_2026.pdf"


def test_safe_pdf_name_falls_back_for_non_ascii_name() -> None:
    assert app._safe_pdf_name("财报样本.pdf") == "document.pdf"


def test_suspicious_script_family_ignores_ascii_and_cjk() -> None:
    assert app._suspicious_script_family("A") == ""
    assert app._suspicious_script_family("中") == ""


def test_suspicious_script_family_detects_unexpected_script() -> None:
    assert app._suspicious_script_family("च") == "DEVANAGARI"


def test_text_quality_warnings_detect_empty_text() -> None:
    warnings = app._text_quality_warnings({"chunks": [{"text": "   "}]})

    assert warnings == ["解析结果没有可用文本，请尝试 OCR 或 MinerU 解析。"]


def test_text_quality_warnings_detect_mojibake_like_text() -> None:
    warnings = app._text_quality_warnings(
        {
            "chunks": [
                {
                    "text": (
                        "BERT(चԭTransformerጱ݌ݻᖫᎱ) "
                        "decoder กขค ሀሁሂ абв деж"
                    )
                }
            ]
        }
    )

    assert warnings
    assert "疑似乱码" in warnings[0]


def test_text_quality_warnings_accept_clean_text() -> None:
    warnings = app._text_quality_warnings(
        {"chunks": [{"text": "财务报表覆盖期间为2025年半年度，答案需要引用来源。"}]}
    )

    assert warnings == []


def test_detection_for_parse_keeps_auto_detection() -> None:
    detection = classify_pdf(
        "sample.pdf",
        [PageDetection(page_number=1, text_length=120, image_count=0)],
    )

    assert app._detection_for_parse(detection, "auto") is detection


def test_detection_for_parse_forces_ocr() -> None:
    detection = classify_pdf(
        "sample.pdf",
        [PageDetection(page_number=1, text_length=120, image_count=0)],
    )

    forced = app._detection_for_parse(detection, "ocr")

    assert forced is not detection
    assert forced.recommended_strategy == "ocr"
    assert "user forced OCR in Streamlit demo" in forced.reasons
