# Codex 配置驱动工作流编排（Prefect）

`scripts/codex_automation_loops.py` 是通用编排引擎：

- 启动时通过 `--preset` 选择预设模板（必选）
- 支持通过命令行注入并覆盖预设中的上下文默认值
- 不再内置 `implement/review/check/fix` 固定阶段语义
- 节点路由仅由 `pass` 与 `on_success/on_failure` 决定
- 节点只写入 `outputs.<node_id>`；边上的 `route_bindings` 负责把结果绑定到运行时上下文供下游读取

## 运行方式

```bash
python3 scripts/codex_automation_loops.py --preset implement_loop
```

新增重构循环预设：

```bash
python3 scripts/codex_automation_loops.py --preset refactor_loop
```

带上下文注入覆盖示例（可重复 `--context`）：

```bash
python3 scripts/codex_automation_loops.py \
  --preset implement_loop \
  --context spec docs/new-spec.md \
  --context user_instruction "请先完成 API 层"
```

运行前请确保：

1. 使用当前系统 `python3.13` 安装依赖（不创建虚拟环境）：

   ```bash
   python3.13 -m pip install --break-system-packages --user -r requirements.txt
   ```

2. 预设文件存在于 `presets/` 下，或 `--preset` 指向有效文件路径
3. `run.project_root` 指向有效项目目录

## CLI 参数

- `--preset <name-or-path>`（必选）
  - 不包含路径分隔符时，解析为 `./presets/<name>.yaml`
  - 包含路径分隔符时，按给定路径解析（相对当前目录或绝对路径）
- `--context <key> <value>`（可选，可重复）
  - 仅支持扁平键值注入
  - `key` 不允许包含 `.`，不允许嵌套对象
  - 同 key 出现多次时，后者覆盖前者

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
  defaults:
    spec: "docs/xxx.md"
    user_instruction: "根据 spec 进行首轮实现"

workflow:
  start: implement_first
  nodes:
    - id: implement_first
      prompt: |
        首轮指令: {{inputs.user_instruction}}
        规格: {{inputs.spec}}
        最后一行输出严格 JSON object，必须包含 pass:boolean
      input_map:
        user_instruction: context.defaults.user_instruction
        spec: context.defaults.spec
      on_success: check
      on_failure: END
      route_bindings:
        success:
          context.runtime.latest_impl: outputs.implement_first

    - id: check
      prompt: |
        实现输出: {{inputs.latest_impl}}
        最后一行输出严格 JSON object，必须包含 pass:boolean
      input_map:
        latest_impl: context.runtime.latest_impl
      on_success: END
      on_failure: implement_loop
      route_bindings:
        failure:
          context.runtime.latest_check: outputs.check
```

`context.defaults` 是预设中的默认输入。运行时若传入 `--context key value`，会覆盖同名默认值；未注入的 key 继续使用预设默认值。

## 固定输出潜规则

每个节点的模型输出必须满足：

1. 只解析输出的最后一个非空行（即最后一行有效内容）
2. 该行必须是可解析的严格 JSON
3. 顶层必须是 JSON object
4. 必含 `pass` 字段
5. `pass` 必须是 boolean

## 路由规则

- `pass=true` -> `on_success`
- `pass=false` -> `on_failure`
- `END` -> 结束流程
- 示例默认采用显式 fail-fast：失败分支直接路由到 `END`

可选 `route_bindings` 在边上执行，用于把来源值写入 `context.runtime.*`：

```yaml
route_bindings:
  success:
    context.runtime.latest_impl: outputs.implement_first
  failure:
    context.runtime.latest_check: outputs.check
```

## 输入映射规则

`input_map` 只允许引用：

- `context.defaults.*`
- `context.runtime.*`
- `outputs.*`

`outputs.<node_id>` 始终是该节点完整 JSON 输出（原样透传）。
`context.runtime.*` 由编排层通过 `route_bindings` 更新，不改变节点输出归属。

## 状态与日志

默认写入 `run.state_dir`：

- `logs/workflow__<timestamp>/`：每次 `codex exec` 的完整控制台日志
- `stepXXX__<node>__attemptYY__raw.txt`：节点原始输出
- `stepXXX__<node>__attemptYY__prompt.txt`：渲染后提示词
- `stepXXX__<node>__attemptYY__parsed.json`：解析后 JSON
- `stepXXX__<node>__attemptYY__meta.json`：step 元信息（step/node_id/attempt/next_node/applied_route_bindings 等）
- `history.jsonl`：逐步执行历史
- `runtime_state.json`：最近状态快照（包含 `context.defaults`/`context.runtime`、`outputs`、`attempt_counter`）
- `run_summary.json`：最终汇总

## 示例配置

仓库根目录提供了可直接改造的示例：

- [presets/implement_loop.yaml](./presets/implement_loop.yaml)
- [presets/refactor_loop.yaml](./presets/refactor_loop.yaml)
