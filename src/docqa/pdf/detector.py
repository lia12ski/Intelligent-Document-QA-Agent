from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PageDetection:
    page_number: int
    text_length: int
    image_count: int

    @property
    def has_usable_text(self) -> bool:
        return self.text_length >= 40

    @property
    def looks_scanned(self) -> bool:
        return self.text_length < 40 and self.image_count > 0


@dataclass(frozen=True)
class PdfDetectionResult:
    file_path: str
    page_count: int
    total_text_length: int
    average_text_length: float
    total_image_count: int
    text_page_count: int
    scanned_like_page_count: int
    pdf_type: str
    recommended_strategy: str
    reasons: list[str]
    pages: list[PageDetection]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pages"] = [asdict(page) for page in self.pages]
        return data


def classify_pdf(
    file_path: str,
    pages: list[PageDetection],
    scanned_ratio_threshold: float = 0.6,
    text_ratio_threshold: float = 0.8,
) -> PdfDetectionResult:
    page_count = len(pages)
    total_text_length = sum(page.text_length for page in pages)
    total_image_count = sum(page.image_count for page in pages)
    text_page_count = sum(1 for page in pages if page.has_usable_text)
    scanned_like_page_count = sum(1 for page in pages if page.looks_scanned)
    average_text_length = total_text_length / page_count if page_count else 0.0

    if page_count == 0:
        pdf_type = "empty"
        recommended_strategy = "reject"
        reasons = ["pdf has no pages"]
    else:
        text_ratio = text_page_count / page_count
        scanned_ratio = scanned_like_page_count / page_count

        if text_ratio >= text_ratio_threshold:
            pdf_type = "text"
            recommended_strategy = "text"
            reasons = [
                f"{text_page_count}/{page_count} pages contain usable text layer",
            ]
        elif scanned_ratio >= scanned_ratio_threshold:
            pdf_type = "scanned"
            recommended_strategy = "ocr"
            reasons = [
                f"{scanned_like_page_count}/{page_count} pages have sparse text and images",
            ]
        else:
            pdf_type = "mixed"
            recommended_strategy = "ocr"
            reasons = [
                "text layer is incomplete or inconsistent",
                "ocr is safer for preserving evidence across pages",
            ]

    return PdfDetectionResult(
        file_path=file_path,
        page_count=page_count,
        total_text_length=total_text_length,
        average_text_length=round(average_text_length, 2),
        total_image_count=total_image_count,
        text_page_count=text_page_count,
        scanned_like_page_count=scanned_like_page_count,
        pdf_type=pdf_type,
        recommended_strategy=recommended_strategy,
        reasons=reasons,
        pages=pages,
    )


def detect_pdf(pdf_path: str | Path) -> PdfDetectionResult:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path}")

    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for PDF detection. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    pages: list[PageDetection] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text") or ""
            image_count = len(page.get_images(full=True))
            pages.append(
                PageDetection(
                    page_number=index,
                    text_length=len(text.strip()),
                    image_count=image_count,
                )
            )

    return classify_pdf(str(path), pages)

