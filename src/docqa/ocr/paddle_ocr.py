from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from docqa.ocr.base import OcrProvider
from docqa.parsing.schema import TextBlock


class PaddleOcrProvider(OcrProvider):
    provider_name = "paddleocr"

    def __init__(self, lang: str = "ch") -> None:
        _configure_paddle_runtime()
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR is not installed. Install paddleocr and paddlepaddle, "
                "or set OCR_PROVIDER=tesseract."
            ) from exc

        self._ocr = PaddleOCR(use_angle_cls=True, lang=lang)

    def recognize(self, image_path: str | Path, page_number: int) -> list[TextBlock]:
        result = self._run_ocr(image_path)
        blocks: list[TextBlock] = []

        for text, confidence, points in _iter_ocr_items(result):
            clean_text = str(text).strip()
            if not clean_text:
                continue
            blocks.append(
                TextBlock(
                    text=clean_text,
                    page=page_number,
                    bbox=_bbox_from_points(points),
                    confidence=confidence,
                    source=self.provider_name,
                )
            )

        return blocks

    def _run_ocr(self, image_path: str | Path):
        try:
            return self._ocr.ocr(
                str(image_path),
                use_textline_orientation=True,
            )
        except TypeError as exc:
            if "use_textline_orientation" not in str(exc):
                raise
            return self._ocr.ocr(str(image_path), cls=True)


def _iter_ocr_items(result: Any):
    for page_result in result or []:
        if _has_key(page_result, "rec_texts"):
            yield from _iter_paddle3_items(page_result)
            continue
        yield from _iter_paddle2_items(page_result)


def _iter_paddle3_items(page_result: Any):
    texts = _get_value(page_result, "rec_texts")
    scores = _get_value(page_result, "rec_scores")
    polys = _first_present_value(page_result, ("rec_polys", "dt_polys"))
    boxes = _get_value(page_result, "rec_boxes")
    texts = [] if texts is None else texts
    scores = [] if scores is None else scores
    polys = [] if polys is None else polys
    boxes = [] if boxes is None else boxes

    for index, text in enumerate(texts):
        confidence = _optional_float(_index_or_none(scores, index))
        points = _index_or_none(polys, index)
        if points is None:
            points = _index_or_none(boxes, index)
        yield text, confidence, points


def _iter_paddle2_items(page_result: Any):
    for item in page_result or []:
        if len(item) < 2:
            continue
        points, text_info = item
        if len(text_info) < 2:
            continue
        yield text_info[0], _optional_float(text_info[1]), points


def _has_key(value: Any, key: str) -> bool:
    try:
        return key in value
    except TypeError:
        return hasattr(value, key)


def _get_value(value: Any, key: str) -> Any:
    if hasattr(value, "get"):
        return value.get(key)
    try:
        return value[key]
    except (KeyError, TypeError):
        return getattr(value, key, None)


def _first_present_value(value: Any, keys: tuple[str, ...]) -> Any:
    for key in keys:
        item = _get_value(value, key)
        if item is not None:
            return item
    return None


def _index_or_none(values: Any, index: int) -> Any:
    try:
        return values[index]
    except (IndexError, TypeError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _bbox_from_points(points: Any) -> list[float]:
    if points is None:
        return [0.0, 0.0, 0.0, 0.0]
    if hasattr(points, "tolist"):
        points = points.tolist()

    if _is_flat_box(points):
        return [float(points[0]), float(points[1]), float(points[2]), float(points[3])]

    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _is_flat_box(points: Any) -> bool:
    return (
        isinstance(points, (list, tuple))
        and len(points) >= 4
        and not isinstance(points[0], (list, tuple))
    )


def _configure_paddle_runtime() -> None:
    os.environ.setdefault("FLAGS_enable_pir_api", "0")
    os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
    try:
        import paddle
    except ImportError:
        return

    try:
        paddle.framework.set_flags(
            {
                "FLAGS_enable_pir_api": False,
                "FLAGS_enable_pir_in_executor": False,
            }
        )
    except Exception:
        return
