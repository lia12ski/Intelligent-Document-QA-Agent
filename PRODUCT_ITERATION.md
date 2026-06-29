# Product Iteration Plan

## 1. 目标用户

需要处理扫描 PDF、财报、合同、标准文件和合规材料的业务人员。他们通常不关心底层 OCR 或检索算法，只关心能否快速得到有来源、可复核、低幻觉风险的答案。

## 2. 用户痛点

- 扫描 PDF 无法直接复制和搜索。
- 表格信息难以检索，尤其是跨页表格和财报数值。
- 大模型容易编造答案。
- 答案缺少页码、chunk_id 和证据片段。
- 无答案问题容易被误答。
- 文档迁移到合同、合规或标准文件时，需要重新调整关键词、解析策略和评估集。

## 3. MVP 范围

当前 MVP 覆盖：

- PDF 上传。
- PDF 类型检测。
- OCR / MinerU / local parser 解析。
- `pages.json`、`chunks.json`、`tables.json` 标准化输出。
- 结构化切块和表格候选块。
- BM25 + Dense + RRF 检索架构。
- QaAgent 问答生成。
- 来源引用，包括 page、chunk_id、snippet。
- self_check、risk_flags 和拒答路径。
- `financial-sample` 评估回归。
- Streamlit 可交互 Demo。

## 4. 产品指标

### 技术可靠性指标

- `retrieval_hit_rate`
- `citation_rate`
- `grounded_answer_rate`
- `correct_rejection_rate`
- `table_supported_rate`
- `expected_answer_terms_present`
- `self_check_match_rate`
- `risk_flags_rate`

### 用户行为指标

- 问题解决率。
- 平均首答时间。
- 用户追问率。
- 重新提问率。
- 引用证据点击率。
- 人工修正率。
- 拒答满意度。
- 上传到首个可用答案的完成率。

## 5. A/B 测试设计

### 实验一：检索策略

A 版：BM25-only  
B 版：BM25 + Dense + RRF

观察：

- 命中率。
- 引用准确率。
- 响应时间。
- self_check 失败率。

### 实验二：交互方式

A 版：直接回答  
B 版：模糊问题先澄清，再回答

观察：

- 用户追问率。
- 错答率。
- 问题解决率。
- 拒答满意度。

### 实验三：答案展示

A 版：只展示答案  
B 版：答案 + 页码 + 证据片段 + 风险标记

观察：

- 用户信任度。
- 证据点击率。
- 人工复核时间。
- 人工修正率。

## 6. 下一步迭代

- 多文档知识库。
- 用户历史问题记录。
- 答案反馈按钮。
- 错误样本自动进入评估集。
- 表格行列定位。
- 更严格的结构化引用校验。
- Web UI 部署。
- 针对合同、标准文件和合规材料建立独立 eval case set。
