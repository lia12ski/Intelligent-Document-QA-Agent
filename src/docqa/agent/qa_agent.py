from __future__ import annotations

from dataclasses import dataclass
import re

from docqa.agent.prompt_builder import build_grounding_prompt
from docqa.agent.query_analyzer import QueryAnalysis, QueryAnalyzerConfig, analyze_query
from docqa.agent.self_check import self_check
from docqa.llm.client import LlmClient
from docqa.parsing.schema import DocumentChunk
from docqa.retrieval.bm25 import RetrievalResult
from docqa.retrieval.hybrid import Retriever


NO_ANSWER_TEXT = "文档中未检索到足够可靠的依据，因此不能给出确定答案。"
DEFAULT_FOCUS_TERMS = (
    "账面价值",
    "金额",
    "合计",
    "到期日",
    "被投资单位名称",
    "金融负债",
    "财务报表",
    "期间",
)


@dataclass(frozen=True)
class QaAnswer:
    question: str
    answer: str
    sources: list[dict[str, object]]
    self_check: dict[str, object]
    query_analysis: dict[str, object]
    retrieval_attempts: list[dict[str, object]]
    generation_policy: str = "context_only_with_page_clause_citations"
    generation_provider: str = "extractive"
    generation_error: str | None = None
    prompt: str | None = None

    def to_dict(self) -> dict[str, object]:
        data = {
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources,
            "self_check": self.self_check,
            "query_analysis": self.query_analysis,
            "retrieval_attempts": self.retrieval_attempts,
            "generation_policy": self.generation_policy,
            "generation_provider": self.generation_provider,
        }
        if self.generation_error:
            data["generation_error"] = self.generation_error
        if self.prompt:
            data["prompt"] = self.prompt
        return data


class QaAgent:
    def __init__(
        self,
        retriever: Retriever,
        min_score: float = 0.01,
        llm_client: LlmClient | None = None,
        show_prompt: bool = False,
        focus_terms: tuple[str, ...] = DEFAULT_FOCUS_TERMS,
        query_config: QueryAnalyzerConfig | None = None,
        dense_min_score: float = 0.4,
        all_chunks: list[DocumentChunk] | None = None,
    ) -> None:
        self._retriever = retriever
        self._min_score = min_score
        self._llm_client = llm_client
        self._show_prompt = show_prompt
        self._focus_terms = focus_terms
        self._query_config = query_config or QueryAnalyzerConfig()
        self._dense_min_score = dense_min_score
        self._all_chunks = list(all_chunks or [])

    def answer(self, question: str, top_k: int = 5) -> QaAnswer:
        analysis = analyze_query(question, self._query_config)
        count_answer = self._answer_count_query(question, analysis, top_k)
        if count_answer is not None:
            return count_answer

        search_query = analysis.rewritten_query or question
        results = self._retriever.search(search_query, top_k=top_k)
        attempts = [{"query": search_query, "result_count": len(results)}]
        check = self_check(
            results,
            min_score=self._min_score,
            question=question,
            dense_min_score=self._dense_min_score,
        )

        if not check.grounded and analysis.rewritten_query:
            retry_results = self._retriever.search(question, top_k=top_k)
            retry_check = self_check(
                retry_results,
                min_score=self._min_score,
                question=question,
                dense_min_score=self._dense_min_score,
            )
            attempts.append(
                {
                    "query": question,
                    "result_count": len(retry_results),
                    "retry": True,
                }
            )
            if retry_check.grounded or (retry_results and not results):
                results = retry_results
                check = retry_check

        if not check.grounded:
            return QaAnswer(
                question=question,
                answer=NO_ANSWER_TEXT,
                sources=[_source_from_result(result) for result in results],
                self_check=check.to_dict(),
                query_analysis=analysis.to_dict(),
                retrieval_attempts=attempts,
                generation_provider="reject",
            )

        prompt = build_grounding_prompt(question, results)
        answer_text, generation_provider, generation_error = self._generate_answer(
            question,
            analysis,
            prompt,
            results,
            self._focus_terms,
        )
        check = self_check(
            results,
            min_score=self._min_score,
            question=question,
            answer_text=answer_text,
            dense_min_score=self._dense_min_score,
        )
        if not check.grounded:
            return QaAnswer(
                question=question,
                answer=NO_ANSWER_TEXT,
                sources=[_source_from_result(result) for result in results],
                self_check=check.to_dict(),
                query_analysis=analysis.to_dict(),
                retrieval_attempts=attempts,
                generation_provider="reject_after_generation",
                generation_error=generation_error,
            )

        return QaAnswer(
            question=question,
            answer=answer_text,
            sources=[_source_from_result(result) for result in results],
            self_check=check.to_dict(),
            query_analysis=analysis.to_dict(),
            retrieval_attempts=attempts,
            generation_provider=generation_provider,
            generation_error=generation_error,
            prompt=prompt if self._show_prompt else None,
        )

    def _generate_answer(
        self,
        question: str,
        analysis: QueryAnalysis,
        prompt: str,
        results: list[RetrievalResult],
        focus_terms: tuple[str, ...],
    ) -> tuple[str, str, str | None]:
        deterministic_answer = _extract_deterministic_table_value(
            question,
            analysis,
            results,
        )
        if deterministic_answer:
            return deterministic_answer, "extractive_deterministic", None

        if self._llm_client is not None:
            try:
                return self._llm_client.generate(prompt), self._llm_client.provider_name, None
            except Exception as exc:
                return (
                    _extractive_answer(question, analysis, results, focus_terms),
                    "extractive_fallback",
                    f"{type(exc).__name__}: {exc}",
                )
        return _extractive_answer(question, analysis, results, focus_terms), "extractive", None

    def _answer_count_query(
        self,
        question: str,
        analysis: QueryAnalysis,
        top_k: int,
    ) -> QaAnswer | None:
        if analysis.intent != "count" or not self._all_chunks:
            return None

        target = _extract_count_target(analysis.rewritten_query or question)
        if not target:
            return None

        matches = _count_term_occurrences(self._all_chunks, target)
        total = sum(count for _, count in matches)
        source_results = [
            RetrievalResult(chunk=chunk, score=float(count), source="deterministic_count")
            for chunk, count in matches[:top_k]
        ]
        if total:
            locations = "；".join(
                f"第{chunk.page}页/{chunk.chunk_id}（{count}次）"
                for chunk, count in matches[:top_k]
            )
            answer_text = f"“{target}”在已解析文本中共出现 {total} 次。命中位置：{locations}。"
            risk_flags: list[str] = []
        else:
            answer_text = f"在已解析文本中没有找到“{target}”。"
            risk_flags = ["term not found in parsed chunks"]

        return QaAnswer(
            question=question,
            answer=answer_text,
            sources=[_source_from_result(result) for result in source_results],
            self_check={
                "grounded": True,
                "confidence": "medium",
                "risk_flags": risk_flags,
            },
            query_analysis=analysis.to_dict(),
            retrieval_attempts=[
                {
                    "query": target,
                    "result_count": len(matches),
                    "tool": "deterministic_count",
                }
            ],
            generation_provider="deterministic_count",
        )


def _source_from_result(result: RetrievalResult) -> dict[str, object]:
    chunk = result.chunk
    return {
        "page": chunk.page,
        "chunk_id": chunk.chunk_id,
        "chunk_type": chunk.chunk_type,
        "clause_id": chunk.clause_id,
        "section_title": chunk.section_title,
        "table_id": chunk.table_id,
        "score": round(result.score, 4),
        "retrieval_source": result.source,
        "dense_score": result.dense_score,
        "snippet": _compact(chunk.text, max_length=220),
    }


def _extract_count_target(question: str) -> str | None:
    patterns = (
        r"(.+?)(?:出现|提到|被提到|命中|包含)(?:了)?(?:几次|多少次|几遍|多少遍|几处|多少处)",
        r"(?:几次|多少次|几遍|多少遍|几处|多少处).{0,8}(?:出现|提到|被提到|命中|包含).{0,4}(.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if not match:
            continue
        target = _clean_count_target(match.group(1))
        if target:
            return target
    return None


def _clean_count_target(target: str) -> str:
    target = re.sub(
        r"^(请问|帮我看下|帮我统计|统计|文档中|全文中|本文中|这份文档中|这个文档中|在文档中|在全文中|在本文中)+",
        "",
        target.strip(),
    )
    target = re.sub(r"(这个词|这个术语|这个短语|该词|该术语|该短语)$", "", target)
    return target.strip(" \t\r\n？?。；;，,：:\"'“”‘’（）()[]【】")


def _count_term_occurrences(
    chunks: list[DocumentChunk],
    target: str,
) -> list[tuple[DocumentChunk, int]]:
    pattern = _term_occurrence_pattern(target)
    matches: list[tuple[DocumentChunk, int]] = []
    for chunk in chunks:
        count = len(pattern.findall(chunk.text))
        if count:
            matches.append((chunk, count))
    return matches


def _term_occurrence_pattern(target: str) -> re.Pattern[str]:
    escaped = re.escape(target)
    if re.fullmatch(r"[A-Za-z0-9_.+-]+", target):
        return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _extractive_answer(
    question: str,
    analysis: QueryAnalysis,
    results: list[RetrievalResult],
    focus_terms: tuple[str, ...] = DEFAULT_FOCUS_TERMS,
) -> str:
    if not results:
        return NO_ANSWER_TEXT

    if analysis.intent in {"table", "numeric"}:
        answer = _extract_table_or_numeric_answer(
            original_question=question,
            extraction_question=analysis.rewritten_query or question,
            results=results,
            domain_focus_terms=focus_terms,
        )
        if answer:
            return answer

    focused = _focused_evidence_lines(results, question, focus_terms)
    if focused:
        return "根据检索到的文档证据：" + "；".join(focused[:5])

    evidence_parts = []
    for result in results[:3]:
        chunk = result.chunk
        evidence_parts.append(
            f"第{chunk.page}页/{chunk.chunk_id}：{_compact(chunk.text, max_length=180)}"
        )
    return "根据检索到的文档证据：" + "；".join(evidence_parts)


def _extract_deterministic_table_value(
    question: str,
    analysis: QueryAnalysis,
    results: list[RetrievalResult],
) -> str | None:
    if analysis.intent not in {"table", "numeric"}:
        return None
    preferred_results = [result for result in results if result.chunk.chunk_type == "table"] or results
    return _extract_explicit_table_value(
        analysis.rewritten_query or question,
        preferred_results,
    )


def _extract_table_or_numeric_answer(
    original_question: str,
    extraction_question: str,
    results: list[RetrievalResult],
    domain_focus_terms: tuple[str, ...] = DEFAULT_FOCUS_TERMS,
) -> str | None:
    focus_terms = _focus_terms(extraction_question, domain_focus_terms)
    preferred_results = [result for result in results if result.chunk.chunk_type == "table"] or results

    explicit_value = _extract_explicit_table_value(extraction_question, preferred_results)
    if explicit_value:
        return explicit_value

    evidence_parts: list[str] = []
    for result in preferred_results[:3]:
        excerpt = _best_excerpt(result.chunk.text, focus_terms)
        evidence_parts.append(f"第{result.chunk.page}页/{result.chunk.chunk_id}：{excerpt}")

    if not evidence_parts:
        return None

    if "金额" in original_question and "账面价值" not in _normalize_for_match(original_question):
        return "问题中的“金额”指向不够具体。文档里最相关的金额证据是：" + "；".join(evidence_parts)

    if "账面价值" in _normalize_for_match(extraction_question):
        return "文档命中了“账面价值”相关表格片段：" + "；".join(evidence_parts)

    return "根据检索到的表格证据：" + "；".join(evidence_parts)


def _extract_explicit_table_value(
    question: str,
    results: list[RetrievalResult],
) -> str | None:
    normalized_question = _normalize_for_match(question)
    if "账面价值" not in normalized_question:
        return None

    question_dates = re.findall(r"\d{4}年\d{1,2}月\d{1,2}日", question)
    if not question_dates:
        return None

    for result in results:
        value = _extract_total_book_value_for_date(result.chunk.text, question_dates[0])
        if value:
            return (
                f"合计行中，{question_dates[0]}账面价值为 {value}。"
                f"来源：第{result.chunk.page}页/{result.chunk.chunk_id}。"
            )
    return None


def _extract_total_book_value_for_date(text: str, date_text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_lines = [_normalize_for_match(line) for line in lines]
    normalized_date = _normalize_for_match(date_text)
    if normalized_date not in "".join(normalized_lines):
        return None

    total_indexes = [
        index
        for index, normalized_line in enumerate(normalized_lines)
        if normalized_line == "合计"
    ]
    for total_index in total_indexes:
        numbers = _following_numeric_lines(lines[total_index + 1 :])
        # Current financial table order around the total row is:
        # opening book value, increase, decrease, ending book value, impairment.
        if len(numbers) >= 4:
            return numbers[3]
    return None


def _following_numeric_lines(lines: list[str]) -> list[str]:
    numbers: list[str] = []
    for line in lines:
        normalized_line = line.replace("，", ",").strip()
        if re.fullmatch(r"-|[\d,]+(?:\.\d+)?", normalized_line):
            if normalized_line != "-":
                numbers.append(normalized_line)
            continue
        if numbers:
            break
    return numbers


def _focused_evidence_lines(
    results: list[RetrievalResult],
    question: str,
    domain_focus_terms: tuple[str, ...] = DEFAULT_FOCUS_TERMS,
) -> list[str]:
    focus_terms = _focus_terms(question, domain_focus_terms)
    lines: list[str] = []
    for result in results:
        chunk = result.chunk
        excerpt = _best_excerpt(chunk.text, focus_terms)
        if excerpt:
            lines.append(f"第{chunk.page}页/{chunk.chunk_id}：{excerpt}")
    return lines


def _focus_terms(
    question: str,
    domain_focus_terms: tuple[str, ...] = DEFAULT_FOCUS_TERMS,
) -> list[str]:
    terms: list[str] = []
    for term in domain_focus_terms:
        if term in question:
            terms.append(term)

    for date_match in re.findall(r"\d{4}年\d{1,2}月\d{1,2}日", question):
        terms.append(date_match)

    for number_match in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", question):
        terms.append(number_match)

    if not terms:
        compact_question = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", question)
        terms.extend(token for token in compact_question.split() if len(token) >= 2)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def _best_excerpt(text: str, focus_terms: list[str]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return _compact(text, max_length=220)

    if not focus_terms:
        return _compact(" / ".join(lines[:4]), max_length=220)

    best_index = 0
    best_score = -1
    normalized_terms = [_normalize_for_match(term) for term in focus_terms]

    for index, line in enumerate(lines):
        normalized_line = _normalize_for_match(line)
        score = sum(3 for term in normalized_terms if term and term in normalized_line)
        if re.search(r"\d", line):
            score += 1
        if "|" in line:
            score += 1
        if score > best_score:
            best_index = index
            best_score = score

    window_end = min(len(lines), best_index + 4)
    excerpt = " / ".join(lines[best_index:window_end])
    if best_score <= 0:
        excerpt = " / ".join(lines[:4])
    return _compact(excerpt, max_length=220)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text)


def _compact(text: str, max_length: int = 320) -> str:
    compacted = " ".join(text.split())
    if len(compacted) <= max_length:
        return compacted
    return compacted[: max_length - 3] + "..."
