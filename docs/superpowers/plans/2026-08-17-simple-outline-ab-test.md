# Simple 可选提纲与 A/B 评测实施计划

> **供 Agent 执行：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项实施；使用本文复选框记录进度。

**目标：** 为 Simple Research 增加默认关闭的“研究前确认提纲”开关，并用同一批中文题目量化比较无提纲与确认提纲两条 Simple 路径。

**架构：** 复用现有 `/api/outline`、提纲编辑弹窗和 `GPTResearcher.outline`，通过请求级 `model_profile` 将 Simple 提纲和研究全过程固定为 `qwen-plus`。前端仅在 `research_report + confirm_outline_before_research=true` 或 `deep` 时进入提纲确认流程；评测工具预生成并保存可人工审阅的 Simple 提纲，再把相同题目分别作为基线组和提纲组串行运行。

**技术栈：** Next.js 14、React 18、TypeScript、Node test runner、FastAPI、Pydantic v2、Python 3.12、unittest、Docker Compose。

## 全局约束

- `confirm_outline_before_research` 默认值必须为 `false`。
- Simple 开关关闭时不得请求 `/api/outline`，也不得发送 `outline` 或 `model_profile`。
- Simple 开关开启时，提纲请求必须发送 `report_type=research_report` 和 `model_profile=simple`。
- Simple 确认提纲后的 WebSocket 启动消息必须发送 `outline` 和 `model_profile=simple`。
- Simple 的 `FAST_LLM`、`SMART_LLM`、`STRATEGIC_LLM` 均固定为 `dashscope:qwen-plus`。
- Deep 继续使用 `model_profile=deep`，但不纳入本轮实验结论。
- 提纲必须包含 3 至 5 个唯一且非空的章节。
- 提纲请求超时为 120 秒；取消、失败或响应非法时不得启动研究。
- A/B 两组必须使用同一批 5 道 Simple 题目、同一搜索器、抓取器、向量模型和最大搜索结果数。
- 评测脚本不做应用层自动补跑；失败结果必须保留。
- 不修改服务器全局 `.env` 来完成请求级模型路由。

---

### 任务 1：将提纲 API 通用化为 Simple/Deep 请求级路由

**文件：**
- 修改：`backend/server/app.py:53-101,219-251`
- 修改：`tests/test_outline.py:305-404`

**接口：**
- 接收：`OutlineRequest(task: str, language: str, report_type: Literal["research_report", "deep"], model_profile: Literal["simple", "deep"])`
- 调用：`resolve_model_profile(request.report_type, request.model_profile)`
- 返回：`OutlineResponse(sections: list[dict], model_profile: Literal["simple", "deep"])`

- [ ] **步骤 1：把现有 Deep 专用端点测试改成 Simple/Deep 参数化失败测试**

在 `tests/test_outline.py` 的 `OutlineApiTests` 中替换 Deep 专用测试，并增加组合校验测试：

```python
async def test_endpoint_uses_requested_simple_profile(self):
    module = _load_app_module()
    config = SimpleNamespace(apply_runtime_overrides=Mock())
    module.Config = Mock(return_value=config)
    module.resolve_model_profile = Mock(
        return_value=("simple", {"STRATEGIC_LLM": "dashscope:qwen-plus"})
    )
    planner = SimpleNamespace(
        generate=AsyncMock(return_value=[
            SimpleNamespace(id="section-1", title="背景", description="研究背景"),
            SimpleNamespace(id="section-2", title="现状", description="研究现状"),
            SimpleNamespace(id="section-3", title="趋势", description="研究趋势"),
        ])
    )
    module.OutlinePlanner = Mock(return_value=planner)

    response = await module.generate_outline(module.OutlineRequest(
        task="研究人工智能教育应用",
        language="Chinese (Simplified)",
        report_type="research_report",
        model_profile="simple",
    ))

    module.resolve_model_profile.assert_called_once_with("research_report", "simple")
    config.apply_runtime_overrides.assert_called_once_with(
        {"STRATEGIC_LLM": "dashscope:qwen-plus"}
    )
    self.assertEqual(response.model_profile, "simple")

async def test_endpoint_preserves_deep_profile(self):
    module = _load_app_module()
    config = SimpleNamespace(apply_runtime_overrides=Mock())
    module.Config = Mock(return_value=config)
    module.resolve_model_profile = Mock(return_value=("deep", {}))
    module.OutlinePlanner = Mock(return_value=SimpleNamespace(
        generate=AsyncMock(return_value=[
            SimpleNamespace(id="section-1", title="背景", description="范围"),
            SimpleNamespace(id="section-2", title="风险", description="范围"),
            SimpleNamespace(id="section-3", title="趋势", description="范围"),
        ])
    ))

    response = await module.generate_outline(module.OutlineRequest(
        task="深度研究主题",
        report_type="deep",
        model_profile="deep",
    ))

    module.resolve_model_profile.assert_called_once_with("deep", "deep")
    self.assertEqual(response.model_profile, "deep")

def test_mismatched_report_type_and_profile_is_rejected(self):
    module = _load_app_module()
    with self.assertRaises(ValidationError):
        module.OutlineRequest(
            task="研究主题",
            report_type="research_report",
            model_profile="deep",
        )
```

- [ ] **步骤 2：运行测试并确认它因请求模型仍缺少字段而失败**

运行：

```bash
python -m unittest tests.test_outline.OutlineApiTests -v
```

预期：Simple 请求构造或端点断言失败，当前代码仍硬编码 `resolve_model_profile("deep", "deep")`。

- [ ] **步骤 3：实现请求字段和匹配校验**

在 `backend/server/app.py` 导入 `Literal` 和 `model_validator`，将请求模型改为：

```python
class OutlineRequest(BaseModel):
    task: str
    language: str = "Chinese (Simplified)"
    report_type: Literal["research_report", "deep"]
    model_profile: Literal["simple", "deep"]

    @field_validator("task")
    @classmethod
    def validate_task(cls, value):
        normalized = value.strip()
        if not normalized:
            raise ValueError("Research task cannot be empty")
        return normalized

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value):
        return normalize_report_language(value or "Chinese (Simplified)")

    @model_validator(mode="after")
    def validate_profile_matches_report_type(self):
        expected = "deep" if self.report_type == "deep" else "simple"
        if self.model_profile != expected:
            raise ValueError("model_profile does not match report_type")
        return self


class OutlineResponse(BaseModel):
    sections: list[dict]
    model_profile: Literal["simple", "deep"]
```

端点不再写死 Deep：

```python
profile, overrides = resolve_model_profile(
    request.report_type,
    request.model_profile,
)
```

- [ ] **步骤 4：运行后端提纲和模型路由测试**

运行：

```bash
python -m unittest tests.test_outline tests.test_model_profiles -v
```

预期：Simple 使用 `qwen-plus`，Deep 保持 Deep profile，非法组合在模型边界返回验证错误。

- [ ] **步骤 5：提交后端通用提纲接口**

```bash
git add backend/server/app.py tests/test_outline.py
git commit -m "feat: route outline generation by report profile"
```

**本任务预期效果：** `/api/outline` 不再等同于 Deep 专用接口；Simple 可以显式、安全地使用 `qwen-plus` 生成提纲，且不能误调用 Deep profile。

---

### 任务 2：扩展前端类型、启动决策和请求载荷

**文件：**
- 修改：`frontend/nextjs/types/data.ts:35-80`
- 修改：`frontend/nextjs/services/researchStart.ts`
- 修改：`frontend/nextjs/services/outlineApi.ts`
- 修改：`frontend/nextjs/tests/researchStart.test.ts`
- 修改：`frontend/nextjs/tests/outlineApi.test.ts`

**接口：**
- 产出：`ModelProfile = "simple" | "deep"`
- 产出：`OutlineRequest.report_type`、`OutlineRequest.model_profile`
- 产出：`getResearchStartAction(settings: ChatBoxSettings) -> ResearchStartAction`
- 产出：`ResearchExecutionOptions.model_profile?: ModelProfile`

- [ ] **步骤 1：先写 Simple 开关的启动路由失败测试**

在 `frontend/nextjs/tests/researchStart.test.ts` 中将路由测试改为：

```typescript
test("routes simple reports through outline review only when enabled", () => {
  assert.equal(
    getResearchStartAction({ ...settings, confirm_outline_before_research: false }),
    "start_directly",
  );
  assert.equal(
    getResearchStartAction({ ...settings, confirm_outline_before_research: true }),
    "review_outline",
  );
  assert.equal(
    getResearchStartAction({ ...settings, report_type: "deep" }),
    "review_outline",
  );
});

test("prepareResearchStart requests the simple profile when enabled", async () => {
  let capturedRequest: unknown;
  const result = await prepareResearchStart({
    task: "研究主题",
    settings: { ...settings, confirm_outline_before_research: true },
    requestOutline: async (request) => {
      capturedRequest = request;
      return { sections: outline, model_profile: "simple" };
    },
  });

  assert.deepEqual(capturedRequest, {
    task: "研究主题",
    language: "Chinese (Simplified)",
    report_type: "research_report",
    model_profile: "simple",
  });
  assert.deepEqual(result, { action: "review_outline", sections: outline });
});

test("simple confirmed outline is included in the WebSocket payload", () => {
  const payload = buildResearchStartPayload({
    task: "研究主题",
    settings: { ...settings, confirm_outline_before_research: true },
    queryDomains: [],
    execution: { outline, model_profile: "simple" },
  });

  assert.equal(payload.model_profile, "simple");
  assert.deepEqual(payload.outline, outline);
});
```

把测试夹具 `settings` 增加 `confirm_outline_before_research: false`。

- [ ] **步骤 2：增加 API profile 匹配失败测试**

在 `frontend/nextjs/tests/outlineApi.test.ts` 中为有效响应拆分 Simple/Deep，并验证响应 profile 必须匹配请求：

```typescript
test("requestOutline sends the simple report type and profile", async () => {
  let capturedBody: unknown;
  const fetchImpl: typeof fetch = async (_input, init) => {
    capturedBody = JSON.parse(String(init?.body));
    return Response.json({ ...validResponse, model_profile: "simple" });
  };

  await requestOutline(
    {
      task: "研究中国新能源汽车市场",
      language: "Chinese (Simplified)",
      report_type: "research_report",
      model_profile: "simple",
    },
    { baseUrl: "http://localhost:8000", fetchImpl },
  );

  assert.deepEqual(capturedBody, {
    task: "研究中国新能源汽车市场",
    language: "Chinese (Simplified)",
    report_type: "research_report",
    model_profile: "simple",
  });
});

test("requestOutline rejects a profile that does not match the request", async () => {
  const fetchImpl: typeof fetch = async () =>
    Response.json({ ...validResponse, model_profile: "deep" });

  await assert.rejects(
    requestOutline(
      {
        task: "研究主题",
        language: "Chinese (Simplified)",
        report_type: "research_report",
        model_profile: "simple",
      },
      { baseUrl: "http://localhost:8000", fetchImpl },
    ),
    (error: unknown) =>
      error instanceof OutlineApiError && error.code === "invalid_response",
  );
});
```

- [ ] **步骤 3：运行前端纯逻辑测试并确认失败**

运行：

```bash
cd frontend/nextjs
node --experimental-strip-types --test tests/researchStart.test.ts tests/outlineApi.test.ts
```

预期：类型或断言失败，因为当前类型仅允许 `deep`，启动函数也只接收字符串报告类型。

- [ ] **步骤 4：实现强类型和启动决策**

在 `frontend/nextjs/types/data.ts` 增加：

```typescript
export type ModelProfile = "simple" | "deep";

export interface OutlineRequest {
  task: string;
  language: ReportLanguage;
  report_type: "research_report" | "deep";
  model_profile: ModelProfile;
}

export interface OutlineResponse {
  sections: OutlineSection[];
  model_profile: ModelProfile;
}

export interface ResearchExecutionOptions {
  outline?: OutlineSection[];
  model_profile?: ModelProfile;
}

export interface ChatBoxSettings {
  // 保留原字段
  confirm_outline_before_research: boolean;
}
```

在 `researchStart.ts` 中用设置对象决定流程：

```typescript
const getModelProfile = (reportType: string): ModelProfile =>
  reportType === "deep" ? "deep" : "simple";

export const getResearchStartAction = (
  settings: ChatBoxSettings,
): ResearchStartAction => {
  if (settings.report_type === "deep") return "review_outline";
  if (
    settings.report_type === "research_report" &&
    settings.confirm_outline_before_research
  ) return "review_outline";
  return "start_directly";
};
```

`prepareResearchStart` 请求中发送 `report_type` 和匹配的 profile；`buildResearchStartPayload` 只在 `execution.outline` 非空时携带提纲，并校验 `execution.model_profile === getModelProfile(settings.report_type)`。Simple 开关关闭且没有执行选项时保持原载荷不变。

在 `outlineApi.ts` 中把 `parseOutlineResponse` 增加 `expectedProfile` 参数，并以 `response.model_profile !== expectedProfile` 判定非法响应；默认超时改为：

```typescript
const DEFAULT_TIMEOUT_MS = 120_000;
```

- [ ] **步骤 5：运行前端服务测试**

```bash
cd frontend/nextjs
node --experimental-strip-types --test tests/researchStart.test.ts tests/outlineApi.test.ts tests/outlineRequestGate.test.ts
```

预期：开关关闭直接执行，开关开启请求 Simple 提纲，Deep 行为不变，profile 不匹配、超时、取消和重复请求均被正确处理。

- [ ] **步骤 6：提交前端服务契约**

```bash
git add frontend/nextjs/types/data.ts frontend/nextjs/services/researchStart.ts frontend/nextjs/services/outlineApi.ts frontend/nextjs/tests/researchStart.test.ts frontend/nextjs/tests/outlineApi.test.ts
git commit -m "feat: add simple outline start contracts"
```

**本任务预期效果：** 前端已经能可靠区分四条启动路径，并能生成正确的 Simple/Deep 提纲请求和 WebSocket 载荷；尚未在 Preference 页面展示开关。

---

### 任务 3：在 Preference 和移动端设置中增加可选开关

**文件：**
- 新建：`frontend/nextjs/components/Settings/OutlineConfirmationToggle.tsx`
- 修改：`frontend/nextjs/components/Task/ResearchForm.tsx:1-180`
- 修改：`frontend/nextjs/components/layouts/MobileLayout.tsx:225-310`
- 修改：`frontend/nextjs/app/page.tsx:40-70`
- 修改：`frontend/nextjs/app/research/[id]/page.tsx:36-70`
- 修改：`frontend/nextjs/src/GPTResearcher.tsx:40-55`

**接口：**
- 产出：`OutlineConfirmationToggle({ checked, disabled, onChange })`
- 状态：`ChatBoxSettings.confirm_outline_before_research`
- 持久化：沿用 `localStorage.chatBoxSettings`

- [ ] **步骤 1：实现语义化 Toggle 组件**

创建 `OutlineConfirmationToggle.tsx`：

```tsx
interface OutlineConfirmationToggleProps {
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}

export default function OutlineConfirmationToggle({
  checked,
  disabled = false,
  onChange,
}: OutlineConfirmationToggleProps) {
  return (
    <label className="flex items-center justify-between gap-4 py-2">
      <span>
        <span className="block font-medium text-white">研究前确认提纲</span>
        <span className="block text-sm text-gray-400">
          先生成并编辑报告结构，确认后再开始研究
        </span>
      </span>
      <input
        type="checkbox"
        role="switch"
        aria-label="研究前确认提纲"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="h-5 w-5 accent-teal-500"
      />
    </label>
  );
}
```

- [ ] **步骤 2：将 Toggle 接入 Preference**

在 `ResearchForm.tsx` 的语言设置后渲染组件，只允许 `research_report` 操作；切换到其他类型时显示但禁用，Deep 仍由系统强制走提纲：

```tsx
<OutlineConfirmationToggle
  checked={chatBoxSettings.confirm_outline_before_research}
  disabled={report_type !== "research_report"}
  onChange={(checked) => setChatBoxSettings((previous) => ({
    ...previous,
    confirm_outline_before_research: checked,
  }))}
/>
```

在 `MobileLayout.tsx` 的报告语言后增加相同的 `role="switch"` 控件，更新同一设置字段。

- [ ] **步骤 3：为所有设置入口补充默认值**

以下三个默认设置对象都增加：

```typescript
confirm_outline_before_research: false,
```

修改位置：

- `frontend/nextjs/app/page.tsx`
- `frontend/nextjs/app/research/[id]/page.tsx`
- `frontend/nextjs/src/GPTResearcher.tsx`

现有 `{ ...defaultSettings, ...parsedSettings }` 会让旧 localStorage 自动获得 `false`，不需要迁移脚本。

- [ ] **步骤 4：运行 TypeScript 构建验证所有设置对象完整**

```bash
cd frontend/nextjs
npm run build
```

预期：Next.js 构建成功；如果任何 `ChatBoxSettings` 初始化遗漏新字段，TypeScript 会在此步骤报错。

- [ ] **步骤 5：提交 Preference 开关**

```bash
git add frontend/nextjs/components/Settings/OutlineConfirmationToggle.tsx frontend/nextjs/components/Task/ResearchForm.tsx frontend/nextjs/components/layouts/MobileLayout.tsx frontend/nextjs/app/page.tsx 'frontend/nextjs/app/research/[id]/page.tsx' frontend/nextjs/src/GPTResearcher.tsx
git commit -m "feat: add optional outline confirmation setting"
```

**本任务预期效果：** 用户在桌面 Preference 和移动端设置中可以打开或关闭“研究前确认提纲”；旧用户和新用户默认关闭，原 Simple 体验不发生变化。

---

### 任务 4：接通页面编排与 Simple 确认提纲执行链路

**文件：**
- 修改：`frontend/nextjs/app/page.tsx:85-115,340-565,1000-1025`
- 修改：`tests/test_websocket_manager.py:70-165`
- 修改：`tests/test_outline_execution.py`

**接口：**
- 消费：`getResearchStartAction(chatBoxSettings)`
- 消费：`prepareResearchStart(...)`
- 产出：`startResearch(task, { outline, model_profile: "simple" | "deep" })`
- 后端保证：Simple 的 `outline` 和 `model_profile=simple` 传入 `BasicReport/GPTResearcher`

- [ ] **步骤 1：增加 Simple WebSocket 传播回归测试**

在 `tests/test_websocket_manager.py` 增加：

```python
async def test_run_agent_passes_simple_outline_to_basic_report(self):
    websocket_manager = _load_websocket_manager_module()
    captured = {}

    class FakeLogsHandler:
        def __init__(self, websocket, task):
            self.websocket = websocket
            self.task = task

    class FakeBasicReport:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.gpt_researcher = object()

        async def run(self):
            return "stub-report"

    websocket_manager.CustomLogsHandler = FakeLogsHandler
    websocket_manager.BasicReport = FakeBasicReport
    outline = [{"id": "section-1", "title": "现状", "description": "范围"}]

    await websocket_manager.run_agent(
        task="test-task",
        report_type="research_report",
        report_source="web",
        source_urls=[],
        document_urls=[],
        tone=websocket_manager.Tone.Objective,
        websocket=object(),
        model_profile="simple",
        outline=outline,
    )

    self.assertEqual(captured["model_profile"], "simple")
    self.assertEqual(captured["outline"], outline)
```

在 `tests/test_outline_execution.py` 增加报告提示词中文标题顺序断言，证明 Simple writer 能复用同一结构约束。

- [ ] **步骤 2：运行后端传播测试，确认现有链路是否已经满足**

```bash
python -m unittest tests.test_websocket_manager tests.test_outline_execution -v
```

预期：如果现有 `run_agent -> BasicReport -> GPTResearcher` 已完整透传，测试直接通过；若失败，只修复丢失参数的那一层，不改研究算法。

- [ ] **步骤 3：修改页面启动判断和确认 profile**

在 `app/page.tsx` 中把所有调用改为传设置对象：

```typescript
getResearchStartAction(chatBoxSettings)
```

当前移动端会让所有非 Deep 请求走 `/api/chat`，因此 Simple 确认提纲后必须绕过这条简化分支，继续使用支持执行选项的 WebSocket：

```typescript
if (
  isMobile &&
  chatBoxSettings.report_type !== "deep" &&
  !execution?.outline?.length
) {
  // 保留原移动端无提纲快速路径。
}
```

这样移动端无提纲 Simple 行为不变，而有提纲 Simple 可以把 `outline` 和 `model_profile=simple` 发送到后端。

确认提纲时根据当前报告类型选择 profile：

```typescript
const handleConfirmOutline = (sections: OutlineSection[]) => {
  if (!pendingOutline) return;
  const task = pendingOutline.task;
  const modelProfile = chatBoxSettings.report_type === "deep" ? "deep" : "simple";
  setPendingOutline(null);
  void startResearch(task, { outline: sections, model_profile: modelProfile });
};
```

`prepareResearch` 保持现有请求门控、取消、重试和错误弹窗；开关关闭时必须在调用 `requestOutline` 前直接进入 `startResearch`。

- [ ] **步骤 4：运行前后端聚焦测试和前端构建**

```bash
python -m unittest tests.test_websocket_manager tests.test_outline_execution tests.test_outline tests.test_model_profiles -v
cd frontend/nextjs
node --experimental-strip-types --test tests/researchStart.test.ts tests/outlineApi.test.ts tests/outlineRequestGate.test.ts tests/outlineEditor.test.ts
npm run build
```

预期：Simple 两条路径、Deep 原路径、提纲编辑、重复请求门控和后端传播全部通过；前端构建无类型错误。

- [ ] **步骤 5：提交完整 Simple 交互链路**

```bash
git add frontend/nextjs/app/page.tsx tests/test_websocket_manager.py tests/test_outline_execution.py
git commit -m "feat: run simple research from confirmed outline"
```

**本任务预期效果：** 开关关闭时点击研究立即执行；开启时先出现提纲生成状态，再进入可编辑提纲，确认后启动同一个 Simple Research，并按章节顺序写报告。失败、取消、返回或超时都不会偷偷启动研究。

---

### 任务 5：扩展评测工具以支持可复现的 Simple A/B 实验

**文件：**
- 新建：`evals/chinese_reliability/outline_metrics.py`
- 新建：`evals/chinese_reliability/prepare_simple_outlines.py`
- 新建：`evals/chinese_reliability/compare_ab.py`
- 修改：`evals/chinese_reliability/run_benchmark.py`
- 修改：`evals/chinese_reliability/metrics.py`
- 修改：`evals/chinese_reliability/README.md`
- 新建测试：`tests/test_outline_metrics.py`
- 新建测试：`tests/test_ab_comparison.py`
- 修改：`tests/test_reliability_metrics.py`
- 修改：`tests/test_reliability_runner.py`

**接口：**
- 产出：`measure_outline_coverage(report: str, sections: list[dict]) -> dict`
- 产出：`load_outline_records(path: Path) -> dict[str, dict]`
- 产出：`build_ab_comparison(baseline: dict, enhanced: dict) -> dict`
- 扩展：`run_single_case(..., mode: str, outline_record: dict | None)`
- 输出：每题增加 `outline_section_count`、`outline_covered_count`、`outline_coverage_rate`

- [ ] **步骤 1：为章节覆盖率写失败测试**

创建 `tests/test_outline_metrics.py`：

```python
import unittest

from evals.chinese_reliability.outline_metrics import measure_outline_coverage


class OutlineCoverageTests(unittest.TestCase):
    def test_counts_matching_heading_with_substantial_chinese_body(self):
        sections = [
            {"title": "行业现状", "description": ""},
            {"title": "主要风险", "description": ""},
            {"title": "未来趋势", "description": ""},
        ]
        report = (
            "# 报告\n\n## 行业现状\n" + "中" * 120 +
            "\n\n## 主要风险分析\n" + "中" * 130 +
            "\n\n## 未来趋势\n" + "中" * 20
        )

        result = measure_outline_coverage(report, sections)

        self.assertEqual(result["outline_section_count"], 3)
        self.assertEqual(result["outline_covered_count"], 2)
        self.assertAlmostEqual(result["outline_coverage_rate"], 2 / 3)

    def test_punctuation_and_spaces_do_not_break_title_matching(self):
        result = measure_outline_coverage(
            "## 未来 趋势：三年展望\n" + "中" * 100,
            [{"title": "未来趋势", "description": ""}],
        )
        self.assertEqual(result["outline_covered_count"], 1)
```

- [ ] **步骤 2：实现确定性的 Markdown 章节覆盖计算**

`outline_metrics.py` 使用正则识别 `#` 至 `######` 标题；标题和确认章节标题去掉 Unicode 标点与空白后比较。标题完全相同或报告标题包含章节标题，并且该标题到下一标题之间至少含 100 个中文字符时计为覆盖。

核心接口：

```python
def measure_outline_coverage(report: str, sections: list[dict]) -> dict:
    heading_blocks = extract_heading_blocks(report)
    covered = 0
    for section in sections:
        expected = normalize_heading(str(section.get("title") or ""))
        matched = any(
            expected
            and (heading == expected or expected in heading)
            and chinese_char_count(body) >= 100
            for heading, body in heading_blocks
        )
        covered += int(matched)
    total = len(sections)
    return {
        "outline_section_count": total,
        "outline_covered_count": covered,
        "outline_coverage_rate": covered / total if total else 0.0,
    }
```

- [ ] **步骤 3：增加提纲预生成脚本并记录成本、耗时**

`prepare_simple_outlines.py`：

1. 从 `queries.json` 只读取 `report_type=research_report` 的 5 道题。
2. 对每题调用 `resolve_model_profile("research_report", "simple")`。
3. 用 `OutlinePlanner.generate(..., cost_callback=collector)` 生成 3 至 5 节提纲。
4. 每完成一题立即写入 `outputs/evals/chinese_reliability/simple-outlines.json`。
5. 每条记录保存 `id`、`question`、`sections`、`outline_duration_seconds`、`outline_cost`。

为此给 `OutlinePlanner.generate` 增加可选参数：

```python
async def generate(
    self,
    task: str,
    language: str = "English",
    cost_callback=None,
) -> list[OutlineSection]:
```

并把 `cost_callback=cost_callback` 传给 `create_chat_completion`。API 调用不提供 callback，行为保持不变。

- [ ] **步骤 4：让评测运行器读取确认提纲并计算总指标**

`run_benchmark.py` 保留现有 `--mode baseline|enhanced`：

- `baseline`：不读取提纲，不传 `outline/model_profile`。
- `enhanced`：要求 `--outlines <json>`，按题目 ID 读取人工确认后的提纲，构造研究员时传 `outline=...`、`model_profile="simple"`。
- Enhanced 的总耗时为提纲耗时加研究耗时，总成本为提纲成本加研究成本。
- 每题结果合并 `measure_outline_coverage` 输出；基线组三个覆盖字段为 `0/0/0.0`。
- 加载时校验题目 ID、题目文本和 3 至 5 个章节，防止把错误提纲配给题目。

研究员构造代码应明确为：

```python
researcher_kwargs = {
    "query": case["question"],
    "report_type": "research_report",
    "report_format": "markdown",
    "language": "Chinese (Simplified)",
    "verbose": False,
}
if outline_record:
    researcher_kwargs.update(
        outline=outline_record["sections"],
        model_profile="simple",
    )
researcher = researcher_factory(**researcher_kwargs)
```

`metrics.summarize_runs` 对存在提纲的记录增加：

```python
"outline_section_count": total_outline_sections,
"outline_covered_count": total_covered_sections,
"outline_coverage_rate": (
    total_covered_sections / total_outline_sections
    if total_outline_sections else 0.0
),
```

`summary.md` 增加“提纲覆盖率”列。

`compare_ab.py` 读取两组 `summary-simple.json`，校验两组题目数均为 5，然后生成：

- `comparison.json`：保存两组原始指标、成功率百分点变化和其余指标相对变化。
- `comparison.md`：用一张表展示基线值、提纲组值和变化值。

对基线值为 0 的相对变化返回 `null` 和 `-`，避免除零或伪造无穷大。核心函数：

```python
def relative_change(baseline: float | None, enhanced: float | None) -> float | None:
    if baseline in (None, 0) or enhanced is None:
        return None
    return (enhanced - baseline) / baseline


def build_ab_comparison(baseline: dict, enhanced: dict) -> dict:
    return {
        "query_count": baseline["total_queries"],
        "baseline": baseline,
        "enhanced": enhanced,
        "changes": {
            "success_rate_points": (
                enhanced["report_success_rate"] - baseline["report_success_rate"]
            ),
            "valid_citation_rate_relative": relative_change(
                baseline["valid_citation_rate"], enhanced["valid_citation_rate"]
            ),
            "average_duration_relative": relative_change(
                baseline["average_duration_seconds"],
                enhanced["average_duration_seconds"],
            ),
            "average_cost_relative": relative_change(
                baseline["average_cost"], enhanced["average_cost"]
            ),
            "outline_coverage_rate": enhanced["outline_coverage_rate"],
        },
}
```

`tests/test_ab_comparison.py` 至少断言成功率百分点差、引用率相对变化、耗时相对变化、成本相对变化和基线为 0 时返回 `None`，测试数据固定为：

```python
baseline = {
    "total_queries": 5,
    "report_success_rate": 0.6,
    "valid_citation_rate": 0.75,
    "average_duration_seconds": 120.0,
    "average_cost": 0.08,
    "outline_coverage_rate": 0.0,
}
enhanced = {
    "total_queries": 5,
    "report_success_rate": 0.8,
    "valid_citation_rate": 0.825,
    "average_duration_seconds": 150.0,
    "average_cost": 0.1,
    "outline_coverage_rate": 0.9,
}
```

- [ ] **步骤 5：运行全部评测单元测试**

```bash
python -m unittest tests.test_outline_metrics tests.test_ab_comparison tests.test_reliability_metrics tests.test_reliability_runner tests.test_outline -v
```

预期：覆盖率规则、提纲与题目配对、Enhanced 载荷、成本/耗时合并、基线兼容和摘要输出全部通过，测试不调用真实模型。

- [ ] **步骤 6：更新评测说明和实际执行命令**

在 `evals/chinese_reliability/README.md` 写入以下三段命令：

```bash
# 1. 生成 Simple 提纲；生成后人工检查 simple-outlines.json
python -m evals.chinese_reliability.prepare_simple_outlines

# 2. 基线组：5 道 Simple，无提纲
python -m evals.chinese_reliability.run_benchmark \
  --mode baseline \
  --ids simple-01 simple-02 simple-03 simple-04 simple-05 \
  --output-dir outputs/evals/chinese_reliability/simple-ab/baseline

# 3. 实验组：同 5 道 Simple，使用确认提纲
python -m evals.chinese_reliability.run_benchmark \
  --mode enhanced \
  --ids simple-01 simple-02 simple-03 simple-04 simple-05 \
  --outlines outputs/evals/chinese_reliability/simple-outlines.json \
  --output-dir outputs/evals/chinese_reliability/simple-ab/outline

# 4. 生成两组量化对比
python -m evals.chinese_reliability.compare_ab \
  --baseline outputs/evals/chinese_reliability/simple-ab/baseline/summary-simple.json \
  --enhanced outputs/evals/chinese_reliability/simple-ab/outline/summary-simple.json \
  --output-dir outputs/evals/chinese_reliability/simple-ab/comparison
```

- [ ] **步骤 7：提交评测能力**

```bash
git add evals/chinese_reliability gpt_researcher/skills/outline.py tests/test_outline.py tests/test_outline_metrics.py tests/test_ab_comparison.py tests/test_reliability_metrics.py tests/test_reliability_runner.py
git commit -m "feat: evaluate simple research with confirmed outlines"
```

**本任务预期效果：** 能以同一批题目生成两组完整、不可挑选的数据，输出成功率、有效引用率、平均耗时、平均成本和提纲覆盖率；提纲成本和耗时不会被遗漏。

---

### 任务 6：整体回归、部署冒烟和 A/B 实验验收

**文件：**
- 修改：`docs/superpowers/specs/2026-08-16-simple-outline-ab-test-design.md`（仅在实现与设计存在经确认的偏差时修改）
- 生成但不提交：`outputs/evals/chinese_reliability/simple-ab/**`

**接口：**
- 验收前端：Preference 开关、提纲编辑、确认和直接执行
- 验收后端：Simple profile 全为 `qwen-plus`
- 验收实验：两组各 5 道题，失败样本保留

- [ ] **步骤 1：运行本地无模型完整回归**

```bash
python -m unittest tests.test_outline tests.test_outline_execution tests.test_model_profiles tests.test_websocket_manager tests.test_outline_metrics tests.test_ab_comparison tests.test_reliability_metrics tests.test_reliability_runner -v
cd frontend/nextjs
node --experimental-strip-types --test tests/researchStart.test.ts tests/outlineApi.test.ts tests/outlineRequestGate.test.ts tests/outlineEditor.test.ts
npm run build
```

预期：所有 Python/TypeScript 测试和 Next.js 构建通过，不产生 DashScope 调用。

- [ ] **步骤 2：检查改动范围和秘密文件**

```bash
git status --short
git diff --check
git diff --stat main...HEAD
git grep -n "DASHSCOPE_API_KEY=" -- ':!*.example' ':!.env.example'
```

预期：没有 `.env`、API Key、`outputs/` 或服务器备份文件进入 Git；改动仅覆盖本计划列出的功能和测试文件。

- [ ] **步骤 3：部署到服务器并确认实际容器配置**

服务器拉取合并后的分支并重建后端和前端容器后执行：

```bash
sudo docker compose exec -T gpt-researcher sh -lc \
  'echo FAST_LLM=$FAST_LLM; echo SMART_LLM=$SMART_LLM; echo STRATEGIC_LLM=$STRATEGIC_LLM; echo EMBEDDING=$EMBEDDING'
sudo docker compose ps
```

预期：容器运行正常；全局环境值只作记录，Simple 请求仍由 request-scoped `simple` profile 强制使用三项 `qwen-plus`。

- [ ] **步骤 4：执行一题双路径冒烟测试**

题目固定为：

```text
生成式AI在高校教学中有哪些典型应用和风险？
```

先关闭开关运行一次，确认直接进入 Agent Work；再开启开关运行一次，确认出现提纲、可修改章节、确认后生成报告。后端日志检查：

```bash
sudo docker compose logs --since=30m --no-color gpt-researcher \
  | grep -E "api/outline|qwen3.7-max|qwen-plus|ERROR|Traceback" \
  | tail -100
```

预期：两份 Simple 报告都完成；开启组出现一次 `/api/outline`；Simple 流程没有 `qwen3.7-max` 调用。

- [ ] **步骤 5：生成并人工确认 5 份提纲**

```bash
python -m evals.chinese_reliability.prepare_simple_outlines
```

逐题核对：ID 和题目一致、章节 3 至 5 个、标题不重复、无明显偏题。只允许在运行 A/B 前修改章节标题或描述；开始实验后冻结该文件。

- [ ] **步骤 6：串行运行完整 A/B 实验**

按任务 5 README 中的命令分别运行 baseline 和 enhanced。每组结束后检查：

```bash
cat outputs/evals/chinese_reliability/simple-ab/baseline/summary.md
cat outputs/evals/chinese_reliability/simple-ab/outline/summary.md
wc -l outputs/evals/chinese_reliability/simple-ab/baseline/runs.jsonl
wc -l outputs/evals/chinese_reliability/simple-ab/outline/runs.jsonl
```

预期：两组 `runs.jsonl` 都恰好 5 行；失败项仍在文件中；两份摘要均包含成功率、有效引用率、平均耗时、平均成本和提纲覆盖率。

- [ ] **步骤 7：计算作品集可用的相对变化**

运行自动对比命令：

```bash
python -m evals.chinese_reliability.compare_ab \
  --baseline outputs/evals/chinese_reliability/simple-ab/baseline/summary-simple.json \
  --enhanced outputs/evals/chinese_reliability/simple-ab/outline/summary-simple.json \
  --output-dir outputs/evals/chinese_reliability/simple-ab/comparison
cat outputs/evals/chinese_reliability/simple-ab/comparison/comparison.md
```

脚本以 baseline 为分母，计算：

```text
成功率变化 = 提纲组成功率 - 基线成功率
有效引用率相对变化 = (提纲组 - 基线) / 基线
平均耗时相对变化 = (提纲组 - 基线) / 基线
平均成本相对变化 = (提纲组 - 基线) / 基线
提纲覆盖率 = 提纲组有效覆盖章节 / 提纲组确认章节
```

实验结论必须同时报告收益和代价。例如：结构覆盖率提高，但耗时增加；不得只选择表现更好的题目。

- [ ] **步骤 8：提交最终代码状态，不提交实验原始输出**

```bash
git status --short
git log --oneline --decorate -6
```

若前面每个任务都已提交且工作区干净，本步骤不产生新提交；A/B 原始报告继续只保存在服务器 `outputs/`。

**本任务预期效果：** 获得一个可演示的求职项目功能，以及一份可复现的量化对照结果。最终可以基于真实数据描述“新增用户可确认提纲的两阶段研究流程，并在 5 道中文任务上测得结构覆盖、引用可靠性、耗时与成本变化”。
