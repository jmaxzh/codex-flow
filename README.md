# Codex 配置驱动工作流编排（Prefect）

`scripts/codex_automation_loops.py` 是通用编排引擎：

- 启动时通过 `--preset` 选择预设模板（必选）
- 支持通过命令行注入并覆盖预设中的上下文默认值
- 不再内置 `implement/review/check/fix` 固定阶段语义
- 节点路由仅由 `pass` 与 `on_success/on_failure` 决定
- 节点只写入 `outputs.<node_id>`；边上的 `route_bindings` 负责把结果绑定到运行时上下文供下游读取
- 支持节点级 `collect_history_to`：将该节点每轮完整输出按顺序追加到 `context.runtime.*` 历史数组

## 运行方式

```bash
python3 scripts/codex_automation_loops.py --preset implement_loop
```

新增重构循环预设：

```bash
python3 scripts/codex_automation_loops.py --preset refactor_loop
```

新增 reviewer 循环预设（仅 `bug_reviwer`，由引擎收集每轮完整评审输出历史）：

```bash
python3 scripts/codex_automation_loops.py --preset reviewer_loop
```

`refactor_loop` 内的评审角色已命名为 `arch_reviwer`（与 `refactor` 迭代，不使用 fix 角色）。

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
        {{ prompt_file("./prompts/shared/implementer_role.md") }}
        最后一行输出严格 JSON object（不要使用代码块），至少包含：
        {
          "pass": true/false,
          "change_summary": "..."
        }
        首轮指令: {{ inputs.user_instruction }}
        规格: {{ inputs.spec }}
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
        {{ prompt_file("./prompts/shared/implementer_checker_role.md") }}
        若全部完成，pass=true 且 todo 为空数组。
        若未完成，pass=false 且 todo 给出剩余待办（字符串数组）。
        最后一行输出严格 JSON object（不要使用代码块），至少包含：
        {
          "pass": true/false,
          "verification": "...",
          "todo": ["..."]
        }
        实现输出: {{ inputs.latest_impl }}
      input_map:
        latest_impl: context.runtime.latest_impl
      collect_history_to: context.runtime.check_history
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

可选 `collect_history_to` 在节点执行后追加历史，用于收集该节点每轮完整输出：

```yaml
collect_history_to: context.runtime.review_history
```

- 目标路径必须以 `context.runtime.` 开头
- 路径不存在时自动初始化为 `[]`
- 每轮 append 当前节点完整 JSON 输出（不去重，不改写原输出）

## 输入映射规则

`input_map` 只允许引用：

- `context.defaults.*`
- `context.runtime.*`
- `outputs.*`

`outputs.<node_id>` 始终是该节点完整 JSON 输出（原样透传）。
`context.runtime.*` 由编排层通过 `route_bindings` 更新，不改变节点输出归属。

## Prompt 模板与 `prompt_file(...)`

节点 `prompt` 使用 Jinja2 统一渲染：`{{ inputs.* }}` 与 `{{ prompt_file("...") }}` 在同一渲染流程完成。

- 语法：`{{ prompt_file("<relative_path>") }}`
- 路径基准：相对当前 workflow 配置文件目录（不是 `cwd`，也不是 `run.project_root`）
- 仅允许非空相对路径，拒绝绝对路径
- 允许 `..`，按常规相对路径解析
- include 文件按 UTF-8 读取
- 建议普通用户始终使用字符串字面量相对路径
- 建议组织方式：仅将可复用 role 文本拆分到文件；输出协议保留在节点 `prompt` 配置中

最小示例（role include + 输出协议内联 + inputs 变量共存）：

```yaml
prompt: |
  {{ prompt_file("./prompts/shared/implementer_role.md") }}
  最后一行输出严格 JSON object（不要使用代码块），至少包含：
  {
    "pass": true/false,
    "change_summary": "..."
  }
  首轮指令: {{ inputs.user_instruction }}
  规格: {{ inputs.spec }}
```

固定边界（保持实现极简）：

- 不支持旧语法兼容（如 `{{prompt_file:./x.md}}`）
- 不做递归 include 检测
- 不做 include 内容二次模板渲染（include 文件里的 `{{ ... }}` 按文本保留）
- 不为动态/表达式路径参数提供兼容承诺
- 不引入复杂路径安全策略（固定仓库根、symlink 越界防护等）

如果需要在主模板里输出字面量 `{{ ... }}`，可使用 Jinja2 `raw` 块：

```jinja
{% raw %}{{ inputs.example }}{% endraw %}
```

旧语法手动迁移最小清单：

1. 把 `{{prompt_file:./path/to/file.md}}` 替换为 `{{ prompt_file("./path/to/file.md") }}`
2. 确认路径是“相对配置文件目录”的相对路径
3. 确认 include 文件按 UTF-8 可读取
4. 检查 include 文件中是否有 `{{ ... }}`，若有则按文本保留或挪回主模板处理

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
- [presets/reviewer_loop.yaml](./presets/reviewer_loop.yaml)
