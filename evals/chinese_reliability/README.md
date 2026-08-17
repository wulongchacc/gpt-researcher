# 中文报告可靠性评测

该工具使用固定的 5 道 Simple 题目和 5 道 Deep Research 题目，分别记录报告成功率、有效引用率、耗时和 API 成本。Simple A/B 实验还记录提纲章节覆盖率，并将提纲生成耗时和成本计入实验组总指标。

## 成功标准

- Simple：报告不少于 400 字，且至少包含 2 个有效来源。
- Deep：报告不少于 1500 字，且至少包含 5 个有效来源。
- 有效来源：规范化、去重后可访问，HTTP 状态为 2xx，前 4096 字节中至少读取到 200 字节内容。
- 401、403 和 429 单独标记为 `blocked`，不计入有效来源。

## Simple 提纲 A/B 实验

所有命令均从仓库根目录执行。先生成 5 份 Simple 提纲：

```bash
python -m evals.chinese_reliability.prepare_simple_outlines
```

检查 `outputs/evals/chinese_reliability/simple-outlines.json`，确认每题 ID 和题目一致、包含 3 至 5 个不重复且未偏题的章节。可在实验开始前修改标题和描述；开始运行 A/B 后必须冻结该文件。

运行 5 道无提纲 Simple 基线：

```bash
python -m evals.chinese_reliability.run_benchmark \
  --mode baseline \
  --ids simple-01 simple-02 simple-03 simple-04 simple-05 \
  --output-dir outputs/evals/chinese_reliability/simple-ab/baseline
```

运行同一批题目的确认提纲实验组：

```bash
python -m evals.chinese_reliability.run_benchmark \
  --mode enhanced \
  --ids simple-01 simple-02 simple-03 simple-04 simple-05 \
  --outlines outputs/evals/chinese_reliability/simple-outlines.json \
  --output-dir outputs/evals/chinese_reliability/simple-ab/outline
```

生成量化对比：

```bash
python -m evals.chinese_reliability.compare_ab \
  --baseline outputs/evals/chinese_reliability/simple-ab/baseline/summary-simple.json \
  --enhanced outputs/evals/chinese_reliability/simple-ab/outline/summary-simple.json \
  --output-dir outputs/evals/chinese_reliability/simple-ab/comparison
```

两组题目、搜索器、抓取器、向量模型和最大搜索结果数必须一致。脚本串行执行题目，并在每题结束后写入结果，避免单题失败导致整批数据丢失；失败题不会被自动补跑或从结果中删除。

## 原有混合模式评测

如需复现包含 Simple 与 Deep 的原始基线，可执行：

```bash
python -m evals.chinese_reliability.run_benchmark \
  --mode baseline \
  --output-dir outputs/evals/chinese_reliability/baseline
```

Docker Compose 已将 `outputs` 映射到服务器宿主机，因此容器重建后结果仍然保留。

## 输出

- `reports/*.md`：完整报告。
- `runs.jsonl`：每题结构化指标，不重复保存完整报告。
- `summary.json`：整体及分模式汇总。
- `summary-simple.json`：Simple 汇总。
- `summary-deep.json`：Deep 汇总。
- `summary.md`：可直接阅读的对比表。
- `simple-outlines.json`：人工确认并在实验前冻结的 Simple 提纲。
- `comparison/comparison.json`：A/B 原始指标及变化值。
- `comparison/comparison.md`：可用于作品集展示的 A/B 对比表。

结果目录不应提交 API Key。完整报告和原始运行结果默认只保留在实验机器上。
