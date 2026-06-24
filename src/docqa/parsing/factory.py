from __future__ import annotations

from docqa.config import Settings
from docqa.ocr.factory import create_ocr_provider
from docqa.parsing.base import DocumentParser
from docqa.parsing.local_parser import LocalPdfParser
from docqa.parsing.mineru_parser import MineruParser


def create_parser(settings: Settings) -> DocumentParser:
    provider = settings.parser_provider.lower().strip()
    if provider == "local":
        return LocalPdfParser(create_ocr_provider(settings))
    if provider == "mineru":
        return MineruParser(settings)

    raise ValueError(
        f"Unsupported PARSER_PROVIDER={settings.parser_provider!r}. "
        "Expected one of: local, mineru."
    )
