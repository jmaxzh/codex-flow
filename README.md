# Codex 配置驱动工作流编排（Prefect）

`scripts/codex_automation_loops.py` 已改为通用编排引擎：

- 启动只读取当前目录 `./orchestrator.yaml`
- 不再接受业务 CLI 参数
- 不再内置 `implement/review/check/fix` 固定阶段语义
- 节点路由仅由 `pass` 与 `on_success/on_failure` 决定

## 运行方式

```bash
python3 scripts/codex_automation_loops.py
```

运行前请确保：

1. 使用当前系统 `python3.13` 安装依赖（不创建虚拟环境）：

   ```bash
   python3.13 -m pip install --break-system-packages --user -r requirements.txt
   ```

2. 当前目录存在 `orchestrator.yaml`
3. `run.project_root` 指向有效项目目录

## 配置 DSL

```yaml
version: 1

run:
  project_root: /abs/path/to/target
  state_dir: .codex-loop-state
  max_steps: 50

executor:
  cmd: ["codex", "exec", "--skip-git-repo-check"]

context:
  static:
    spec: "docs/xxx.md"

workflow:
  start: plan
  nodes:
    - id: plan
      prompt: |
        输入: {{inputs.spec}}
        输出 JSON object，必须包含 pass:boolean
      input_map:
        spec: context.static.spec
      on_success: implement
      on_failure: END

    - id: implement
      prompt: |
        规划输出: {{inputs.plan_output}}
        输出 JSON object，必须包含 pass:boolean
      input_map:
        plan_output: outputs.plan
      on_success: END
      on_failure: END
```

## 固定输出契约

每个节点的模型输出必须满足：

1. 可解析为 JSON
2. 顶层为 JSON object
3. 必含 `pass` 字段
4. `pass` 必须是 boolean

## 路由规则

- `pass=true` -> `on_success`
- `pass=false` -> `on_failure`
- `END` -> 结束流程
- 示例默认采用显式 fail-fast：失败分支直接路由到 `END`

## 输入映射规则

`input_map` 只允许引用：

- `context.static.*`
- `outputs.*`

`outputs.<node_id>` 始终是该节点完整 JSON 输出（原样透传）。

## 状态与日志

默认写入 `run.state_dir`：

- `logs/workflow__<timestamp>/`：每次 `codex exec` 的完整控制台日志
- `stepXXX__<node>__attemptYY__raw.txt`：节点原始输出
- `stepXXX__<node>__attemptYY__prompt.txt`：渲染后提示词
- `stepXXX__<node>__attemptYY__parsed.json`：解析后 JSON
- `stepXXX__<node>__attemptYY__meta.json`：step 元信息（step/node_id/attempt/next_node 等）
- `history.jsonl`：逐步执行历史
- `runtime_state.json`：最近状态快照
- `run_summary.json`：最终汇总

## 示例配置

仓库根目录提供了一个可直接改造的示例：[orchestrator.yaml](./orchestrator.yaml)。
