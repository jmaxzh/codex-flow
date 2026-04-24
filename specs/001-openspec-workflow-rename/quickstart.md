# Quickstart: OpenSpec Workflow Rename

## 1. 执行新预设名称

```bash
python3 scripts/codex_automation_loops.py --preset openspec_implement
python3 scripts/codex_automation_loops.py --preset openspec_propose
```

预期结果：工作流可正常解析并进入 native flow 运行路径，且无需旧名称。

## 2. 验证旧名称迁移行为

```bash
python3 scripts/codex_automation_loops.py --preset implement_loop
python3 scripts/codex_automation_loops.py --preset doc_doctor
```

预期结果：返回 unknown preset 错误，并在可用列表中显示新名称。

## 3. 验证模板外置资产可独立维护

1. 编辑 `presets/prompts/openspec_implement*.md` 任一模板文本。
2. 重新运行 `--preset openspec_implement`。
3. 确认运行使用新模板内容，且无需修改 `presets.py`。

同理对 `openspec_propose` 执行一次。

## 4. 重点回归（T026）

执行命令：

```bash
python3 -m pytest -q tests/codex_orchestrator_cases_config.py tests/codex_orchestrator_cases_presets_cli.py tests/codex_orchestrator_cases_runtime.py tests/codex_orchestrator_cases_prompt.py
```

结果记录：`37 passed`（有 Prefect logger warning，不影响断言结果）。

## 5. 旧标识残留扫描（T025）

执行命令：

```bash
rg -n "\bimplement_loop\b|\bdoc_doctor\b" scripts tests docs/specs README.md specs/001-openspec-workflow-rename/quickstart.md
```

结果结论：旧标识仅出现在迁移允许位置：

- 迁移说明与示例：`README.md`、本 quickstart 第 2 节
- 迁移行为测试：`tests/codex_orchestrator_cases_presets_cli.py`
- 迁移契约场景：`docs/specs/preset-enum-resolution/spec.md`

无“仍作为主入口”的残留。

## 6. 质量门禁（T027）

执行命令与结果：

```bash
ruff check scripts tests
# All checks passed!

ruff format scripts tests
# 25 files left unchanged

basedpyright --warnings scripts tests
# 0 errors, 0 warnings, 0 notes

python3 -m pytest -q
# 52 passed, 30 warnings in 4.90s
```

备注：pytest 结束后有 Prefect 停服阶段 logging error（I/O operation on closed file），不影响测试断言与退出码（0）。
