from __future__ import annotations

from pathlib import Path

from docqa.ocr.base import OcrProvider
from docqa.parsing.schema import TextBlock


class PaddleOcrProvider(OcrProvider):
    provider_name = "paddleocr"

    def __init__(self, lang: str = "ch") -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR is not installed. Install paddleocr and paddlepaddle, "
                "or set OCR_PROVIDER=tesseract."
            ) from exc

        self._ocr = PaddleOCR(use_angle_cls=True, lang=lang)

    def recognize(self, image_path: str | Path, page_number: int) -> list[TextBlock]:
        result = self._ocr.ocr(str(image_path), cls=True)
        blocks: list[TextBlock] = []

        for page_result in result or []:
            for item in page_result or []:
                if len(item) < 2:
                    continue
                points, text_info = item
                if len(text_info) < 2:
                    continue
                text, confidence = text_info[0], float(text_info[1])
                xs = [float(point[0]) for point in points]
                ys = [float(point[1]) for point in points]
                blocks.append(
                    TextBlock(
                        text=str(text).strip(),
                        page=page_number,
                        bbox=[min(xs), min(ys), max(xs), max(ys)],
                        confidence=confidence,
                        source=self.provider_name,
                    )
                )

        return [block for block in blocks if block.text]

