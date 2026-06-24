from pathlib import Path
import tempfile

from docqa.ocr.base import OcrProvider
from docqa.parsing.local_parser import LocalPdfParser
from docqa.parsing.schema import TextBlock
from docqa.pdf.detector import PageDetection, classify_pdf


class FakeOcrProvider(OcrProvider):
    provider_name = "fake"

    def recognize(self, image_path: str | Path, page_number: int) -> list[TextBlock]:
        return [
            TextBlock(
                text=f"第{page_number}页 OCR 文本",
                page=page_number,
                bbox=[0.0, 0.0, 0.0, 0.0],
                confidence=0.93,
                source="fake_ocr",
            )
        ]


def test_local_parser_uses_ocr_provider_for_scanned_pdf(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rendered_image = tmp_path / "page_1.png"
        rendered_image.write_bytes(b"fake image")

        def fake_render_pdf_pages(pdf_path, output_dir):
            _ = pdf_path
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            return [rendered_image]

        monkeypatch.setattr(
            "docqa.parsing.local_parser.render_pdf_pages",
            fake_render_pdf_pages,
        )
        detection = classify_pdf(
            "sample.pdf",
            [PageDetection(page_number=1, text_length=0, image_count=1)],
        )

        result = LocalPdfParser(FakeOcrProvider()).parse("sample.pdf", detection, tmp_path)

        assert result.strategy == "ocr"
        assert result.pages[0].text == "第1页 OCR 文本"
        assert result.pages[0].parse_status == "parsed"
        assert result.pages[0].blocks[0].confidence == 0.93
