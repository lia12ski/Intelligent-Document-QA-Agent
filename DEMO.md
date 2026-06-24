# Demo Walkthrough

本文件用于提交材料中的“清晰截图/演示脚本”。当前实际附件为 `agent开发作业样本.pdf`，内容是中信证券 2025 半年度财务报表片段。

## 1. 启动与环境

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

将样本放到：

```text
data/raw/agent开发作业样本.pdf
```

## 2. PDF 类型判断

```bash
python scripts/ingest.py --pdf "data/raw/agent开发作业样本.pdf" --detect-only
```

当前样本检测结论：

```text
pdf_type: text
recommended_strategy: text
reason: 5/6 pages contain usable text layer
```

说明：作业描述原本强调扫描 PDF，但本次实际附件是带文本层的财报样本。代码仍保留并测试了 scanned/mixed PDF 的 OCR 路径：当 `recommended_strategy=ocr` 时，`LocalPdfParser` 会渲染页面并调用 OCR provider。

## 3. 解析与索引

```bash
python scripts/ingest.py --pdf "data/raw/agent开发作业样本.pdf"
python scripts/validate_index.py
```

当前解析结果：

```text
source_file: data/raw/agent开发作业样本.pdf
parser_provider: local
strategy: text
page_count: 6
chunk_count: 16
table_count: 8
target keywords: 中信证券, 财务报表, 2025 半年度报告
```

主要产物：

```text
data/processed/pdf_detection.json
data/processed/pages.json
data/processed/chunks.json
data/processed/tables.json
data/processed/index_manifest.json
```

## 4. 问答示例

### 正文检索

```bash
python scripts/ask.py "财务报表覆盖的期间是什么？"
```

预期行为：返回“2025 年 1 月 1 日至 6 月 30 日止期间财务报表”等证据，并包含页码和 chunk。

### 表格查询

```bash
python scripts/ask.py "2025年6月30日账面价值是多少？"
```

当前输出要点：

```text
answer: 合计行中，2025年6月30日账面价值为 9,786,701,432.33。来源：第1页/page_1_table_1。
self_check.grounded: true
```

### OCR 容错

```bash
python scripts/ask.py "2025年6月30日账面价植是多少？"
```

当前输出要点：

```text
query_analysis.rewritten_query: 2025年6月30日账面价值是多少
answer: 合计行中，2025年6月30日账面价值为 9,786,701,432.33。来源：第1页/page_1_table_1。
```

### 模糊查询

```bash
python scripts/ask.py "金额是多少？"
```

预期行为：不直接编造一个金额，而是说明“金额”指向不够具体，并返回最相关金额/表格证据。

### 无答案拒答

```bash
python scripts/ask.py "这个标准是否规定了国外认证流程？"
```

当前输出要点：

```text
answer: 文档中未检索到足够可靠的依据，因此不能给出确定答案。
self_check.grounded: false
risk_flags: evidence lacks important query terms
```

### 跨表综合

```bash
python scripts/ask.py "被投资单位名称和金融负债到期日分析分别在哪些表里？"
```

预期行为：同时引用被投资单位名称表和金融负债到期日分析表，至少包含两个来源 chunk。

## 5. 自动评估

```bash
python -m pytest -q
python scripts/eval.py --case-set financial-sample
```

当前验证结果：

```text
pytest: 55 passed
eval total: 6
eval passed: 6
eval failed: 0
retrieval_hit_rate: 1.0
citation_rate: 1.0
self_check_match_rate: 1.0
```

评估额外检查 `expected_answer_terms_present`：表格数值题必须在最终答案中包含精确值 `9,786,701,432.33`，避免“只命中表格但没有答出数值”的假阳性。

## 6. 迁移说明

迁移到合同、合规、标准文件时，优先修改 `.env`：

```env
TARGET_DOCUMENT_KEYWORDS=...
INLINE_TABLE_KEYWORDS=...
DOMAIN_FOCUS_TERMS=...
QUERY_TABLE_TERMS=...
QUERY_NUMERIC_TERMS=...
QUERY_OCR_REPLACEMENTS=...
```

对于复杂扫描 PDF 或合并单元格表格，建议切换：

```env
PARSER_PROVIDER=mineru
OCR_PROVIDER=paddleocr
```

也可以先让 LLM 生成候选配置：

```bash
python scripts/suggest_domain_config.py --business-scene "合同审查问答" --dry-run-prompt
python scripts/suggest_domain_config.py --business-scene "合同审查问答" --output domain_config.suggested.env
```

注意：该脚本不会覆盖 `.env`。候选配置必须人工审阅，并通过评估脚本验证后再采用。

## 7. 截图指引（提交材料用）

以下节点建议截图，覆盖题目要求的全部内容：

| # | 命令 | 截图要点 |
|---|------|----------|
| 1 | `python scripts/ingest.py --pdf "data/raw/agent开发作业样本.pdf" --detect-only` | PDF 类型（text/scanned）、页数、推荐策略 |
| 2 | `python scripts/ingest.py --pdf "data/raw/agent开发作业样本.pdf"` | page_count、chunk_count、table_count |
| 3 | `python scripts/ask.py "2025年6月30日账面价值是多少？"` | 答案中的数值 `9,786,701,432.33`、来源页码、`grounded: true` |
| 4 | `python scripts/ask.py "这个标准是否规定了国外认证流程？"` | 拒答、`grounded: false`、`risk_flags` |
| 5 | `python scripts/ask.py "金额是多少？"` | 模糊查询路径，包含"指向不够具体"说明 |
| 6 | `python scripts/ask.py "2025年6月30日账面价植是多少？"` | `rewritten_query` 中的 OCR 修正、"账面价值" |
| 7 | `python scripts/ask.py "被投资单位名称和金融负债到期日分析分别在哪些表里？"` | 跨表综合，至少两个来源 chunk |
| 8 | `python -m pytest -q` | 全部通过（55 passed） |
| 9 | `python scripts/eval.py --case-set financial-sample` | total/passed/failed、各项 rate |
| 10 | `type data\processed\pdf_detection.json \| python -m json.tool` | PDF 检测完整结果（可选，展示解析细节）
