# Intelligent Document QA Agent

面向扫描版 PDF 的最小可运行智能文档问答 Agent 原型。

本项目用于技术笔试作业：围绕实际附件 `agent开发作业样本.pdf`（中信证券财务报表片段）完成文档类型判断、OCR/文本解析、结构化切分、检索问答、来源引用和答案自检。

## 已实现能力

- PDF 类型检测：判断文本层、扫描件或混合 PDF。
- Parser provider：支持 `local` 和 `mineru` 两种解析入口。
- OCR provider：支持 `paddleocr`、`tesseract`。
- MinerU API：已接入官方批量上传、轮询、下载 zip 的解析流程。
- 标准化输出：生成 `pages.json`、`chunks.json`、`tables.json`。
- 条款识别：支持 `5`、`5.1`、`6.2` 等标准条款编号。
- 表格候选抽取：支持简单规则表格和 MinerU HTML 表格归一化。
- 检索问答：基于 BM25 返回答案、来源页码、片段和自检结果。
- 双路索引架构：BM25 + Dense 已实现，默认 Dense backend 为 FAISS，ChromaDB 作为可选持久化后端保留，RRF 融合已实现。
- Agent 检索决策：query intent、查询改写、一次重试、拒答路径。
- 评估脚本：默认覆盖财报样本上的正文、表格、模糊查询和无答案拒答问题；表格数值题会校验最终答案中的精确值，同时保留 `gbt-standard` 作为扩展模板用例集。

## 项目结构

```text
.
├── README.md
├── DESIGN.md
├── TESTING.md
├── AI_USAGE.md
├── requirements.txt
├── .env.example
├── data/
│   ├── raw/
│   ├── processed/
│   └── index/
├── scripts/
│   ├── ingest.py
│   ├── ask.py
│   └── eval.py
├── src/docqa/
│   ├── agent/
│   ├── evaluation/
│   ├── ocr/
│   ├── parsing/
│   ├── pdf/
│   └── retrieval/
└── tests/
```

## 环境准备

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

默认依赖已包含 FAISS dense 检索所需包。若需要可选的 ChromaDB 持久化后端：

```bash
pip install -r requirements-dense.txt
```

默认 `EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5` 首次运行可能需要从 HuggingFace 下载模型；离线环境建议改为本地模型路径。若 dense 初始化失败且 `DENSE_FAIL_OPEN=true`，系统会降级到 BM25-only，并在 stderr 输出原因。

不要把真实 API Key 提交到仓库。`.env` 已被 `.gitignore` 排除。

## MinerU 配置

在 `.env` 中配置：

```env
PARSER_PROVIDER=mineru
MINERU_BASE_URL=https://mineru.net
MINERU_API_KEY=your_key_here
MINERU_MODEL_VERSION=vlm
```

默认 `PARSER_PROVIDER=local` 可离线运行基础流程；配置 MinerU 后，扫描 PDF 会走 MinerU 官方 API，并把结果统一转换为本项目的 `pages.json`、`chunks.json` 和 `tables.json`。

## 领域配置

当前默认配置面向中信证券财报样本。迁移到合同、合规文档或标准文件时，优先调整 `.env` 中的目标文档关键词、表格识别关键词和证据聚焦词：

```env
TARGET_DOCUMENT_KEYWORDS=中信证券,财务报表,2025 半年度报告
INLINE_TABLE_KEYWORDS=项目,要求,账面价值,被投资单位名称,本期增加,本期减少,合计,金额,到期日,金融负债,即期偿还,减值准备
DOMAIN_FOCUS_TERMS=账面价值,金额,合计,到期日,被投资单位名称,金融负债,财务报表,期间
QUERY_TABLE_TERMS=表格,对应,项目,账面价值,合计,金额,到期日,被投资单位
QUERY_NUMERIC_TERMS=多少,数值,比例,金额,余额
QUERY_OCR_REPLACEMENTS=价植=>价值,价直=>价值,帐面=>账面
```

也可以让 LLM 基于已解析的文档片段生成候选配置：

```bash
python scripts/suggest_domain_config.py --business-scene "财报文档问答" --dry-run-prompt
python scripts/suggest_domain_config.py --business-scene "财报文档问答" --output domain_config.suggested.env
```

该脚本只写 `domain_config.suggested.env`，不会覆盖 `.env`。候选配置需要人工审阅，并重新运行 `scripts/ingest.py`、`scripts/validate_index.py` 和 `scripts/eval.py` 后才能采用。

## 运行流程

1. 放入 PDF：

```text
data/raw/agent开发作业样本.pdf
```

2. 检测 PDF 类型：

```bash
python scripts/ingest.py --pdf "data/raw/agent开发作业样本.pdf" --detect-only
```

输出：

```text
data/processed/pdf_detection.json
```

3. 解析、切分并构建检索输入：

```bash
python scripts/ingest.py --pdf "data/raw/agent开发作业样本.pdf"
```

输出：

```text
data/processed/pages.json
data/processed/chunks.json
data/processed/tables.json
data/processed/index_manifest.json
```

4. 验证索引来源和目标文档身份：

```bash
python scripts/validate_index.py
```

该检查必须通过后再执行问答或评估；默认会检查 `中信证券`、`财务报表`、`2025 半年度报告` 等关键词，确保索引对应当前实际附件样本。

5. 提问：

```bash
python scripts/ask.py "2025年6月30日账面价值是多少？"
```

输出包含：

```text
question
answer
sources[].page
sources[].chunk_id
sources[].snippet
self_check.grounded
self_check.risk_flags
```

6. 运行评估：

```bash
python -m pytest -q
python scripts/eval.py
```

`scripts/eval.py` 默认运行 `financial-sample`。如果显式指定当前财务报表测试样本，也可以运行：

```bash
python scripts/eval.py --case-set financial-sample
```

如果后续切换到 GB/T 标准文档，可运行扩展模板用例集：

```bash
python scripts/eval.py --case-set gbt-standard
```

## 设计取舍

- 不手工录入 PDF 全文，必须通过解析流程产生文本。
- MinerU 作为增强 provider，不作为唯一硬依赖。
- 默认 OCR 为 PaddleOCR，首次运行自动下载模型。Tesseract 作为可选备选。
- 当前样本以编号、日期和表格为主，初版先用 BM25 保证可解释检索。
- 无证据或低置信度证据时，QA Agent 会拒答或标记风险。
- `RETRIEVAL_MIN_SCORE=0.01` 是 RRF/BM25 排序融合分数阈值，不是答案置信度；dense 相似度阈值由 `DENSE_MIN_SCORE=0.4` 单独控制。

## 当前限制

- 表格规则抽取是轻量实现，复杂合并单元格依赖 MinerU 或后续版面模型增强。
- QA 已支持 DeepSeek / OpenAI-compatible / Ollama provider；当外部 LLM 不可用时会回退为证据片段式回答，并在 `generation_provider` / `generation_error` 中标明。
- 当前评估集是工程回归测试，已覆盖财报样本的精确数值校验；后续应补充更多人工标注页码和标准答案。
