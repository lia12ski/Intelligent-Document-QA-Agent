from docqa.pdf.detector import PageDetection, classify_pdf


def test_classify_text_pdf() -> None:
    result = classify_pdf(
        "sample.pdf",
        [
            PageDetection(page_number=1, text_length=200, image_count=0),
            PageDetection(page_number=2, text_length=180, image_count=1),
        ],
    )

    assert result.pdf_type == "text"
    assert result.recommended_strategy == "text"


def test_classify_scanned_pdf() -> None:
    result = classify_pdf(
        "sample.pdf",
        [
            PageDetection(page_number=1, text_length=0, image_count=1),
            PageDetection(page_number=2, text_length=12, image_count=2),
        ],
    )

    assert result.pdf_type == "scanned"
    assert result.recommended_strategy == "ocr"


def test_classify_mixed_pdf_uses_ocr_strategy() -> None:
    result = classify_pdf(
        "sample.pdf",
        [
            PageDetection(page_number=1, text_length=200, image_count=0),
            PageDetection(page_number=2, text_length=0, image_count=1),
        ],
    )

    assert result.pdf_type == "mixed"
    assert result.recommended_strategy == "ocr"
