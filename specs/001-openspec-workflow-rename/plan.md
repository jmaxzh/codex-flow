# Implementation Plan: OpenSpec Workflow Rename

**Branch**: `[002-refactor-openspec-workflows]` | **Date**: 2026-04-22 | **Spec**: [specs/001-openspec-workflow-rename/spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-openspec-workflow-rename/spec.md`

## Summary

将两个内置预设工作流统一重命名为 `openspec_implement` 与 `openspec_propose`，并把其提示词模板从
`scripts/_codex_orchestrator/native_workflows/presets.py` 内嵌文本迁移到 `presets/prompts/` 独立文件。
实现路径覆盖 CLI 入口、原生工作流注册、运行时模板加载、测试断言与 `docs/specs/` 契约文档，
同时明确旧名称（`implement_loop`/`doc_doctor`）行为为“拒绝并提供可用新名称提示”。

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: Prefect（flow/task 装饰器与运行入口）、Jinja2（模板渲染与 `prompt_file(...)`）、pytest + unittest  
**Storage**: 文件系统（`presets/prompts/` 模板资产、`.codex-loop-state/` 运行产物）  
**Testing**: `python3 -m pytest -q`（`tests/codex_orchestrator_cases_*.py`）+ `ruff` + `basedpyright`  
**Target Platform**: 本地 CLI（macOS/Linux shell）  
**Project Type**: 单仓库 Python CLI/编排运行时  
**Performance Goals**: 不增加既有节点执行次数；循环类预设继续受 `run.max_steps` 硬上限约束  
**Constraints**: 严格类型检查；模板路径必须稳定且可复现；工作流契约在 `docs/specs/` 保持一致  
**Scale/Scope**: 2 个目标预设、`native_workflows` 核心模块、CLI 参数校验、相关测试与规范文档

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Gate

- [x] Spec-first 范围已定义并可追溯到 `specs/001-openspec-workflow-rename/spec.md`。
- [x] 已识别契约影响：`--preset` 可调用标识、注册表键、模板资产路径、未知预设错误提示、`docs/specs/` 文档更新。
- [x] 已规划质量门禁：`ruff check scripts tests`、`ruff format scripts tests`、`basedpyright --warnings scripts tests`、`python3 -m pytest -q`。
- [x] 已规划行为测试证据：`tests/codex_orchestrator_cases_config.py`、`tests/codex_orchestrator_cases_presets_cli.py`、`tests/codex_orchestrator_cases_runtime.py`、`tests/codex_orchestrator_cases_prompt.py`。
- [x] 已记录运行产物影响：`.codex-loop-state/` 内节点输出键与步骤文件名前缀将随新节点标识变化；目录结构保持不变。

**Gate Result**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/001-openspec-workflow-rename/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── preset-workflow-contract.md
└── tasks.md                # 由 /speckit.tasks 后续生成
```

### Source Code (repository root)

```text
scripts/
├── codex_automation_loops.py
└── _codex_orchestrator/
    └── native_workflows/
        ├── presets.py
        ├── registry.py
        └── runtime.py

presets/
└── prompts/
    ├── shared/
    ├── openspec_implement_*.md
    └── openspec_propose_*.md

tests/
├── test_codex_orchestrator.py
└── codex_orchestrator_cases_*.py

docs/
└── specs/
    ├── native-prefect-preset-orchestration/
    ├── preset-enum-resolution/
    └── doc-doctor-preset/
```

**Structure Decision**: 采用现有单项目结构，在既有模块内完成重命名与模板资产迁移，不新增运行时子系统。

## Phase 0: Research

研究输出见 [research.md](./research.md)。本阶段已收敛以下关键决策：

1. 旧名称输入策略：拒绝旧名称并在错误信息中列出新可用标识，避免隐式别名导致长期双轨维护。
2. 模板外置策略：为目标预设节点建立独立模板文件，`presets.py` 仅保留流程装配与 `prompt_file(...)` 引用。
3. 命名一致性策略：代码符号、注册键、模板资产名、测试断言、文档入口统一使用 `openspec_implement*` / `openspec_propose*` 前缀。
4. 契约更新策略：同步更新 `docs/specs/` 中与预设标识相关的场景与迁移说明。

## Phase 1: Design & Contracts

### Design Artifacts

- 数据模型: [data-model.md](./data-model.md)
- 接口契约: [contracts/preset-workflow-contract.md](./contracts/preset-workflow-contract.md)
- 验证说明: [quickstart.md](./quickstart.md)

### Agent Context Update

`AGENTS.md` 中 `<!-- SPECKIT START --> ... <!-- SPECKIT END -->` 已更新为指向
`specs/001-openspec-workflow-rename/plan.md`。

### Post-Design Constitution Check

- [x] 设计产物覆盖契约变更（CLI 标识、注册映射、模板资产加载、错误路径）。
- [x] 质量门禁命令在 quickstart 中可直接执行。
- [x] 测试覆盖点按行为划分并映射到现有 `codex_orchestrator_cases_*`。
- [x] `.codex-loop-state/` 产物命名影响在契约中已显式记录。

**Gate Result**: PASS

## Phase 2: Implementation Planning Approach

1. 重命名与注册迁移：`registry.py` 与 `presets.py` 的函数/键/节点标识统一迁移到新命名。
2. 模板资产迁移：新增 `presets/prompts/openspec_implement_*.md`、`presets/prompts/openspec_propose_*.md`，删除目标预设内嵌模板正文。
3. CLI 与错误语义：`scripts/codex_automation_loops.py` 帮助文本及未知预设提示与新标识一致，旧名输入走未知预设错误路径。
4. 测试与文档同步：更新相关测试断言与 `docs/specs/` 场景描述，覆盖模板缺失、旧名称、新名称可执行路径。
5. 全量验证：执行 lint/format/type/test 四类门禁并记录结果。

## Complexity Tracking

无宪章违规项，无需豁免记录。
