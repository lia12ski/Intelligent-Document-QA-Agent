from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TextBlock:
    text: str
    page: int
    bbox: list[float]
    confidence: float | None = None
    source: str = "text_layer"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TableBlock:
    page: int
    rows: list[list[str]]
    bbox: list[float] | None = None
    confidence: float | None = None
    source: str = "parser"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParsedPage:
    page: int
    text: str
    blocks: list[TextBlock] = field(default_factory=list)
    tables: list[TableBlock] = field(default_factory=list)
    image_path: str | None = None
    parse_status: str = "parsed"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["blocks"] = [block.to_dict() for block in self.blocks]
        data["tables"] = [table.to_dict() for table in self.tables]
        return data


@dataclass(frozen=True)
class ParseResult:
    source_file: str
    parser_provider: str
    strategy: str
    pages: list[ParsedPage]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "parser_provider": self.parser_provider,
            "strategy": self.strategy,
            "page_count": len(self.pages),
            "pages": [page.to_dict() for page in self.pages],
            "warnings": self.warnings,
        }



@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    page: int
    chunk_type: str
    source_file: str
    clause_id: str | None = None
    section_title: str | None = None
    table_id: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChunkBuildResult:
    source_file: str
    chunks: list[DocumentChunk]
    tables: list[TableBlock]
    warnings: list[str] = field(default_factory=list)

    def to_chunks_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "chunk_count": len(self.chunks),
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "warnings": self.warnings,
        }

    def to_tables_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "table_count": len(self.tables),
            "tables": [table.to_dict() for table in self.tables],
            "warnings": self.warnings,
        }
