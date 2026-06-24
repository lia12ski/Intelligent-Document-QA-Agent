from docqa.agent.qa_agent import QaAgent
from docqa.evaluation.cases import EvaluationCase
from docqa.evaluation.runner import run_evaluation
from docqa.parsing.schema import DocumentChunk
from docqa.retrieval.bm25 import Bm25Retriever


def test_evaluation_runner_outputs_metrics() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_clause_5_1",
            text="5.1 键的材料应符合标准要求",
            page=1,
            chunk_type="clause",
            source_file="sample.pdf",
            clause_id="5.1",
        )
    ]
    cases = [
        EvaluationCase(
            case_id="material",
            case_type="正文检索",
            question="材料要求是什么",
            expected_behavior="retrieve material clause",
            expected_chunk_type="clause",
            required_terms=["材料"],
        )
    ]

    report = run_evaluation(QaAgent(Bm25Retriever(chunks)), cases)
    data = report.to_dict()

    assert report.total == 1
    assert report.passed == 1
    assert data["retrieval_hit_rate"] == 1.0
    assert data["citation_rate"] == 1.0
    assert data["items"][0]["metrics"]["retrieval_hit"] is True


def test_evaluation_runner_accepts_correct_rejection() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text="被投资单位名称",
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
        )
    ]
    cases = [
        EvaluationCase(
            case_id="reject",
            case_type="无答案",
            question="这个标准是否规定了国外认证流程？",
            expected_behavior="reject unsupported question",
            expected_mode="reject",
            requires_citation=False,
        )
    ]

    report = run_evaluation(QaAgent(Bm25Retriever(chunks)), cases)

    assert report.total == 1
    assert report.passed == 1
    assert report.items[0].metrics.correct_rejection is True


def test_clarify_or_answer_requires_retrieval_hit() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text="项目 | 合计 | 100",
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
        )
    ]
    cases = [
        EvaluationCase(
            case_id="ambiguous",
            case_type="模糊查询",
            question="金额是多少？",
            expected_behavior="should not pass without expected retrieval terms",
            expected_mode="clarify_or_answer",
            required_terms=["不存在的字段"],
        )
    ]

    report = run_evaluation(QaAgent(Bm25Retriever(chunks), min_score=0.01), cases)

    assert report.passed == 0
    assert report.items[0].metrics.retrieval_hit is False


def test_clarify_or_answer_can_pass_when_answer_supplies_generic_term() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text="| 项目 | 合计 |\n| --- | --- |\n| 金额 | 100 |\n| 账面价值 | 100 |",
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
        )
    ]
    cases = [
        EvaluationCase(
            case_id="amount",
            case_type="模糊查询",
            question="金额是多少？",
            expected_behavior="allow generic amount answers when grounded",
            expected_mode="clarify_or_answer",
            required_terms=["金额"],
        )
    ]

    report = run_evaluation(QaAgent(Bm25Retriever(chunks), min_score=0.01), cases)

    assert report.passed == 1
    assert report.items[0].metrics.retrieval_hit is True


def test_table_numeric_case_requires_exact_answer_term() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text="| 项目 | 2025年6月30日账面价值 |\n| --- | --- |\n| 合计 | 100 |",
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
        )
    ]
    cases = [
        EvaluationCase(
            case_id="book_value",
            case_type="表格查询",
            question="2025年6月30日账面价值是多少？",
            expected_behavior="final answer must include the exact numeric value",
            expected_chunk_type="table",
            required_terms=["2025", "账面价值"],
            expected_answer_terms=["9,786,701,432.33"],
        )
    ]

    report = run_evaluation(QaAgent(Bm25Retriever(chunks), min_score=0.01), cases)

    assert report.passed == 0
    assert report.items[0].metrics.expected_answer_terms_present is False
    assert "expected answer terms missing from final answer" in report.items[0].notes
