from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from docqa.pdf.detector import PdfDetectionResult
from docqa.parsing.schema import ParseResult


class DocumentParser(ABC):
    provider_name: str

    @abstractmethod
    def parse(
        self,
        pdf_path: str | Path,
        detection: PdfDetectionResult,
        output_dir: str | Path,
    ) -> ParseResult:
        """Parse a PDF into normalized pages."""

