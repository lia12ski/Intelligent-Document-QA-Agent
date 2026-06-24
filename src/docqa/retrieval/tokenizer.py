from __future__ import annotations

import re


_TOKEN_RE = re.compile(r"[A-Za-z0-9_.+-]+|[\u4e00-\u9fff]+")
_CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")
_CJK_STOP_CHARS = {
    "的",
    "了",
    "是",
    "在",
    "和",
    "与",
    "或",
    "及",
    "这",
    "个",
    "该",
    "有",
    "无",
    "么",
    "什",
    "哪",
    "些",
    "否",
    "中",
    "为",
    "对",
    "按",
}
_CJK_STOP_WORDS = {
    "这个",
    "是否",
    "什么",
    "哪些",
    "如何",
    "规定",
    "标准",
}


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        raw = match.group(0).lower()
        if _CJK_RE.match(raw):
            tokens.extend(_tokenize_cjk(raw))
        else:
            tokens.append(raw)
    return [token for token in tokens if token]


def _tokenize_cjk(text: str) -> list[str]:
    tokens: list[str] = []
    if text not in _CJK_STOP_WORDS:
        tokens.extend(
            text[index : index + 2]
            for index in range(len(text) - 1)
            if text[index : index + 2] not in _CJK_STOP_WORDS
        )
    tokens.extend(char for char in text if char not in _CJK_STOP_CHARS)
    return tokens
