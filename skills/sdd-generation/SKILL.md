---
name: sdd-generation
description: 基于 `structured-prd.json`、`feature-brief.md`、`module-map.json`、`schema-context.json` 和架构约束生成 `design-v{N}.md` 与最小可用 `design-pack/`。当 Codex 需要从结构化需求和项目事实生成可进入 Gate 的技术设计草稿、按 `capability_tags` 联动设计包、读取 `gate-report.json` 进行定向修复，或通过 `run_pipeline.py generate-design` 自动产出设计文档时使用本 Skill。
---

# 设计生成器

使用 [run.py](run.py) 作为执行入口。

按以下流程执行：

1. 从工作区读取 `structured-prd.json`；若缺失，则从 `feature-brief.md` 推导最小结构化需求。
2. 通过 [assemble_context.py](assemble_context.py) 读取并裁剪 `module-map.json`、`schema-context.json` 和架构约束。
3. 若配置了 OpenAI 兼容网关，则优先使用 AI 生成设计文档与设计包。
4. 无论 AI 是否参与，都必须对输出执行确定性补全与最小校验。
5. 使用 [render_design_pack.py](render_design_pack.py) 生成与 `capability_tags` 对齐的最小 `design-pack/` 文件集。
6. 生成完成后，必须本地执行 `check_design_structure.py` 与 `check_design_pack.py`。
7. 若有 `gate-report.json` 反馈，则把违规项转成下一轮修复约束；不要忽略历史失败原因。
8. 支持 `feedback` 和 `resume` 两种闭环模式：
   - `feedback`：基于上一版 Gate 报告生成下一版设计
   - `resume`：在当前版本上保留人工修改并恢复校验/修复流程

遵循以下规则：

- 类名只能来自 `module-map.json` 的事实集合；如果没有匹配到相关类，就切换为“新领域模式”，不要编造存量类。
- 表名和字段名优先来自 `schema-context.json`；如果缺少可用事实，不要静默伪造真实存量表。
- `design-v{N}.md` 必须满足当前仓库的固定章节结构，并显式引用 `design-pack/`。
- `design-pack/` 只生成当前 `capability_tags` 必需的文件，但每个文件都必须满足现有校验脚本的最小语义要求。
- `payment`、`idempotent`、`external-call`、`async` 等高价值标签对应的策略文件不能只写空模板。
- 在 brownfield 场景下，优先选择真实存在的类、方法、表和字段；在 new-domain 场景下，必须明确写出“待脚手架确认”或“待领域建模确认”。

生成 `design-v{N}.md` 时，按以下契约映射字段：

- `feature_name`、`one_liner`、`requirements`
  用于生成“设计目标”“适用范围”“对应 REQ-ID”“验收标准矩阵”。
- `entities`
  用于生成“领域模型映射”和实体关系图；若缺少英文实体名，可使用稳定的领域对象名。
- `apis`
  用于生成“接口契约”章节和 `接口契约.openapi.yaml`、`接口文档.md`。
- `business_rules`、`dependencies`
  用于生成“异常流程”“异常处理”“依赖与时序说明”“外部调用策略”等内容。
- `capability_tags`
  决定必须生成的 `design-pack/` 文件和设计关注点。
- `project_mode`、`scenario`
  决定是优先引用存量事实，还是进入“新领域模式”的保守输出。
- `gate-report.json`
  用于形成“本轮必须修复的问题”约束，指导下一轮生成。
- `current_design_markdown`、`current_design_pack`
  在 `resume` 模式下作为当前人工修改基线传入；如果没有必要，不要覆盖这些修改。

`feedback / resume` 的行为约定：

- 首次运行时，若当前版本的 `gate-report.json` 不存在，应直接跳过反馈注入。
- 非 `resume` 模式下重新运行时，优先读取上一版 `reports/v{N-1}/gate-report.json` 作为反馈输入。
- `resume` 模式下重新运行时，优先读取当前版本 `reports/v{N}/gate-report.json`。
- `resume` 模式若未启用 AI，应保留当前 `design-vN.md`，只执行校验与必要的设计包补全，不要整篇重写。
- 超出最大重试次数后，必须写入 `escalation.log`，并给出明确的 `resume` 命令。

不要做以下事情：

- 不要引用 `module-map.json` 中不存在的 CamelCase 类名。
- 不要在 brownfield 场景下生成看似真实、但事实源里不存在的 `t_*` 表名。
- 不要只生成主设计文档而忽略 `design-pack/`。
- 不要把设计文档写成模板占位符集合；至少要包含可读的实体、流程、接口、异常和验收项。
- 不要让 `design-pack/` 留在空模板状态后直接进入 Gate。
- 不要在 `resume` 模式下无条件覆盖人工已修改的 draft 和设计包。

只有在启用 AI 时才读取 [prompt.md](prompt.md)。
当需要补充可重复执行的设计包渲染逻辑时，读取 [render_design_pack.py](render_design_pack.py)。
