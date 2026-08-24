# 来源可靠性改造前实验快照

## 1. 用途

本快照用于封存来源可靠性改造前的原始实验产物，防止后续评测覆盖历史结果，并为最终 A/B 对照和简历数据提供可追溯依据。

快照基准日期为 2026-08-21。原始产物位于云服务器，本地仓库不包含被 `.gitignore` 排除的 `outputs/` 目录。

## 2. 已知实验目录

服务器当前需要封存以下目录：

```text
outputs/evals/chinese_reliability/baseline-complete
outputs/evals/chinese_reliability/baseline-remaining
outputs/evals/chinese_reliability/historical-baseline-20260807
outputs/evals/chinese_reliability/simple-ab/outline-20260818
outputs/evals/chinese_reliability/simple-ab/restricted-3plus-original-20260819
outputs/evals/chinese_reliability/smoke
```

若某个目录不存在，归档命令会在清单中记录 `MISSING`，不会创建空实验结果冒充原始数据。

## 3. 已确认指标

当前对最终报告实际 Markdown 链接重新计算后，已确认：

| 组别 | 报告成功率 | 实际引用 | 有效引用 | 有效引用率 | 平均耗时 | 平均成本 |
|---|---:|---:|---:|---:|---:|---:|
| 历史 Simple 基线 | 60.0% | 21 | 20 | 95.2% | 132.8 秒 | $0.0808 |
| 最新提纲实验 | 40.0% | 16 | 7 | 43.8% | 192.0 秒 | $0.0869 |

最新提纲实验的已知无效状态包括 404、网络错误、超时和编码错误。表中数据只用于人工核对；最终以封存的原始 JSON、Markdown 报告和 SHA-256 清单为准。

## 4. 服务器封存命令

在云服务器项目目录执行：

```bash
cd ~/apps/gpt-researcher

snapshot_name="pre-source-reliability-20260821"
snapshot_dir="$HOME/backups/gpt-researcher/$snapshot_name"
mkdir -p "$snapshot_dir"

git rev-parse HEAD > "$snapshot_dir/GIT_COMMIT"
git branch --show-current > "$snapshot_dir/GIT_BRANCH"
date -Iseconds > "$snapshot_dir/CREATED_AT"

paths=(
  outputs/evals/chinese_reliability/baseline-complete
  outputs/evals/chinese_reliability/baseline-remaining
  outputs/evals/chinese_reliability/historical-baseline-20260807
  outputs/evals/chinese_reliability/simple-ab/outline-20260818
  outputs/evals/chinese_reliability/simple-ab/restricted-3plus-original-20260819
  outputs/evals/chinese_reliability/smoke
)

: > "$snapshot_dir/PATHS"
existing_paths=()
for path in "${paths[@]}"; do
  if [ -d "$path" ]; then
    printf 'FOUND %s\n' "$path" >> "$snapshot_dir/PATHS"
    existing_paths+=("$path")
  else
    printf 'MISSING %s\n' "$path" >> "$snapshot_dir/PATHS"
  fi
done

if [ "${#existing_paths[@]}" -eq 0 ]; then
  echo "No experiment directories found; snapshot aborted." >&2
  exit 1
fi

find "${existing_paths[@]}" -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  > "$snapshot_dir/SHA256SUMS"

tar -czf "$snapshot_dir/results.tar.gz" "${existing_paths[@]}"
sha256sum "$snapshot_dir/results.tar.gz" \
  > "$snapshot_dir/results.tar.gz.sha256"

chmod -R a-w "$snapshot_dir"

echo "Snapshot: $snapshot_dir"
cat "$snapshot_dir/PATHS"
cat "$snapshot_dir/results.tar.gz.sha256"
```

该命令不会读取或复制 `.env`，因此不会把 API Key 放入归档。

## 5. 完成判定

出现以下三项即可认为原始结果已封存：

1. `PATHS` 至少包含一个 `FOUND`，且缺失目录被明确记录。
2. `SHA256SUMS` 包含归档内每个原始文件的校验值。
3. `results.tar.gz.sha256` 包含压缩包校验值，且快照目录已变为只读。

验证压缩包：

```bash
cd ~/backups/gpt-researcher/pre-source-reliability-20260821
sha256sum -c results.tar.gz.sha256
tar -tzf results.tar.gz | head -30
```

预期第一条命令输出：

```text
results.tar.gz: OK
```
