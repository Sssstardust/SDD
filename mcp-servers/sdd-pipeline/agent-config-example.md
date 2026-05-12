# sdd-pipeline MCP 配置示例

这是给 agent 直接注册 `sdd-pipeline` 的最小示例。

## Codex / 通用 MCP JSON

```json
{
  "mcpServers": {
    "sdd-pipeline": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\sdd-pipeline\\dist\\server.js"
      ]
    }
  }
}
```

## 推荐首批工具

- `sdd-pipeline.health_check`
- `sdd-pipeline.show_attachment`
- `sdd-pipeline.list_pipeline_commands`
- `sdd-pipeline.project_next`
- `sdd-pipeline.project_console_cycle`
- `sdd-pipeline.generate_feature_brief`
- `sdd-pipeline.init_feature`
- `sdd-pipeline.prepare_design_cycle`
- `sdd-pipeline.design_cycle`
- `sdd-pipeline.approved_implementation_cycle`
- `sdd-pipeline.full_flow`

## 适用场景

- 只看当前项目入口和附着配置时，用 `show_attachment`
- 需要推进单个 feature 时，用 `flow_status` / `design_cycle` / `approved_implementation_cycle`
- 需要让 agent 走完整条 SDD 主链路时，优先用 `full_flow`
- 需要项目级持续推进时，用 `project_cycle` 或 `continue_project_flow`

## 多项目用法

- 先用 `onboard_project` 为外部项目建立一个 `profile`
- 后续所有工具都可以显式带 `profile`
- 如果 feature 在外部项目的 `design_root` 下，`feature_dir` 仍然可以传 `specs/<feature>`，MCP 会按当前 `profile` 解析到对应项目

示例：

```json
{
  "project_root": "D:\\project\\PDC2\\pdc_src\\pdc-arc-root\\arc-web",
  "name": "pdc-arc-web",
  "profile": "pdc-arc-web",
  "design_roots": [
    "D:\\project\\PDC2\\pdc_src\\pdc-arc-root\\arc-web\\specs"
  ],
  "schema_roots": [
    "D:\\project\\PDC2\\pdc_src\\pdc-arc-root\\arc-web\\src\\main\\resources",
    "D:\\project\\PDC2\\pdc_src\\pdc-arc-root\\arc-web\\database"
  ]
}
```
