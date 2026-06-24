from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from docqa.parsing.schema import TextBlock


class OcrProvider(ABC):
    provider_name: str

    @abstractmethod
    def recognize(self, image_path: str | Path, page_number: int) -> list[TextBlock]:
        """Recognize text blocks from a rendered page image."""

