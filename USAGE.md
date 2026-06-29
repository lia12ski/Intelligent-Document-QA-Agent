# Usage Guide

本文面向第一次拿到项目的人，说明如何在本地启动前端 Demo、在哪里打开页面，以及如何完成一次文档问答演示。

## 1. 环境准备

在 Windows PowerShell 中进入项目根目录：

```powershell
cd "C:\Users\exten\Documents\New project"
```

如果仓库中已经有 `.venv`，直接使用它：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果是全新机器，先创建虚拟环境：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

可选：复制环境变量模板。

```powershell
copy .env.example .env
```

默认配置可以先跑本地解析和证据片段式问答；如果要启用 MinerU、DeepSeek、OpenAI-compatible 或 Ollama，再按 `.env.example` 填写对应 key 和 provider。

如果演示环境有 MinerU key，建议在 `.env` 中填写：

```env
MINERU_API_KEY=your_key_here
```

Streamlit Demo 检测到 `MINERU_API_KEY` 后，会在页面左侧默认选择 `MinerU (recommended for scanned PDFs)`。这样扫描版 PDF 和复杂版面会优先走 MinerU，避开本地 PaddleOCR 的 Windows 兼容问题。没有 MinerU key 时，页面仍默认使用 `Local`，保证项目可以离线启动。

## 2. 启动前端页面

在项目根目录执行：

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

启动成功后，终端会显示类似：

```text
Local URL: http://localhost:8501
```

用浏览器打开：

```text
http://localhost:8501
```

如果 8501 端口被占用，可以换一个端口：

```powershell
.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

然后打开：

```text
http://localhost:8502
```

## 3. Demo 操作流程

1. 打开前端页面后，在 `PDF 上传` 区域选择一个 PDF。
2. 点击 `Detect PDF`，查看文档类型检测结果：
   - `PDF type`
   - `Pages`
   - `Text pages`
   - `Scanned-like pages`
   - `Strategy`
3. 点击 `Parse & Build Index`，生成解析和检索输入：
   - `pages.json`
   - `chunks.json`
   - `tables.json`
   - `index_manifest.json`
4. 在 `Document QA` 输入问题。
5. 点击 `Ask` 查看回答。
6. 重点检查页面中的：
   - `Answer`
   - `self_check`
   - `query_analysis`
   - `Sources`
   - `page`
   - `chunk_id`
   - `snippet`
7. 如果页面出现 warning，说明 `grounded=false` 或 `risk_flags` 非空，需要人工复核答案。

默认情况下，前端 Demo 的 `执行目标关键词校验（仅财报样本/回归评估需要）` 是关闭的。这样上传合同、简历、报告或其他 PDF 时，不会被财报样本关键词拦截。

## 4. 推荐演示问题

如果使用当前财报样本文档，可以尝试：

```text
财务报表覆盖的期间是什么？
```

```text
2025年6月30日账面价值是多少？
```

```text
金额是多少？
```

```text
这个标准是否规定了国外认证流程？
```

```text
decoder出现了几次？
```

这些问题分别用于展示正文检索、表格数值问答、模糊问题处理、无证据拒答和全局词频计数。

## 5. 页面字段怎么看

- `Answer`：最终回答。回答应来自检索到的文档证据。
- `Sources`：回答依据，包含页码、chunk_id、检索分数和证据片段。
- `self_check.grounded`：是否有足够证据支撑回答。
- `self_check.risk_flags`：潜在风险，例如检索分数过低、证据缺少关键问题词、数值没有在证据中出现。
- `query_analysis.intent`：系统判断问题属于表格、数值、定义或开放问题。
- `query_analysis.rewritten_query`：系统为了容错或聚焦检索而改写后的问题。

## 6. CLI 使用方式

除了前端页面，也可以用命令行跑完整流程。

检测 PDF：

```powershell
.venv\Scripts\python.exe scripts\ingest.py --pdf "data/raw/agent开发作业样本.pdf" --detect-only
```

解析并构建索引：

```powershell
.venv\Scripts\python.exe scripts\ingest.py --pdf "data/raw/agent开发作业样本.pdf"
```

命令行问答：

```powershell
.venv\Scripts\python.exe scripts\ask.py "2025年6月30日账面价值是多少？"
```

运行回归评估：

```powershell
.venv\Scripts\python.exe scripts\eval.py --case-set financial-sample
```

## 7. 常见问题

### 页面打不开

确认 Streamlit 进程仍在运行，并检查终端显示的 `Local URL`。默认地址是：

```text
http://localhost:8501
```

如果端口被占用，使用 `--server.port 8502` 换端口。

### 上传后问答失败

先确认已经点击 `Parse & Build Index`。问答依赖 `data/processed/chunks.json` 和 `data/processed/index_manifest.json`。

### 任意 PDF 上传后目标关键词校验失败

页面左侧有 `执行目标关键词校验（仅财报样本/回归评估需要）` 开关。当前默认关键词面向财报样本；如果上传合同、标准、简历或其他 PDF，请关闭该开关，再问答验证解析和检索链路。

### 回答里出现 BERT(चԭTransformerጱ...) 这类乱码

这通常说明 PDF 自带文本层的编码是坏的。系统检测到文本层后走了 text 解析，但 PyMuPDF 抽出来的文字已经不是正常中文。

前端 `自动检测` 模式会先走 text 解析；如果发现文本层疑似乱码或没有产出 chunks，会自动重试 OCR。

如果仍然无法得到正常文本，可以手动处理：

1. 在页面左侧把 `解析策略` 从 `自动检测` 改成 `强制 OCR`。
2. 重新点击 `Parse & Build Index`。
3. 再重新提问。

如果强制 OCR 仍然效果不好，建议在 `.env` 中切换 `PARSER_PROVIDER=mineru`，用 MinerU 做版面解析。

### PaddleOCR 出现 ConvertPirAttribute2RuntimeAttribute / oneDNN 错误

这是 PaddleOCR / PaddlePaddle 在 Windows CPU 环境下的运行时兼容问题，不是 PDF 问答逻辑错误。项目代码会默认关闭 `FLAGS_enable_pir_api` 和 `FLAGS_enable_pir_in_executor` 来规避该问题。

处理方式：

1. 停掉 Streamlit。
2. 重新启动：

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

3. 再点击 `Parse & Build Index`。

如果仍然失败，可以改用 Tesseract 或 MinerU：

```env
OCR_PROVIDER=tesseract
```

或：

```env
PARSER_PROVIDER=mineru
```

### 外部 LLM 不可用

系统会保留 extractive fallback，仍可基于证据片段回答。查看输出里的 `generation_provider` 和 `generation_error` 可以判断是否发生降级。

### 不要提交哪些文件

不要提交：

- `.env`
- 上传的 PDF
- `data/processed/*`
- `data/index/*`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- IDE 配置和运行截图

这些文件属于本地运行产物或敏感配置，不是项目源码交付内容。
