from __future__ import annotations

from dataclasses import dataclass

from docqa.agent.qa_agent import QaAgent
from docqa.evaluation.cases import EvaluationCase


@dataclass(frozen=True)
class EvaluationMetrics:
    retrieval_hit: bool
    citation_present: bool
    self_check_matched: bool
    correct_rejection: bool | None
    table_hit: bool | None
    multi_chunk_used: bool | None
    required_terms_present: bool
    expected_answer_terms_present: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "retrieval_hit": self.retrieval_hit,
            "citation_present": self.citation_present,
            "self_check_matched": self.self_check_matched,
            "correct_rejection": self.correct_rejection,
            "table_hit": self.table_hit,
            "multi_chunk_used": self.multi_chunk_used,
            "required_terms_present": self.required_terms_present,
            "expected_answer_terms_present": self.expected_answer_terms_present,
        }


@dataclass(frozen=True)
class EvaluationItem:
    case_id: str
    case_type: str
    question: str
    passed: bool
    expected_behavior: str
    expected_mode: str
    metrics: EvaluationMetrics
    answer: dict[str, object]
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "question": self.question,
            "passed": self.passed,
            "expected_behavior": self.expected_behavior,
            "expected_mode": self.expected_mode,
            "metrics": self.metrics.to_dict(),
            "answer": self.answer,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class EvaluationReport:
    total: int
    passed: int
    items: list[EvaluationItem]

    def to_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.total - self.passed,
            "retrieval_hit_rate": _rate(item.metrics.retrieval_hit for item in self.items),
            "citation_rate": _rate(item.metrics.citation_present for item in self.items),
            "self_check_match_rate": _rate(item.metrics.self_check_matched for item in self.items),
            "items": [item.to_dict() for item in self.items],
        }


def run_evaluation(agent: QaAgent, cases: list[EvaluationCase]) -> EvaluationReport:
    items: list[EvaluationItem] = []
    for case in cases:
        answer = agent.answer(case.question)
        answer_data = answer.to_dict()
        sources = [source for source in answer_data.get("sources", []) if isinstance(source, dict)]
        grounded = bool(answer.self_check.get("grounded"))
        notes: list[str] = []

        citation_present = _citation_present(sources) if case.requires_citation else True
        retrieval_hit = _retrieval_hit(case, sources, str(answer_data.get("answer", "")))
        required_terms_present = _required_terms_present(case, answer_data, sources)
        expected_answer_terms_present = _expected_answer_terms_present(case, answer_data)
        self_check_matched = _self_check_matches(case, grounded)
        correct_rejection = (not grounded) if case.expected_reject else None
        table_hit = _has_chunk_type(sources, "table") if case.expected_chunk_type == "table" else None
        multi_chunk_used = len({source.get("chunk_id") for source in sources if source.get("chunk_id")}) >= case.min_sources
        if case.expected_mode != "multi_chunk_answer":
            multi_chunk_metric: bool | None = None
        else:
            multi_chunk_metric = multi_chunk_used

        metrics = EvaluationMetrics(
            retrieval_hit=retrieval_hit,
            citation_present=citation_present,
            self_check_matched=self_check_matched,
            correct_rejection=correct_rejection,
            table_hit=table_hit,
            multi_chunk_used=multi_chunk_metric,
            required_terms_present=required_terms_present,
            expected_answer_terms_present=expected_answer_terms_present,
        )
        passed = _case_passed(case, metrics, grounded)

        if not retrieval_hit:
            notes.append("retrieval did not hit expected source type/clause/terms")
        if not citation_present:
            notes.append("source citation missing")
        if not self_check_matched:
            notes.append("self-check result does not match expected mode")
        if case.expected_chunk_type == "table" and table_hit is False:
            notes.append("expected table source")
        if case.expected_mode == "multi_chunk_answer" and multi_chunk_metric is False:
            notes.append("expected multiple source chunks")
        if case.required_terms and not required_terms_present:
            notes.append("required terms missing from answer/evidence")
        if case.expected_answer_terms and not expected_answer_terms_present:
            notes.append("expected answer terms missing from final answer")

        items.append(
            EvaluationItem(
                case_id=case.case_id,
                case_type=case.case_type,
                question=case.question,
                passed=passed,
                expected_behavior=case.expected_behavior,
                expected_mode=case.expected_mode,
                metrics=metrics,
                answer=answer_data,
                notes=notes,
            )
        )

    return EvaluationReport(
        total=len(items),
        passed=sum(1 for item in items if item.passed),
        items=items,
    )


def _case_passed(case: EvaluationCase, metrics: EvaluationMetrics, grounded: bool) -> bool:
    if case.expected_reject:
        return metrics.correct_rejection is True and metrics.self_check_matched
    if case.expected_mode == "clarify_or_answer":
        return (
            metrics.retrieval_hit
            and metrics.citation_present
            and metrics.self_check_matched
            and (grounded or metrics.required_terms_present)
        )
    if case.expected_mode == "multi_chunk_answer":
        return (
            grounded
            and metrics.retrieval_hit
            and metrics.citation_present
            and metrics.self_check_matched
            and metrics.multi_chunk_used is True
            and metrics.expected_answer_terms_present
        )
    return (
        grounded
        and metrics.retrieval_hit
        and metrics.citation_present
        and metrics.self_check_matched
        and metrics.required_terms_present
        and metrics.expected_answer_terms_present
    )


def _retrieval_hit(
    case: EvaluationCase,
    sources: list[dict[str, object]],
    answer_text: str,
) -> bool:
    if not sources and case.expected_reject:
        return True
    if case.expected_chunk_type and not _has_chunk_type(sources, case.expected_chunk_type):
        return False
    if case.expected_clause_prefix and not _has_clause_prefix(sources, case.expected_clause_prefix):
        return False
    if case.required_terms:
        if _required_terms_in_sources(case.required_terms, sources):
            return True
        if case.expected_mode == "clarify_or_answer":
            return all(term in answer_text for term in case.required_terms)
        return False
    return bool(sources) or case.expected_reject


def _citation_present(sources: list[dict[str, object]]) -> bool:
    return any(source.get("page") and source.get("chunk_id") for source in sources)


def _has_chunk_type(sources: list[dict[str, object]], chunk_type: str) -> bool:
    return any(source.get("chunk_type") == chunk_type for source in sources)


def _has_clause_prefix(sources: list[dict[str, object]], clause_prefix: str) -> bool:
    return any(str(source.get("clause_id") or "").startswith(clause_prefix) for source in sources)


def _required_terms_present(
    case: EvaluationCase,
    answer_data: dict[str, object],
    sources: list[dict[str, object]],
) -> bool:
    if not case.required_terms:
        return True
    text = str(answer_data.get("answer", "")) + "\n" + "\n".join(
        str(source.get("snippet", "")) for source in sources
    )
    return all(term in text for term in case.required_terms)


def _expected_answer_terms_present(
    case: EvaluationCase,
    answer_data: dict[str, object],
) -> bool:
    if not case.expected_answer_terms:
        return True
    answer_text = str(answer_data.get("answer", ""))
    return all(term in answer_text for term in case.expected_answer_terms)


def _required_terms_in_sources(required_terms: list[str], sources: list[dict[str, object]]) -> bool:
    text = "\n".join(str(source.get("snippet", "")) for source in sources)
    return all(term in text for term in required_terms)


def _self_check_matches(case: EvaluationCase, grounded: bool) -> bool:
    if case.expected_reject:
        return not grounded
    if case.expected_mode == "clarify_or_answer":
        return grounded
    return grounded


def _rate(values) -> float:
    values = list(values)
    if not values:
        return 0.0
    return round(sum(1 for value in values if value) / len(values), 4)
