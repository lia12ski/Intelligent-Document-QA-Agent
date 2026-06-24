from __future__ import annotations

from pathlib import Path


def render_pdf_pages(
    pdf_path: str | Path,
    output_dir: str | Path,
    dpi: int = 200,
) -> list[Path]:
    path = Path(pdf_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for page rendering. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)
    image_paths: list[Path] = []

    with fitz.open(path) as document:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = target_dir / f"page_{index:04d}.png"
            pixmap.save(image_path)
            image_paths.append(image_path)

    return image_paths

