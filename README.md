# Codex Native Prefect 工作流编排

`scripts/codex_automation_loops.py` 基于 Prefect + native Python flow 注册表运行，不再加载/编译 YAML DSL preset。

## 快速开始

```bash
python3 scripts/codex_automation_loops.py --preset openspec_implement
```

带上下文覆盖（可重复 `--context`，同 key 后写覆盖前写）：

```bash
python3 scripts/codex_automation_loops.py \
  --preset openspec_implement \
  --context spec docs/new-spec.md \
  --context user_instruction "请先完成 API 层"
```

## 可用内置 Preset

- `openspec_implement`
- `openspec_propose`
- `refactor_loop`
- `reviewer_loop`
- `doc_reviewer_loop`

## 文档导航

详细规范已迁移到 `docs/specs`。README 只保留入口信息，避免与规范文档重复。

- native flow 与编排迁移：`docs/specs/native-prefect-preset-orchestration/spec.md`
- preset 标识符解析与校验：`docs/specs/preset-enum-resolution/spec.md`
- 节点输出（`result/control`）契约：`docs/specs/node-output-contract/spec.md`
- prompt 文件引用与渲染规则：`docs/specs/prompt-file-reference/spec.md`
- `openspec_propose` 预设语义：`docs/specs/openspec-propose-preset/spec.md`
- workflow 组合/弃用字段约束：`docs/specs/preset-workflow-composition/spec.md`
- Python 质量门禁规范：`docs/specs/python-quality-gate/spec.md`

## 运行产物（概览）

默认状态目录：`<launch_cwd>/.codex-loop-state/`

- `runs/<run_id>/`：单次 run 目录
- `runs/<run_id>/logs/`：`codex exec` 控制台日志
- `runs/<run_id>/history.jsonl`：step 元信息流水
- `runs/<run_id>/runtime_state.json`：运行时状态快照
- `runs/<run_id>/run_summary.json`：run 汇总
- `latest_run_id` / `latest_run.json`：最近一次 run 索引

## 依赖安装与本地验证

安装依赖（系统 Python 3.13）：

```bash
python3.13 -m pip install --break-system-packages --user -r requirements.txt
```

运行测试：

```bash
python3 -m pytest -q
```

安装并执行 Git hooks（pre-commit + pre-push）：

```bash
./scripts/setup_hooks.sh
```

## 迁移说明

- `--preset` 接受内置 preset 标识符，不接受 YAML 路径
- 旧名称 `implement_loop` / `doc_doctor` 已移除，传入时会报 unknown preset 并显示新可用列表
- `workflow.imports` / `node_overrides` 等旧 YAML DSL 组合能力已移除
- 现有行为以 `scripts/_codex_orchestrator/native_workflows/` 与 `docs/specs/` 为准
