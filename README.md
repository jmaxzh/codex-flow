# codex 自动闭环脚本（Fast-Fail / 极简字段）

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

`review-loop` 每轮直接审查目标项目当前工作区变更，不再通过 `scope.diff` 注入完整代码差异。

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
python3 scripts/codex_automation_loops.py implement-loop --project-root /path/to/target --spec docs/xxx.md
python3 scripts/codex_automation_loops.py implement-loop --project-root /path/to/target --spec openspec/changes/xxx

# 实现闭环（注入额外提示词）
python3 scripts/codex_automation_loops.py implement-loop --project-root /path/to/target --spec docs/xxx.md \
  --implement-extra-prompt "使用 skill openspec-apply-change，按 tasks.md 逐项实现"

# review/fix 闭环
python3 scripts/codex_automation_loops.py review-loop --project-root /path/to/target

# 顺序执行两套闭环
python3 scripts/codex_automation_loops.py all --project-root /path/to/target --spec docs/xxx.md
```

可选参数：

- `--project-root`（默认当前目录；所有 git/codex 在该目录执行）
- `--state-dir`（默认 `.codex-loop-state`）
- `--max-iterations`（默认 `20`）
- `--prompt-dir`（默认脚本内置 `prompts/` 绝对路径；也可传相对 `project-root` 的路径）
- `--implement-extra-prompt`（仅 `implement-loop` / `all`；注入到 `implement_initial.prompt.txt` 的 `${implement_extra_prompt}`）
- `--spec`（仅 `implement-loop` / `all`；支持文件或目录，不做类型校验）

## 固定执行命令

脚本已固定调用本机 `codex` 的非交互模式：

```bash
codex exec --skip-git-repo-check --cd <project-root> --output-last-message <out-file> -
```

提示词通过 stdin 传入，最终回答写入 `<out-file>`，并按严格 JSON 解析。
