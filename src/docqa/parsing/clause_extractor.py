from __future__ import annotations

import re


CLAUSE_RE = re.compile(r"^(?P<clause>[1-9]\d?(?:\.\d+)*)(?:\s+|[、．])(?P<title>.*)$")
APPENDIX_RE = re.compile(r"^(?P<clause>附录\s*[A-ZＡ-Ｚ])(?:\s+|[、.．])?(?P<title>.*)$", re.IGNORECASE)


def extract_clause_id(line: str) -> str | None:
    stripped = line.strip()
    match = CLAUSE_RE.match(stripped)
    if match:
        clause = match.group("clause")
        title = match.group("title").strip()
        if _looks_like_year_or_number(clause, title):
            return None
        return clause

    appendix_match = APPENDIX_RE.match(stripped)
    if appendix_match:
        return appendix_match.group("clause").replace(" ", "")

    return None


def is_clause_heading(line: str) -> bool:
    return extract_clause_id(line) is not None


def _looks_like_year_or_number(clause: str, title: str) -> bool:
    if len(clause) == 4 and clause.startswith(("19", "20")):
        return True
    if "." in clause and not title:
        return True
    if not title and len(clause) > 2:
        return True
    return False
