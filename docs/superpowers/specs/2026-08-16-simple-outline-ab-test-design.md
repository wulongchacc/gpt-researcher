# Simple 可选提纲与 A/B 评测设计

## 1. 背景

当前项目已为 Deep Research 实现独立提纲接口和提纲确认界面，但 Deep Research 会递归创建多个子任务，并在中间提炼阶段大量调用高成本模型。实际测试中，单次 Deep Research 消耗显著高于原有基线，且中间模型调用失败会导致已抓取的上下文被丢弃，不适合在剩余求职准备时间内继续作为主要实验对象。

本轮将实验范围收缩到 Simple 报告，在不改变其检索和报告生成主流程的前提下增加“研究前确认提纲”可选开关，并使用同一模型、同一搜索配置和同一测试题进行 A/B 对照。

## 2. 目标

1. Simple 模式默认保持直接执行，确保原有用户流程和基线行为不变。
2. 用户可以在 Preference 中开启“研究前确认提纲”。
3. 开启后，系统先生成 3 至 5 个可编辑章节，用户确认后再启动 Simple Research。
4. Simple 提纲规划、检索、内容处理和报告生成全部使用 `qwen-plus`，不调用 `qwen3.7-max`。
5. 使用同一批题目对比无提纲与有提纲的报告质量、稳定性、耗时和成本。

## 3. 非目标

- 本轮不继续修复 Deep Research 的递归研究和上下文降级问题。
- 本轮不重做 Preference 页面整体中文化。
- 本轮不增加数据库持久化、用户账号或历史提纲管理。
- 本轮不引入新的搜索引擎或 MCP 服务。
- 本轮不改变 Simple 的检索器、抓取器和向量模型。

## 4. 用户体验

Preference 中增加一个二元开关：

```text
研究前确认提纲  [关闭/开启]
```

默认值为关闭。

### 4.1 开关关闭

```text
输入研究主题
→ 直接启动 Simple Research
→ 生成报告
```

该路径作为 A/B 实验的基线组。

### 4.2 开关开启

```text
输入研究主题
→ 请求 Simple 提纲
→ 展示 3 至 5 个章节
→ 用户增删、修改或排序章节
→ 用户确认
→ 携带确认后的提纲启动 Simple Research
→ 按提纲组织报告
```

该路径作为 A/B 实验的实验组。

### 4.3 失败体验

- 提纲生成期间禁用重复提交。
- 提纲请求最多等待 120 秒。
- 提纲生成失败时保留原研究主题，并提供“返回修改”和“重新生成”。
- 提纲失败不会自动退回直接研究，避免用户不知情地消耗额外 Token。
- 用户主动取消或返回时，不启动研究任务。

## 5. 架构方案

复用现有 `/api/outline` 接口，不新增 Simple 专用接口。请求中增加受白名单约束的 `model_profile`，后端根据 profile 使用对应模型配置。

### 5.1 提纲请求

```json
{
  "task": "研究主题",
  "language": "Chinese (Simplified)",
  "report_type": "research_report",
  "model_profile": "simple"
}
```

### 5.2 提纲响应

```json
{
  "sections": [
    {
      "id": "section-1",
      "title": "章节标题",
      "description": "研究范围"
    }
  ],
  "model_profile": "simple"
}
```

后端只接受 `research_report` 和 `deep` 两种 `report_type`，以及 `simple` 和 `deep` 两种 `model_profile`，并通过 `resolve_model_profile(report_type, model_profile)` 校验组合。Simple 提纲使用 Simple profile；Deep 提纲维持现有 Deep profile。客户端必须校验响应 profile 与请求一致。

### 5.3 研究启动请求

Simple 实验组在 WebSocket 启动消息中携带：

```json
{
  "report_type": "research_report",
  "model_profile": "simple",
  "outline": [
    {
      "id": "section-1",
      "title": "章节标题",
      "description": "研究范围"
    }
  ]
}
```

Simple 基线组不携带 `outline`，保持现有请求形态。后端沿用已有 `GPTResearcher.outline` 和报告提示词中的 `CONFIRMED REPORT STRUCTURE`，不创建第二套报告生成器。

## 6. 前端组件与状态

### 6.1 Preference 状态

在 `ChatBoxSettings` 中增加布尔字段：

```text
confirm_outline_before_research
```

默认值为 `false`。该字段仅控制当前浏览器会话中的启动流程，不发送给后端作为长期配置。

### 6.2 启动路由

`getResearchStartAction` 从只检查 `report_type` 改为同时检查设置：

```text
research_report + confirm_outline_before_research=false → start_directly
research_report + confirm_outline_before_research=true  → review_outline
deep                                                   → review_outline
其他报告类型                                            → start_directly
```

### 6.3 提纲确认

复用现有 Deep 提纲编辑界面。确认时根据当前报告类型选择 profile：

- `research_report` 使用 `simple`
- `deep` 使用 `deep`

类型定义不再把 `model_profile` 限制为仅 `deep`。

## 7. 模型路由

Simple 有提纲和无提纲两组必须使用相同模型：

```text
FAST_LLM      = dashscope:qwen-plus
SMART_LLM     = dashscope:qwen-plus
STRATEGIC_LLM = dashscope:qwen-plus
```

Simple 提纲接口必须通过 `resolve_model_profile("research_report", "simple")` 获取运行时配置，禁止依赖服务器全局 `.env` 恰好配置为 qwen-plus。

这样可以保证 A/B 实验的唯一主要变量是“是否由用户确认提纲”，而不是模型能力差异。

## 8. 错误处理与兼容性

- 缺少或非法 `model_profile` 时，接口返回 4xx，不静默选择高成本模型。
- Simple 请求不能使用 `deep` profile，Deep 请求不能使用 `simple` profile。
- 提纲响应结构不合法时，前端显示明确错误，不启动研究。
- 开关关闭时不请求 `/api/outline`，避免基线组额外成本。
- 旧客户端不发送开关和提纲时，仍按原 Simple 流程工作。
- Deep 现有流程保持可用，但不纳入本轮验收和实验结论。

## 9. 测试策略

### 9.1 前端单元测试

- Simple + 开关关闭返回 `start_directly`。
- Simple + 开关开启返回 `review_outline`。
- Deep 始终返回 `review_outline`。
- Simple 提纲请求携带 `model_profile=simple`。
- Simple 确认后启动请求携带 `outline` 和 `model_profile=simple`。
- Simple 直接执行不携带 `outline` 和 `model_profile`。
- 非法或不匹配的提纲响应被拒绝。
- 超时、取消和重复点击行为保持正确。

### 9.2 后端单元测试

- `/api/outline` 对 Simple 使用 Simple profile。
- `/api/outline` 对 Deep 使用 Deep profile。
- 非法 profile 返回 4xx。
- Simple 的确认提纲能够传递到 `GPTResearcher`。
- Simple profile 三类模型均解析为 `qwen-plus`。

### 9.3 回归测试

- 现有 Simple 无提纲测试继续通过。
- 现有 Deep 提纲测试继续通过。
- WebSocket 执行选项测试覆盖 Simple outline。

## 10. A/B 评测设计

### 10.1 实验控制

两组使用相同的：

- 5 道中文研究题目
- `qwen-plus`
- 搜索器和抓取器
- 向量模型
- 服务器配置
- 最大搜索结果数
- 运行时间段和评测脚本版本

每道题分别运行一次基线组和一次实验组，共 10 次 Simple Research。评测脚本不自动重试；失败运行作为失败样本保留，不能选择性删除。只有服务器断电等与应用无关、且没有产生模型调用记录的基础设施中断可以补跑，补跑原因必须写入实验记录。

### 10.2 指标

1. 报告成功率。
2. 有效引用率。
3. 平均耗时。
4. 平均成本或总 Token。
5. 提纲章节覆盖率：最终报告中得到实质内容覆盖的确认章节数 / 确认章节总数。

章节覆盖采用确定性文本规则进行初筛：将章节标题和报告 Markdown 标题去除空白与标点后比较，标题完全相同或报告标题包含确认章节标题时视为标题匹配；匹配标题下至少包含 100 个中文字符的正文时计为有效覆盖。评测结果保留人工抽查记录。指标报告分别输出两组结果和相对变化，不只展示表现更好的样本。

### 10.3 成功标准

功能验收要求：

- 两条 Simple 路径均可完成报告。
- 开关关闭不产生提纲调用。
- 开关开启时用户可以修改并确认提纲。
- Simple 全流程不调用 `qwen3.7-max`。

实验结果不预设“提纲组必须全面更好”。作品集的有效结论可以是结构覆盖率提高，同时耗时或成本小幅增加。最终简历描述必须使用真实测量结果。

## 11. 交付范围

本功能以一个独立 Git 分支交付，包含：

- Preference 可选开关。
- 通用化提纲 API。
- Simple 提纲确认和执行链路。
- 前后端自动化测试。
- Simple A/B 评测配置与结果摘要。

代码实现完成后先进行无模型单元测试，再部署到服务器进行一题冒烟测试，最后运行完整 A/B 实验。
