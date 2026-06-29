from docqa.agent.qa_agent import QaAgent
from docqa.llm.client import LlmClient
from docqa.parsing.schema import DocumentChunk
from docqa.retrieval.bm25 import Bm25Retriever


class RefusingLlm(LlmClient):
    provider_name = "refusing-test-llm"

    def generate(self, prompt: str) -> str:
        return "无法确定，因此拒绝回答。"


def test_retriever_finds_clause_evidence() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_clause_5_1",
            text="5.1 键的材料应符合标准要求",
            page=1,
            chunk_type="clause",
            source_file="sample.pdf",
            clause_id="5.1",
        ),
        DocumentChunk(
            chunk_id="page_2_clause_6",
            text="6 检验规则包括抽样和判定",
            page=2,
            chunk_type="clause",
            source_file="sample.pdf",
            clause_id="6",
        ),
    ]

    results = Bm25Retriever(chunks).search("材料 要求")

    assert results[0].chunk.chunk_id == "page_1_clause_5_1"


def test_agent_rejects_no_answer_question() -> None:
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

    answer = QaAgent(Bm25Retriever(chunks)).answer("国外认证要求是什么")

    assert answer.self_check["grounded"] is False
    assert "不能给出确定答案" in answer.answer


def test_agent_rejects_when_evidence_lacks_key_terms() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_paragraph_1",
            text="中信证券股份有限公司 信用损失准备",
            page=1,
            chunk_type="paragraph",
            source_file="sample.pdf",
        )
    ]

    answer = QaAgent(Bm25Retriever(chunks), min_score=0.1).answer("这个标准是否规定了国外认证流程")

    assert answer.self_check["grounded"] is False
    assert "evidence lacks important query terms" in answer.self_check["risk_flags"]


def test_extractive_fallback_combines_table_evidence() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text="| 项目 | 2025年6月30日账面价值 |\n| --- | --- |\n| 合计 | 100 |",
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
            table_id="table_1",
        ),
        DocumentChunk(
            chunk_id="page_2_table_2",
            text="| 项目 | 到期日 |\n| --- | --- |\n| 金融负债 | 3个月内 |",
            page=2,
            chunk_type="table",
            source_file="sample.pdf",
            table_id="table_2",
        ),
    ]

    answer = QaAgent(Bm25Retriever(chunks), min_score=0.01).answer("账面价值是多少？")

    assert answer.generation_provider == "extractive"
    assert "page_1_table_1" in answer.answer
    assert "100" in answer.answer


def test_extractive_fallback_marks_generic_amount_as_ambiguous() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text="| 项目 | 合计 |\n| --- | --- |\n| 金额 | 100 |",
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
            table_id="table_1",
        )
    ]

    answer = QaAgent(Bm25Retriever(chunks), min_score=0.01).answer("金额是多少？")

    assert "金额" in answer.answer
    assert "指向不够具体" in answer.answer


def test_extractive_fallback_extracts_financial_total_book_value() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text=(
                "被投资单位名称\n"
                "2024 年12 月31 日\n"
                "本期增加\n"
                "本期减少\n"
                "2025 年6 月30 日\n"
                "减值准备\n"
                "账面价值\n"
                "合计\n"
                "9,607,514,080.96\n"
                "449,995,947.17\n"
                "270,808,595.80\n"
                "9,786,701,432.33\n"
                "14,965,691.15"
            ),
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
            table_id="table_1",
        )
    ]

    answer = QaAgent(Bm25Retriever(chunks), min_score=0.01).answer("2025年6月30日账面价值是多少？")

    assert answer.self_check["grounded"] is True
    assert "9,786,701,432.33" in answer.answer
    assert "第1页/page_1_table_1" in answer.answer


def test_extractive_fallback_uses_rewritten_ocr_query_for_table_value() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text=(
                "2025 年6 月30 日\n"
                "账面价值\n"
                "合计\n"
                "9,607,514,080.96\n"
                "449,995,947.17\n"
                "270,808,595.80\n"
                "9,786,701,432.33\n"
                "14,965,691.15"
            ),
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
            table_id="table_1",
        )
    ]

    answer = QaAgent(Bm25Retriever(chunks), min_score=0.01).answer("2025年6月30日账面价植是多少？")

    assert answer.query_analysis["rewritten_query"] == "2025年6月30日账面价值是多少"
    assert "9,786,701,432.33" in answer.answer


def test_deterministic_table_value_runs_before_conservative_llm() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_table_1",
            text=(
                "2025 年6 月30 日\n"
                "账面价值\n"
                "合计\n"
                "9,607,514,080.96\n"
                "449,995,947.17\n"
                "270,808,595.80\n"
                "9,786,701,432.33\n"
                "14,965,691.15"
            ),
            page=1,
            chunk_type="table",
            source_file="sample.pdf",
            table_id="table_1",
        )
    ]

    answer = QaAgent(
        Bm25Retriever(chunks),
        min_score=0.01,
        llm_client=RefusingLlm(),
    ).answer("2025年6月30日账面价值是多少？")

    assert answer.generation_provider == "extractive_deterministic"
    assert "9,786,701,432.33" in answer.answer


def test_agent_counts_term_occurrences_across_all_chunks() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="page_1_paragraph_1",
            text="The decoder receives inputs. A decoder layer uses attention.",
            page=1,
            chunk_type="paragraph",
            source_file="sample.pdf",
        ),
        DocumentChunk(
            chunk_id="page_2_paragraph_1",
            text="The encoder is different from the Decoder.",
            page=2,
            chunk_type="paragraph",
            source_file="sample.pdf",
        ),
        DocumentChunk(
            chunk_id="page_3_paragraph_1",
            text="This page mentions attention only.",
            page=3,
            chunk_type="paragraph",
            source_file="sample.pdf",
        ),
    ]

    answer = QaAgent(
        Bm25Retriever(chunks),
        min_score=0.01,
        all_chunks=chunks,
    ).answer("decoder出现了几次？")

    assert answer.generation_provider == "deterministic_count"
    assert answer.query_analysis["intent"] == "count"
    assert "共出现 3 次" in answer.answer
    assert [source["chunk_id"] for source in answer.sources] == [
        "page_1_paragraph_1",
        "page_2_paragraph_1",
    ]
