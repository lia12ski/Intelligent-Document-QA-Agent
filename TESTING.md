# Testing and Evaluation

## 测试目标

本项目测试重点不是只验证代码能运行，还要验证问答结果是否可靠。

核心问题：

- 是否正确识别扫描 PDF。
- 是否能提取正文和条款。
- 是否能提取或近似重建表格。
- 是否能检索到相关页码和片段。
- 是否能在无答案问题上拒答。
- 是否能暴露 OCR 低置信度和证据不足风险。

## 建议测试问题

至少准备 5 个固定问题：

1. 正文问题：询问某项技术要求。
2. 条款问题：询问某编号条款的含义或内容。
3. 表格问题：询问表格中某项目或规格对应要求。
4. 模糊问题：询问标准适用范围或总体要求。
5. 无答案问题：询问文档未覆盖的信息，期望系统拒答。

扩展模板 `gbt-standard` 评估集覆盖：

| 类型 | 示例问题 | 预期行为 |
| --- | --- | --- |
| 正文检索 | 键的适用范围是什么？ | 返回 1.x 条款内容 + 页码 |
| 表格查询 | 普通型平键 b=10 时的公差是多少？ | 从表格 chunk 返回具体数值 |
| 无答案 | 这个标准适用于汽车零部件吗？ | 拒答 + 说明依据不足 |
| 模糊查询 | 公差是什么？ | 返回最相关段落并标注风险，或进入澄清/低置信度路径 |
| OCR 容错 | 硬度耍求 | 尽量召回硬度要求相关 chunk；Dense 接入后应提升召回 |
| 跨条款综合 | 材料和热处理要求分别是什么？ | 多 chunk 合并回答 |

当前真实附件就是中信证券财务报表片段，因此 `financial-sample` 是默认评估集，用来验证同一套链路在财报类表格文档上的表现：

| 类型 | 示例问题 | 预期行为 |
| --- | --- | --- |
| 正文检索 | 财务报表覆盖的期间是什么？ | 返回财务报表期间相关正文 + 页码 |
| 表格查询 | 2025年6月30日账面价值是多少？ | 从表格 chunk 返回包含该日期和账面价值字段的证据 |
| 无答案 | 这个标准是否规定了国外认证流程？ | 拒答 + 说明财报样本中证据不足 |
| 模糊查询 | 金额是多少？ | 标记问题过宽，返回最相关金额/表格证据并提示低置信度，或进入澄清路径 |
| OCR 容错 | 2025年6月30日账面价植是多少？ | “价值/价植”近似错误下仍尽量召回账面价值相关表格 |
| 跨表综合 | 被投资单位名称和金融负债到期日分析分别在哪些表里？ | 同时引用被投资单位名称表和金融负债到期日分析表 |

## 评估指标

```text
retrieval_hit: 检索结果是否包含正确页。
citation_present: 答案是否包含页码和片段。
grounded_answer: 答案是否由证据支持。
correct_rejection: 无答案问题是否拒答。
table_supported: 表格问题是否命中表格 chunk。
multi_chunk_used: 综合问题是否引用多个 chunk。
required_terms_present: 答案或证据中是否包含关键术语。
expected_answer_terms_present: 数值/表格题的最终答案是否包含预期精确值。
```

## 运行方式

先验证索引是否来自目标 PDF：

```bash
python scripts/validate_index.py
```

该命令会检查 `index_manifest.json`、源 PDF 哈希，以及目标关键词（默认 `中信证券`、`财务报表`、`2025 半年度报告`）。

```bash
python scripts/eval.py
```

单元测试：

```bash
python -m pytest tests -q
```

当前本地验证结果：

```text
57 passed
```

预期输出示例：

```text
total: 6
passed: 6
failed: 0
retrieval_hit_rate: 1.0
citation_rate: 1.0
self_check_match_rate: 1.0
```

## 回归风险

- OCR 模型或版本变化导致文本结果变化。
- chunk 大小调整导致检索命中变化。
- embedding 模型变化导致排序变化。
- prompt 调整导致拒答边界变化。

因此评估脚本应固定测试集，并把关键输出写入日志。表格数值题必须配置 `expected_answer_terms`，避免只检索到正确表格、但最终答案没有给出精确数值时被误判为通过。

LLM 生成领域配置时，需要额外检查：

- `domain_config.suggested.env` 是否只包含允许的配置项。
- 关键词是否真实出现在文档片段或典型问题中。
- 替换配置后重新运行 `ingest`、`validate_index`、`eval`，不能只看 LLM 输出。

## 当前样本验证记录

当前本地样本文件是 `agent开发作业样本.pdf`，内容为中信证券财务报表片段。默认评估集应使用 `financial-sample`；`gbt-standard` 仅保留为后续切换标准类文档时的扩展模板。

已验证 MinerU 路径：

```text
parser_provider: mineru
page_count: 6
chunk_count: 22
table_count: 6
```

有效问答样例：

```bash
python scripts/ask.py "被投资单位名称有哪些？"
python scripts/ask.py "2025年6月30日账面价值是多少？"
```

无答案拒答样例：

```bash
python scripts/ask.py "这个标准是否规定了国外认证流程？"
```

该问题会返回 `grounded=false`，风险标记为 `evidence lacks important query terms`。
