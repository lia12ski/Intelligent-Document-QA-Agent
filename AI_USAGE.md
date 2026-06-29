# AI Usage Record

本项目允许并鼓励使用 AI/Agent 工具，但所有输出需要人工理解、校验和修正。

## 使用的 AI 工具

- **Claude Code（Anthropic）**：作为主要开发助手，用于代码审查、Bug 定位与修复、代码重构、测试验证和文档更新。

## 具体使用场景

1. **项目骨架搭建**：辅助生成初始模块结构和接口定义。
2. **代码审查与 Bug 修复**：用 Claude Code 扫描代码库，定位潜在 Bug（如 `str.format()` 误判、BM25 默认阈值过高、query intent 误分类），逐项验证后做最小修复，并通过全量测试确认无回归。
3. **测试覆盖增强**：辅助编写测试用例，覆盖边界情况（条款号识别、OCR 错字改写、RRF 去重等）。
4. **重构**：删除 Mock OCR provider，统一默认 `paddleocr`，清理分散在三处的 mock 特判代码。
5. **文档维护**：同步更新 README、DESIGN.md、DEMO.md，保持与实际代码一致。

## AI 输出的校验方式

- 不接受无法解释的代码。每个 AI 生成的修改必须经过人工理解。
- 所有 Bug 修复先写脚本验证问题确实存在，再修改代码，最后跑全量测试确认。
- 问答结果必须检查来源页码和证据片段，不能只看最终答案。
- 对无答案问题必须验证系统是否拒答，而不是编造内容。
- 评估结果作为回归依据，每次修改后至少跑一遍 `scripts/eval.py`。

## 人工负责部分

- 最终架构取舍（分层设计、Provider 模式、自检独立于 prompt）。
- OCR 结果和表格解析质量判断。
- 测试用例设计（哪些场景要覆盖、如何判定通过/失败）。
- API Key 等敏感信息保护。
- README、设计说明和演示材料的最终审核。
- 决定哪些 AI 建议采纳、哪些拒绝。

## 禁止事项

- 不手工录入 PDF 全文绕过解析流程。
- 不硬编码演示问题答案。
- 不提交 API Key、账号密码或其他敏感信息。
- 不接受无法解释的 AI 生成代码。

## 使用统计

本项目开发过程中，AI 辅助的主要产出包括：

- 代码行数：约 3000+ 行 Python（含测试）
- Bug 发现与修复：6 处（min_score 默认值、query intent 误分类、embedding 默认模型、`generation_provider` 误导、`answer_min_score` 死字段、`None` chunk_id 计数）
- 重构：移除 Mock OCR Provider（~100 行代码 + 相关测试）
- 测试：55 个测试用例，覆盖所有核心模块
## Codex 使用记录

- **OpenAI Codex**：作为后续代码检测和发布前检查助手，参与仓库状态检查、版本控制清理、测试执行、样本评估验证和推送前风险排查。
- 本轮 Codex 执行并确认：`pytest` 55 项通过、`compileall` 通过、`scripts/validate_index.py` 通过、`scripts/eval.py --case-set financial-sample` 6/6 通过，并完成一次 `scripts/ask.py` 问答烟测。
- 本轮 Codex 发现并处理的提交前问题包括：将 `.idea/` 加入 `.gitignore`，删除误生成的 `1.8.0` 文件，确认 `.env`、缓存目录、原始数据和处理产物不会被误提交。
- Codex 输出仍需人工最终确认，尤其是是否公开提交样本 PDF、运行截图，以及绑定哪个 GitHub 远程仓库。

## AI Native Workflow 补充

为了贴近真实 AI Native 开发流程，本项目将 AI 工具使用方式进一步显式化：

- 使用 Product Agent 思维拆解 MVP 范围。
- 使用 Architect Agent 思维约束模块边界和数据契约。
- 使用 Coding Agent 辅助实现 Streamlit Demo 和功能胶水代码。
- 使用 Test Agent 检查现有 pytest 和 eval 是否受影响。
- 使用 Reviewer Agent 检查是否存在硬编码答案、未处理异常和敏感信息提交风险。
- 使用 Ops Agent 检查 README、依赖、`.env.example` 和运行说明是否一致。

所有 AI 生成内容仍需人工审查，不能直接视为可信结果；不接受无法解释的代码，也不能绕过来源引用和 self_check 直接展示最终答案。
