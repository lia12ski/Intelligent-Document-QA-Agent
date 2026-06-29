# Agent Workflow

## 1. 为什么采用 AI Agent 协作开发

本项目不是让 AI 一次性生成完整系统，而是把智能文档问答拆成可审查、可测试、可替换的任务边界。人工负责确定业务目标、架构约束和验收标准，AI Agent 负责在明确边界内辅助产出候选实现、测试和文档。

这种方式适合当前仓库：PDF detection、parser provider、OCR provider、retrieval provider、QaAgent、self_check 和 eval 都是独立模块，可以分别交给不同 Agent 处理，再由人工统一审查输入输出契约。

## 2. Agent 角色设计

### Product Agent

负责把目标拆成 MVP 范围：上传 PDF、识别文档类型、解析为 pages/chunks/tables、检索问答、展示引用来源、展示 self_check 和风险标记。它还负责把面试 JD 中的高保真原型、快速 MVP、业务指标和 A/B 测试要求转化为仓库文档。

### Architect Agent

负责维护 0-6 层架构边界：PDF detection 只判断类型和推荐策略，parser provider 负责本地解析或 MinerU 解析，OCR provider 负责扫描页识别，retrieval provider 负责 BM25/Dense/RRF，QaAgent 负责查询分析、检索、生成、拒答和自检。

### Coding Agent

负责在既有模块上写胶水代码，例如 Streamlit `app.py` 只复用 `detect_pdf()`、`create_parser()`、`build_chunks()`、`build_manifest()`、`load_chunks()`、`build_retriever()` 和 `QaAgent`，不重写解析、检索和问答逻辑。

### Test Agent

负责生成和维护 pytest、compileall、eval 回归路径。当前项目的关键检查包括 `python -m pytest tests -q`、`python -m compileall src scripts app.py` 和 `python scripts/eval.py --case-set financial-sample`。

### Reviewer Agent

负责审查硬编码答案、异常处理、敏感信息泄露、运行产物误提交和幻觉风险。重点检查 `answer.sources`、`self_check.grounded`、`risk_flags`、`query_analysis` 是否被展示和用于拒答。

### Ops Agent

负责依赖、`.env.example`、README、运行说明、`.gitignore` 和提交前检查。它要确认 `.env`、上传 PDF、`data/processed`、`data/index`、缓存目录和 IDE 文件不会被提交。

## 3. 人类负责的决策

- 最终架构取舍和 Provider 边界。
- 是否启用 MinerU、PaddleOCR、Tesseract、Dense retrieval 或外部 LLM。
- 是否采纳 AI 生成代码和文档。
- 测试通过标准和 eval case 设计。
- 无证据问题是否拒答，以及是否允许 extractive fallback。
- 是否公开样本 PDF、运行截图和评估结果。
- 是否提交运行产物。

## 4. 协作流程

需求拆解 -> 架构设计 -> 模块实现 -> 单元测试 -> 集成测试 -> 文档同步 -> 发布前检查。

在本仓库中，对应流程是：先用 Product Agent 明确财报/合同/合规材料场景，再由 Architect Agent 锁定 provider 和数据契约；Coding Agent 实现 parsing、retrieval、agent、evaluation 或 Streamlit 胶水；Test Agent 跑 pytest 和 eval；Reviewer Agent 检查来源引用、自检和拒答；Ops Agent 确认依赖、运行命令和提交范围。

## 5. 风险控制

- 不接受无法解释的代码。
- 不硬编码样本答案。
- 不绕过 PDF 解析流程手工录入全文。
- 不提交 API Key、上传 PDF、处理产物或缓存文件。
- 修改后必须运行 pytest 和 compileall。
- 问答结果必须检查来源页码、chunk_id、snippet 和 self_check。
- `grounded=false` 或 `risk_flags` 非空时必须明确提示人工复核。
