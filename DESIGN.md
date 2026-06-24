# Design Notes

## 目标架构

本项目按 0-6 层实现智能文档问答 Agent。目标不是简单聊天，而是能处理扫描 PDF、表格、条款编号、无答案问题和可靠性自检。

```text
扫描 PDF
   |
   v
[Layer 0] PDF 类型判断
  PyMuPDF/pdfminer/pdfplumber 试提取 -> 文本层质量评分
  低于阈值 -> 扫描件路径 OCR
  高于阈值 -> 数字原生路径直接提取
   |
   v
[Layer 1] 文档解析
  Parser provider: local | mineru
  正文: MinerU / PaddleOCR / Tesseract
  表格: MinerU / table_transformer / img2table + PaddleOCR
  输出: {page, clause_number, content_type, bbox, confidence}
   |
   v
[Layer 2] 结构感知切块
  条款号边界: 3.1 / 4.2.3
  表格作为原子块: markdown 或 key-value
  chunk metadata: page, clause, section_title, chunk_type
  领域表格关键词通过 INLINE_TABLE_KEYWORDS 配置
   |
   v
[Layer 3] 双路索引
  Dense: embedding model -> FAISS by default, optional ChromaDB
  Sparse: BM25
  Fusion: RRF
   |
   v
[Layer 4] Agent 检索决策
  query intent: definition / numeric / table / open
  query terms / OCR replacements 通过环境配置
  初次检索不足 -> 查询改写重试一次
  仍不足 -> 拒答
   |
   v
[Layer 5] 生成 + 来源标注
  Prompt 约束: 只从 context 回答
  必须引用 page / clause
   |
   v
[Layer 6] 自检模块
  dense similarity < 0.4 -> 拒答
  答案数字必须出现在 evidence
  出现“可能/通常”等推测词 -> low confidence
  评估层对数值题检查 expected_answer_terms
```

## 当前实现状态

| Layer | 状态 | 说明 |
| --- | --- | --- |
| Layer 0 | 已实现 | `PdfDetectionResult` 输出页数、文本密度、图片数、推荐策略。 |
| Layer 1 | 已实现 | `local` 和 `mineru` provider；MinerU 已完成上传、轮询、下载和结果归一化。 |
| Layer 2 | 已实现 | 条款 chunk、paragraph chunk、table chunk；表格作为原子块；chunk 带 page/clause/section_title/chunk_type；表格关键词可配置。 |
| Layer 3 | 已实现 | BM25 已实现；Dense 默认使用本地 BGE + FAISS；ChromaDB 可作为可选持久化后端；RRF hybrid 已实现。 |
| Layer 4 | 已实现 | query intent 分类、查询改写、一次重试和拒答路径；query 术语、泛化短语、OCR 替换表可配置。 |
| Layer 5 | 已实现 | 已有 context-only prompt builder、来源字段和 LLM provider；支持 DeepSeek / OpenAI-compatible / Ollama，失败时回退证据片段回答。 |
| Layer 6 | 已实现 | 独立 self-check：检索分数、dense 分数、关键短语覆盖、数字一致性、推测词风险；评估层额外校验精确答案项。 |

## Provider 设计

### Parser Provider

`PARSER_PROVIDER=local | mineru`

- `local`: 文本层 PDF 直接提取；扫描件渲染页面后交给 OCR provider。
- `mineru`: 调用 MinerU API，下载 zip，读取 `full.md` 和 `*_content_list.json`，标准化为 `pages.json`。

### OCR Provider

`OCR_PROVIDER=paddleocr | tesseract`

- `mock`: 仅用于无依赖环境下验证流程。
- `paddleocr`: 中文扫描件优先方案。
- `tesseract`: 轻量 fallback。

### Retrieval Provider

- Sparse: `Bm25Retriever`
- Dense: `FaissDenseRetriever` by default; `InMemoryDenseRetriever` and `ChromaDenseRetriever` are optional backends.
- Fusion: `RrfHybridRetriever`

默认依赖包含 FAISS dense 路径；`requirements-dense.txt` 仅用于安装可选 ChromaDB 后端。

### Domain Config Suggestion

`scripts/suggest_domain_config.py` 使用当前 LLM provider 读取 `chunks.json` 抽样片段和评估问题，生成 `TARGET_DOCUMENT_KEYWORDS`、`INLINE_TABLE_KEYWORDS`、`DOMAIN_FOCUS_TERMS`、`QUERY_*` 等候选配置。

设计约束：

- 只生成 `domain_config.suggested.env`，不自动覆盖 `.env`。
- 支持 `--dry-run-prompt`，可在无 API Key 环境中审查提示词。
- LLM 输出只作为候选，必须通过 `ingest + validate_index + eval` 验证后采用。
- 业务迁移时保留默认配置作为 fallback，避免 LLM 生成过宽泛或文档中不存在的词导致召回下降。

## 输出契约

解析阶段输出：

```text
data/processed/pdf_detection.json
data/processed/pages.json
data/processed/chunks.json
data/processed/tables.json
```

问答输出：

```json
{
  "question": "...",
  "answer": "...",
  "sources": [
    {
      "page": 1,
      "chunk_id": "page_1_table_1",
      "chunk_type": "table",
      "clause_id": null,
      "section_title": "table",
      "score": 0.0164,
      "retrieval_source": "rrf:bm25",
      "snippet": "..."
    }
  ],
  "self_check": {
    "grounded": true,
    "confidence": "medium",
    "risk_flags": []
  },
  "query_analysis": {
    "intent": "table",
    "rewritten_query": null
  }
}
```

## 关键取舍

- MinerU 可作为高质量解析路径，但系统不绑定 MinerU，仍保留 local provider。
- 表格作为原子 chunk，避免普通段落切分破坏表格结构。
- 标准文件、财报、合同都有编号和数值，BM25 必须保留。
- Dense 检索通过 provider 接口隔离，便于替换 BGE、OpenAI embedding 或私有 embedding 服务。
- 自检独立于 prompt，避免只靠 LLM 自我声明。
- 财报样本的 `INLINE_TABLE_KEYWORDS`、`DOMAIN_FOCUS_TERMS`、`QUERY_TABLE_TERMS`、`QUERY_NUMERIC_TERMS` 和 `QUERY_OCR_REPLACEMENTS` 放在环境配置中，迁移到合同、合规、标准文件时优先替换词表，而不是修改核心流程。
- 当前本地表格数值抽取是面向演示样本的轻量规则；高保真单元格恢复仍建议使用 MinerU 或专门版面模型。

## 后续增强

- 如需多文档长期服务，可接入持久化 ChromaDB、LanceDB 或 sqlite-vec。
- 增强 LLM 输出校验，例如对引用页码、条款号和表格数值做更严格的结构化校验。
- 为表格 QA 增加行列定位和 key-value 查询。
- 为标准文件补充人工标注评估集：期望页码、条款号、标准答案。
