# SDD Agent Integration

本文档说明如何把本仓库接入 Codex、Gemini CLI、OpenCode 一类 agent，供项目组成员复用统一的 SDD 工作流。

## 推荐接入形态

SDD 不建议只作为一段提示词接入 agent。推荐拆成三层：

1. Skill / 指令层
   - 负责告诉 agent 按什么流程工作。
   - 对应本仓库的 `skills/` 与 `templates/*/AGENTS.md`、`templates/gemini/GEMINI.md`。

2. MCP 工具层
   - 负责给 agent 暴露可调用工具。
   - 当前已提供：
     - `mcp-servers/project-explorer`
     - `mcp-servers/arch-standard`
     - `mcp-servers/sdd-pipeline`

3. Pipeline 执行层
   - 负责真实生成、校验和刷新产物。
   - 当前入口是 `python scripts/run_pipeline.py ...`。

推荐调用链：

```text
Agent -> Skill/Prompt -> MCP tools -> run_pipeline.py -> specs/.spec reports
```

## 本地源码版接入

第一阶段先使用本地源码版接入，不要求发布 npm 包。

### 前置检查

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/doctor.ps1
```

该脚本会检查：

- Python / Node.js / Java 工具链
- `run_pipeline.py`
- `skills/` 目录
- 三个 MCP Server 的 `dist/server.js`
- 当前附着项目配置
- MCP CLI smoke test
- 内置 Gate smoke fixture 的 release gate / reports 校验

### MCP Server

当前建议挂载三个 MCP：

```json
{
  "mcpServers": {
    "sdd-project-explorer": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\project-explorer\\dist\\server.js"
      ]
    },
    "sdd-arch-standard": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\arch-standard\\dist\\server.js"
      ]
    },
    "sdd-pipeline": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\sdd-pipeline\\dist\\server.js"
      ]
    }
  }
}
```

如果团队成员本地路径不同，把 `D:\\project\\SDD` 替换为自己的 SDD 仓库路径。

## Codex

参考模板：

- `templates/codex/config.example.toml`
- `templates/codex/AGENTS.md`

建议做法：

1. 把 `config.example.toml` 中的 MCP 配置合并到自己的 Codex 配置。
2. 把 `templates/codex/AGENTS.md` 的内容放到业务项目或 SDD 工作区根目录的 `AGENTS.md`。
3. 在 agent 里验证 MCP 工具：
   - `sdd-project-explorer.scan_modules`
   - `sdd-project-explorer.verify_class_exists`
   - `sdd-arch-standard.list_rules`
   - `sdd-arch-standard.get_feature_rules`
   - `sdd-pipeline.list_pipeline_commands`
   - `sdd-pipeline.flow_status`

## Gemini CLI

参考模板：

- `templates/gemini/settings.example.json`
- `templates/gemini/GEMINI.md`

建议做法：

1. 把 `settings.example.json` 中的 `mcpServers` 合并到 Gemini CLI 设置。
2. 把 `GEMINI.md` 放到 Gemini CLI 会读取的项目上下文位置。
3. 首次运行时先让 Gemini 调用 `list_rules`、`scan_modules`、`list_pipeline_commands` 验证 MCP 是否可用。

## OpenCode

参考模板：

- `templates/opencode/opencode.example.json`
- `templates/opencode/AGENTS.md`

建议做法：

1. 把 `opencode.example.json` 中的 `mcp` 配置合并到 OpenCode 配置。
2. 把 `AGENTS.md` 放到项目上下文中。
3. 只挂载 SDD 必需的 MCP，避免工具列表过多挤占上下文。
4. 让 `sdd-pipeline` 承接流程控制与报告读取，减少 agent 直接拼接命令行参数的负担。

## 团队使用建议

- 新成员第一次接入时，先跑 `scripts/doctor.ps1`。
- 团队共享的业务项目只需要统一：
  - SDD 仓库路径
  - 目标业务项目路径
  - 设计目录路径
  - 数据库 schema 根目录
- 先使用本地源码版 MCP；稳定后再把 MCP Server 发布为 npm 包。
- 后续发布 npm 后，配置可从：

```json
{
  "command": "node",
  "args": ["D:\\project\\SDD\\mcp-servers\\project-explorer\\dist\\server.js"]
}
```

切换为：

```json
{
  "command": "npx",
  "args": ["-y", "project-explorer-mcp@0.1.0"]
}
```

## 当前边界

第一阶段只接入现有能力：

- 项目扫描：`project-explorer`
- 架构规范：`arch-standard`
- Pipeline MCP：`sdd-pipeline`
- 本地 Pipeline 后端：`scripts/run_pipeline.py`

Gate 边界：

- Gate 1：校验设计结构、`sdd_level + capability_tags` 对应的 Design Pack 完整性，并冻结 `reports/vN/design-pack.snapshot/`。
- Gate 2：校验 baseline 真实性、REQ 覆盖和资源冲突，优先读取版本快照。
- Gate 3：校验架构语义最小规则，例如分层方向、异常处理和能力标签对应规则。
- Gate 5：校验测试骨架覆盖、可执行测试结果和 attached project 验证命令。

AI 可以辅助生成设计和修复建议，但 Gate 结论来自这些脚本产物。报告中的 `commands`、`evidence`、hash 和 `source` 字段用于审计。

当前 `sdd-pipeline` 已封装的能力：

- `list_pipeline_commands`
- `show_attachment`
- `refresh_baseline`
- `project_console_cycle`
- `project_next`
- `flow_status`
- `validate_reports`
- `validate_all_reports`
- `generate_task_slices`
- `design_gates`
- `gate5`
- `release_gate`
- `onboard_project`

推荐 strict-first 主链路：

```powershell
python scripts/run_pipeline.py refresh-baseline --strict --feature-dir specs\your-feature
python scripts/run_pipeline.py design-gates specs\your-feature --strict
python scripts/run_pipeline.py implementation-gates specs\your-feature --strict
python scripts/run_pipeline.py release-gate specs\your-feature --strict
python scripts/run_pipeline.py validate-all-reports --stage all
```

GitHub Actions 示例：

- [../.github/workflows/sdd-pipeline.example.yml](../.github/workflows/sdd-pipeline.example.yml)

Long-running `sdd-pipeline` tools now run asynchronously by default, and also accept `{"async": false}` to force synchronous execution. Async calls return a task envelope that can
be polled with `get_pipeline_task` and read back with `read_pipeline_task_result`.

尚未封装为 MCP 的能力：

- `generate-feature-brief`
- `generate-design`
- `gate1` / `gate2` / `gate3` / `gate4`
- 更细粒度的报告资源读取，例如 latest `verify-report` / `gate-report` / `release-gate-report`
- 设计阶段与治理阶段的 resource 型接口，例如 `project-console` / `project-next` / `flow-status` 的只读暴露

当前建议优先让 agent 走 `sdd-pipeline` MCP；MCP 内部再调用 `run_pipeline.py`。只有在宿主环境明确禁止 Node 子进程执行时，才回退为终端直调。

### 宿主环境边界

`sdd-pipeline` 当前属于“轻封装”模式，本身不重写 Pipeline 逻辑，而是把 `run_pipeline.py` 包装成 MCP 工具。因此：

- 在普通本地终端环境中，MCP 会直接执行底层 pipeline 命令并返回刷新后的产物。
- 在某些受限沙箱中，宿主可能禁止 `node child_process` 拉起 Python。此时工具会显式返回 `error_code` / `execution_blocked`，并在已有产物存在时以 `artifact_status = fallback-existing` 的方式回读最近一次报告，便于 agent 继续消费现有治理结果。
- 如果团队要发布给更广泛的智能体使用，建议把“可执行宿主”作为接入前置条件写入安装说明。
