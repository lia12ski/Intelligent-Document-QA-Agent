from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    question: str
    expected_behavior: str
    case_type: str = "general"
    expected_mode: str = "answer"
    expected_chunk_type: str | None = None
    expected_clause_prefix: str | None = None
    required_terms: list[str] = field(default_factory=list)
    expected_answer_terms: list[str] = field(default_factory=list)
    min_sources: int = 1
    requires_citation: bool = True

    @property
    def expected_reject(self) -> bool:
        return self.expected_mode == "reject"


GBT_STANDARD_CASES = [
    EvaluationCase(
        case_id="scope",
        case_type="正文检索",
        question="键的适用范围是什么？",
        expected_behavior="返回 1.x 范围条款内容，并带页码/条款来源。",
        expected_mode="answer",
        expected_chunk_type="clause",
        expected_clause_prefix="1",
        required_terms=["适用", "范围"],
    ),
    EvaluationCase(
        case_id="parallel_key_b10_tolerance",
        case_type="表格查询",
        question="普通型平键 b=10 时的公差是多少？",
        expected_behavior="从表格 chunk 返回 b=10 对应的具体公差数值。",
        expected_mode="answer",
        expected_chunk_type="table",
        required_terms=["普通型", "平键", "b=10", "公差"],
    ),
    EvaluationCase(
        case_id="unsupported_auto_parts",
        case_type="无答案",
        question="这个标准适用于汽车零部件吗？",
        expected_behavior="拒答，并说明检索证据不足。",
        expected_mode="reject",
        requires_citation=False,
    ),
    EvaluationCase(
        case_id="ambiguous_tolerance",
        case_type="模糊查询",
        question="公差是什么？",
        expected_behavior="可返回最相关段落并标注风险，或进入澄清/低置信度路径。",
        expected_mode="clarify_or_answer",
        required_terms=["公差"],
    ),
    EvaluationCase(
        case_id="ocr_tolerance_hardness",
        case_type="OCR 容错",
        question="硬度耍求",
        expected_behavior="OCR 错字下仍尽量召回硬度要求相关 chunk；Dense 接入后应提升召回。",
        expected_mode="answer",
        required_terms=["硬度"],
    ),
    EvaluationCase(
        case_id="material_and_heat_treatment",
        case_type="跨条款综合",
        question="材料和热处理要求分别是什么？",
        expected_behavior="多 chunk 合并回答材料要求和热处理要求。",
        expected_mode="multi_chunk_answer",
        expected_chunk_type="clause",
        required_terms=["材料", "热处理"],
        min_sources=2,
    ),
]


FINANCIAL_SAMPLE_CASES = [
    EvaluationCase(
        case_id="financial_statement_period",
        case_type="正文检索",
        question="财务报表覆盖的期间是什么？",
        expected_behavior="返回财务报表期间相关正文，并带页码来源。",
        expected_mode="answer",
        required_terms=["财务报表", "期间"],
    ),
    EvaluationCase(
        case_id="book_value_2025",
        case_type="表格查询",
        question="2025年6月30日账面价值是多少？",
        expected_behavior="命中包含 2025 年 6 月 30 日账面价值列的表格。",
        expected_mode="answer",
        expected_chunk_type="table",
        required_terms=["2025", "账面价值"],
        expected_answer_terms=["9,786,701,432.33"],
    ),
    EvaluationCase(
        case_id="no_answer_certification",
        case_type="无答案",
        question="这个标准是否规定了国外认证流程？",
        expected_behavior="拒答，并说明证据不足。",
        expected_mode="reject",
        requires_citation=False,
    ),
    EvaluationCase(
        case_id="ambiguous_amount",
        case_type="模糊查询",
        question="金额是多少？",
        expected_behavior="问题较模糊，可返回最相关金额/表格证据并标注风险，或进入低置信度路径。",
        expected_mode="clarify_or_answer",
        required_terms=["金额"],
    ),
    EvaluationCase(
        case_id="ocr_tolerance_book_value",
        case_type="OCR 容错",
        question="2025年6月30日账面价植是多少？",
        expected_behavior="账面价值出现近似 OCR 错字时，仍尽量召回账面价值相关表格。",
        expected_mode="answer",
        expected_chunk_type="table",
        required_terms=["2025", "账面"],
        expected_answer_terms=["9,786,701,432.33"],
    ),
    EvaluationCase(
        case_id="investee_and_liability_summary",
        case_type="跨表综合",
        question="被投资单位名称和金融负债到期日分析分别在哪些表里？",
        expected_behavior="同时引用被投资单位名称表和金融负债到期日分析表。",
        expected_mode="multi_chunk_answer",
        required_terms=["被投资", "金融负债"],
        min_sources=2,
    ),
]


DEFAULT_CASES = FINANCIAL_SAMPLE_CASES
