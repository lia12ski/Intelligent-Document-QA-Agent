from __future__ import annotations

from dataclasses import dataclass
import re

from docqa.retrieval.bm25 import RetrievalResult
from docqa.retrieval.tokenizer import tokenize


@dataclass(frozen=True)
class SelfCheckResult:
    grounded: bool
    confidence: str
    risk_flags: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "grounded": self.grounded,
            "confidence": self.confidence,
            "risk_flags": self.risk_flags,
        }


def self_check(
    results: list[RetrievalResult],
    min_score: float,
    question: str = "",
    answer_text: str = "",
    dense_min_score: float = 0.4,
) -> SelfCheckResult:
    if not results:
        return SelfCheckResult(
            grounded=False,
            confidence="low",
            risk_flags=["no supporting evidence found"],
        )

    best_score = results[0].score
    risk_flags: list[str] = []
    if best_score < min_score:
        risk_flags.append("retrieval score below answer threshold")
    if results[0].dense_score is not None and results[0].dense_score < dense_min_score:
        risk_flags.append("max similarity score below dense threshold")
    if any(result.chunk.confidence == 0.0 for result in results):
        risk_flags.append("zero-confidence OCR evidence detected")

    important_terms = _important_query_terms(question)
    if important_terms and not _evidence_covers_terms(results[0].chunk.text, important_terms):
        risk_flags.append("evidence lacks important query terms")
    if answer_text and not _answer_numbers_are_grounded(answer_text, results):
        risk_flags.append("answer numeric values not found in evidence")
    if answer_text and _contains_hedging_words(answer_text):
        risk_flags.append("hedging words detected")

    grounded = (
        best_score >= min_score
        and "zero-confidence OCR evidence detected" not in risk_flags
        and "evidence lacks important query terms" not in risk_flags
        and "max similarity score below dense threshold" not in risk_flags
        and "answer numeric values not found in evidence" not in risk_flags
    )
    confidence = "low" if not grounded or "hedging words detected" in risk_flags else "medium"

    return SelfCheckResult(
        grounded=grounded,
        confidence=confidence,
        risk_flags=risk_flags,
    )


def _important_query_terms(question: str) -> list[str]:
    terms = []
    for token in tokenize(question):
        if len(token) < 2:
            continue
        if any(char.isdigit() for char in token):
            terms.append(token)
            continue
        if _is_meaningful_cjk_bigram(token):
            terms.append(token)
        elif token.isascii() and len(token) >= 3:
            terms.append(token)
    return list(dict.fromkeys(terms))


def _evidence_covers_terms(text: str, important_terms: list[str]) -> bool:
    evidence_terms = set(tokenize(text))
    overlap = [term for term in important_terms if term in evidence_terms]
    if not important_terms:
        return True
    required = 1 if len(important_terms) <= 2 else 2
    return len(overlap) >= required


def _is_meaningful_cjk_bigram(token: str) -> bool:
    if len(token) != 2:
        return False
    weak_chars = {"的", "了", "是", "在", "和", "与", "或", "及", "这", "个", "什", "么", "哪", "些"}
    return not any(char in weak_chars for char in token)


def _answer_numbers_are_grounded(answer_text: str, results: list[RetrievalResult]) -> bool:
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?%?", answer_text)
    if not numbers:
        return True
    evidence = "\n".join(result.chunk.text for result in results)
    return all(number in evidence for number in numbers)


def _contains_hedging_words(answer_text: str) -> bool:
    return any(word in answer_text for word in ("可能", "通常", "大概", "一般来说", "推测"))
