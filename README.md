# codex-cli 自动闭环脚本（Fast-Fail / 极简字段）

`scripts/codex_automation_loops.py` 提供两个独立循环：

1. `implement-loop`：实施 → 检查 → 继续实施
2. `review-loop`：review → 修复 → review

## 核心约束

- 只接受 **严格 JSON** 输出。
- 解析失败、缺字段、字段类型错误：**立即失败退出**（fast-fail）。
- 不做 fallback、兼容解析、兜底。

## 最小数据契约

### 实现闭环（implement/check）

- 检查步骤只输出：

```json
{"todo": ["item || reason"]}
```

- 含义：`todo` 同时覆盖“未完成项 + 偏差项”。
- 结束条件：`{"todo":[]}`。

### review/fix 闭环

- review 步骤只输出：

```json
{"issues": ["..."]}
```

- 修复步骤接收 `issues` 列表。
- 结束条件：`{"issues":[]}`。

## 审查对象绑定

`review-loop` 每轮会先生成 `scope.diff`，包含以下全部变更，并传入 review 提示词：

- 未跟踪（untracked）文件
- 暂存区（staged）变更
- 工作区未暂存（unstaged）变更

- 若 `scope.diff` 为空：立即失败退出。

## 提示词文件

`prompts/` 下为独立模板：

- `implement_initial.prompt.txt`
- `implement_continue.prompt.txt`
- `check.prompt.txt`
- `review.prompt.txt`
- `fix.prompt.txt`

## 用法

```bash
# 实现闭环
python3 scripts/codex_automation_loops.py implement-loop --spec docs/xxx.md

# review/fix 闭环
python3 scripts/codex_automation_loops.py review-loop

# 顺序执行两套闭环
python3 scripts/codex_automation_loops.py all --spec docs/xxx.md
```

可选参数：

- `--state-dir`（默认 `.codex-loop-state`）
- `--max-iterations`（默认 `20`）
- `--prompt-dir`（默认 `prompts`）
- `--codex-cmd`（默认 `CODEX_CMD` 或 `codex-cli`）

## CODEX_CMD

支持占位符：

- `{PROMPT}`：完整提示词文本
- `{PROMPT_FILE}`：提示词文件路径

如果 `CODEX_CMD` 未使用占位符，脚本会先执行 `<codex_cmd> --help` 自动识别参数：

- 若存在 `--prompt-file`，使用 `--prompt-file <path>`
- 否则若存在 `--prompt`，使用 `--prompt <text>`
- 两者都不存在则立即失败退出（fast-fail）

示例：

```bash
CODEX_CMD='codex-cli run --non-interactive --prompt-file {PROMPT_FILE}' \
  python3 scripts/codex_automation_loops.py all --spec docs/xxx.md
```
