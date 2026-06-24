from __future__ import annotations

from pathlib import Path

from docqa.ocr.base import OcrProvider
from docqa.pdf.detector import PdfDetectionResult
from docqa.pdf.renderer import render_pdf_pages
from docqa.parsing.base import DocumentParser
from docqa.parsing.schema import ParsedPage, ParseResult, TextBlock


class LocalPdfParser(DocumentParser):
    provider_name = "local"

    def __init__(self, ocr_provider: OcrProvider) -> None:
        self._ocr_provider = ocr_provider

    def parse(
        self,
        pdf_path: str | Path,
        detection: PdfDetectionResult,
        output_dir: str | Path,
    ) -> ParseResult:
        if detection.recommended_strategy == "text":
            return self._parse_text_layer(pdf_path, detection)

        return self._prepare_ocr_pages(pdf_path, detection, output_dir)

    def _parse_text_layer(
        self,
        pdf_path: str | Path,
        detection: PdfDetectionResult,
    ) -> ParseResult:
        try:
            import fitz  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "PyMuPDF is required for text-layer parsing. Install dependencies with "
                "`pip install -r requirements.txt`."
            ) from exc

        pages: list[ParsedPage] = []
        with fitz.open(pdf_path) as document:
            for page_index, page in enumerate(document, start=1):
                blocks: list[TextBlock] = []
                raw_blocks = page.get_text("blocks") or []
                for block in raw_blocks:
                    if len(block) < 5:
                        continue
                    x0, y0, x1, y1, text = block[:5]
                    clean_text = str(text).strip()
                    if not clean_text:
                        continue
                    blocks.append(
                        TextBlock(
                            text=clean_text,
                            page=page_index,
                            bbox=[float(x0), float(y0), float(x1), float(y1)],
                            confidence=None,
                            source="text_layer",
                        )
                    )

                page_text = "\n".join(block.text for block in blocks)
                pages.append(
                    ParsedPage(
                        page=page_index,
                        text=page_text,
                        blocks=blocks,
                        parse_status="parsed",
                    )
                )

        return ParseResult(
            source_file=str(pdf_path),
            parser_provider=self.provider_name,
            strategy=detection.recommended_strategy,
            pages=pages,
        )

    def _prepare_ocr_pages(
        self,
        pdf_path: str | Path,
        detection: PdfDetectionResult,
        output_dir: str | Path,
    ) -> ParseResult:
        _ = detection
        rendered_dir = Path(output_dir) / "rendered_pages"
        image_paths = render_pdf_pages(pdf_path, rendered_dir)

        pages: list[ParsedPage] = []
        warnings: list[str] = []
        for index, image_path in enumerate(image_paths, start=1):
            try:
                blocks = self._ocr_provider.recognize(image_path, index)
                page_text = "\n".join(block.text for block in blocks)
                pages.append(
                    ParsedPage(
                        page=index,
                        text=page_text,
                        blocks=blocks,
                        image_path=str(image_path),
                        parse_status="parsed",
                    )
                )
            except RuntimeError as exc:
                warning = f"OCR failed on page {index}: {exc}"
                warnings.append(warning)
                pages.append(
                    ParsedPage(
                        page=index,
                        text="",
                        blocks=[],
                        image_path=str(image_path),
                        parse_status="ocr_failed",
                        warnings=[warning],
                    )
                )

        return ParseResult(
            source_file=str(pdf_path),
            parser_provider=self.provider_name,
            strategy="ocr",
            pages=pages,
            warnings=warnings,
        )
