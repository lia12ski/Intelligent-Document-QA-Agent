from __future__ import annotations

import re


_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("，", ",").replace("。", ".")
    text = text.replace("：", ":").replace("；", ";")
    text = text.replace("（", "(").replace("）", ")")
    text = "\n".join(_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def normalize_lines(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [line for line in normalized.splitlines() if line.strip()]

