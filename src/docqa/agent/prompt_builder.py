from __future__ import annotations

import re

from docqa.retrieval.bm25 import RetrievalResult


def _strip_original_page_numbers(text: str) -> str:
    return re.sub(r"第\s*\d+\s*页", "", text)


GROUNDING_PROMPT_TEMPLATE = """你是一个严谨的文档问答 Agent。

要求：
1. 只能基于 context 回答，不能使用外部常识补充。
2. 引用来源时使用 [page=X] 格式（X 取自 context 前缀中的 page=），不要使用"第X页"这类文字。如果有条款号，也必须引用条款号。
3. 如果 context 不足以回答，必须拒答。
4. 数字、日期、金额必须与 context 原文一致。
5. 表格问题优先读取表头和合计行；如果 context 已给出合计行对应数值，直接回答该数值，不要因为表格被 OCR 拆行而拒答。
6. 回答中必须保留原始数值格式，并标注来源页码和 chunk。

question:
{question}

context:
{context}
"""


def build_grounding_prompt(question: str, results: list[RetrievalResult]) -> str:
    context = "\n\n".join(
        f"[page={result.chunk.page}, clause={result.chunk.clause_id or '-'}, "
        f"type={result.chunk.chunk_type}]\n{_strip_original_page_numbers(result.chunk.text)}"
        for result in results
    )
    return GROUNDING_PROMPT_TEMPLATE.format(question=question, context=context)
