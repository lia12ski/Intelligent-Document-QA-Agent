from __future__ import annotations

from docqa.config import Settings
from docqa.ocr.base import OcrProvider
from docqa.ocr.paddle_ocr import PaddleOcrProvider
from docqa.ocr.tesseract_ocr import TesseractOcrProvider


def create_ocr_provider(settings: Settings) -> OcrProvider:
    provider = settings.ocr_provider.lower().strip()
    if provider == "paddleocr":
        return PaddleOcrProvider()
    if provider == "tesseract":
        return TesseractOcrProvider()

    raise ValueError(
        f"Unsupported OCR_PROVIDER={settings.ocr_provider!r}. "
        "Expected one of: paddleocr, tesseract."
    )
