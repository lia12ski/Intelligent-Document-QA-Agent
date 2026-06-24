from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docqa.parsing.schema import DocumentChunk


def load_chunks(path: str | Path) -> list[DocumentChunk]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    chunks_data: list[dict[str, Any]] = data.get("chunks", [])
    return [
        DocumentChunk(
            chunk_id=str(item["chunk_id"]),
            text=str(item["text"]),
            page=int(item["page"]),
            chunk_type=str(item["chunk_type"]),
            source_file=str(item["source_file"]),
            clause_id=item.get("clause_id"),
            section_title=item.get("section_title"),
            table_id=item.get("table_id"),
            confidence=item.get("confidence"),
        )
        for item in chunks_data
    ]
