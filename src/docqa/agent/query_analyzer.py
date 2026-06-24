from __future__ import annotations

from dataclasses import dataclass
import re


_TABLE_TERMS = (
    "表格",
    "对应",
    "项目",
    "账面价值",
    "合计",
    "金额",
    "到期日",
    "被投资单位",
)
_NUMERIC_TERMS = ("多少", "数值", "比例", "金额", "余额")
_DEFINITION_TERMS = ("是什么", "定义", "含义", "指什么", "期间")
_GENERIC_PHRASES = ("这个标准", "这个", "标准", "请问", "文档中", "文档里", "是否", "规定了")
_OCR_REPLACEMENTS = (
    ("价植", "价值"),
    ("价直", "价值"),
    ("帐面", "账面"),
    ("帐戸", "账户"),
    ("賬面", "账面"),
    ("金額", "金额"),
    ("負债", "负债"),
    ("财務", "财务"),
)


@dataclass(frozen=True)
class QueryAnalysis:
    intent: str
    rewritten_query: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "intent": self.intent,
            "rewritten_query": self.rewritten_query,
        }


@dataclass(frozen=True)
class QueryAnalyzerConfig:
    table_terms: tuple[str, ...] = _TABLE_TERMS
    numeric_terms: tuple[str, ...] = _NUMERIC_TERMS
    definition_terms: tuple[str, ...] = _DEFINITION_TERMS
    generic_phrases: tuple[str, ...] = _GENERIC_PHRASES
    ocr_replacements: tuple[tuple[str, str], ...] = _OCR_REPLACEMENTS
    generic_amount_expansion: str = "金额 合计 账面价值 金融负债"


def analyze_query(
    question: str,
    config: QueryAnalyzerConfig | None = None,
) -> QueryAnalysis:
    config = config or QueryAnalyzerConfig()
    normalized_question = _apply_ocr_replacements(question, config.ocr_replacements)
    rewritten = rewrite_query(normalized_question, config)

    if _is_table_query(normalized_question, config.table_terms):
        intent = "table"
    elif _is_numeric_query(normalized_question, config.numeric_terms):
        intent = "numeric"
    elif _is_definition_query(normalized_question, config.definition_terms):
        intent = "definition"
    else:
        intent = "open"

    return QueryAnalysis(
        intent=intent,
        rewritten_query=rewritten if rewritten != normalized_question else None,
    )


def rewrite_query(
    question: str,
    config: QueryAnalyzerConfig | None = None,
) -> str:
    config = config or QueryAnalyzerConfig()
    rewritten = _apply_ocr_replacements(question, config.ocr_replacements).strip()

    if re.fullmatch(r"金额是?多少[？?]?", rewritten):
        return config.generic_amount_expansion

    for phrase in config.generic_phrases:
        rewritten = rewritten.replace(phrase, " ")

    rewritten = re.sub(r"\s+", " ", rewritten).strip(" ？?。；;，,：:")
    return rewritten or question.strip()


def _is_table_query(question: str, table_terms: tuple[str, ...]) -> bool:
    return any(word in question for word in table_terms)


def _is_numeric_query(question: str, numeric_terms: tuple[str, ...]) -> bool:
    clause_stripped = re.sub(r"\d+\.\d+", "", question)
    return bool(re.search(r"\d", clause_stripped)) or any(word in question for word in numeric_terms)


def _is_definition_query(question: str, definition_terms: tuple[str, ...]) -> bool:
    return any(word in question for word in definition_terms)


def _apply_ocr_replacements(
    question: str,
    replacements: tuple[tuple[str, str], ...],
) -> str:
    normalized = question
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    return normalized
