from __future__ import annotations

from pathlib import Path

from docqa.ocr.base import OcrProvider
from docqa.parsing.schema import TextBlock


class TesseractOcrProvider(OcrProvider):
    provider_name = "tesseract"

    def __init__(self, lang: str = "chi_sim+eng") -> None:
        self._lang = lang

    def recognize(self, image_path: str | Path, page_number: int) -> list[TextBlock]:
        try:
            from PIL import Image
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError(
                "Tesseract OCR requires pillow and pytesseract. Install them and ensure "
                "the tesseract binary is available in PATH."
            ) from exc

        image = Image.open(image_path)
        data = pytesseract.image_to_data(image, lang=self._lang, output_type=Output.DICT)

        blocks: list[TextBlock] = []
        count = len(data.get("text", []))
        for index in range(count):
            text = str(data["text"][index]).strip()
            if not text:
                continue

            try:
                confidence = float(data["conf"][index]) / 100
            except (ValueError, TypeError):
                confidence = None

            left = float(data["left"][index])
            top = float(data["top"][index])
            width = float(data["width"][index])
            height = float(data["height"][index])

            blocks.append(
                TextBlock(
                    text=text,
                    page=page_number,
                    bbox=[left, top, left + width, top + height],
                    confidence=confidence,
                    source=self.provider_name,
                )
            )

        return blocks

