---
name: requirement-analyzer
description: 将 PRD、Markdown 需求文档、纯文本需求说明和 Word（`.docx`）PRD 解析为 SDD 工作流可消费的 `structured-prd.json`。当 Codex 需要从非结构化需求文本中提取或归一化 `feature_name`、`feature_type`、`project_mode`、`capability_tags`、`risk_tier`、`requirements`、`ambiguities`、`entities`、`apis`、`business_rules`、`dependencies` 等字段，或当 `run_pipeline.py generate-feature-brief` 需要一个可信的单一输入来生成 `feature-brief.md` 时使用本 Skill。
---

# 需求解析器

使用 [run.py](run.py) 作为执行入口。

按以下流程执行：

1. 从 Markdown、纯文本或 `.docx` 中读取原始 PRD。
2. 仅在环境变量中已配置 OpenAI 兼容网关时，优先尝试 AI 提取。
3. 无论 AI 是否参与，都必须在提取后运行 [extract.py](extract.py) 中的确定性归一化与校验。
4. 输出符合 [schema.json](schema.json) 的机器可读 `structured-prd.json`。
5. 遇到需要澄清的场景时返回 `exit code 2`，而不是静默猜测缺失的核心字段。
6. 只有当输出达到 `status=ready` 时，才生成 `feature-brief.md`。
7. `feature-brief.md` 的前两个 YAML 块必须保持与仓库现有校验脚本兼容。
8. `feature-brief.md` 的后续章节应由结构化字段显式展开，而不是写成泛化描述。

遵循以下规则：

- 把不确定性明确写入 `ambiguities`；不要编造 API、实体或业务规则。
- 允许通过 CLI 覆盖 `feature_name`、`feature_type`、`project_mode`、标签、实体、API 和业务规则。
- `capability_tags` 与 `risk_tier` 必须符合 v3.4 规则。
- 生成结果必须兼容仓库当前使用的 `feature-brief.md` 结构。

生成 `feature-brief.md` 时，按以下契约做字段映射：

- `project_mode`、`project_mode_source`、`project_mode_confidence`、`project_mode_evidence`、`project_mode_confirmed_by`、`feature_name`、`feature_type`、`one_liner`、`capability_tags`、`risk_tier`
  这些字段必须原样写入第一个 YAML 块，保证现有脚本可以稳定读取。
- `requirements`
  必须写入第二个 YAML 块，并保留稳定的 `req_id`、`priority`、`title` 和多行 `description`。
- `ambiguities`
  每一项渲染为 `- [AMBIGUOUS: ...]`；只有列表为空时才写 `- 无`。
- `one_liner`、`feature_type`、`project_mode`、`metadata`
  用这些字段推导“背景”“业务目标”“非目标”“成功标准”等业务说明。
- `requirements`
  还要在单独的“需求优先级映射”小节中按优先级汇总。
- `business_rules`
  必须在“关键业务规则映射”中逐条展开，不要压缩成一句模糊总结。
- `entities`
  必须在“实体映射”中展开 `name`、`kind`、`evidence`。
- `apis`
  必须在“接口映射”中展开 method、path、summary、evidence。
- `dependencies`
  必须在“依赖映射”中展开，并同时用于高层影响范围总结。
- `entities`、`apis`、`business_rules`、`dependencies`
  必须在 `feature-brief.md` 下半部分附带一段机器可读 YAML 上下文，供后续人工审阅。
- `capability_tags`、`risk_tier`、`project_mode`
  用这些字段解释风险原因、是否需要审批、设计关注点；措辞应可追溯到标签本身，而不是写成泛化风险模板。

不要做以下事情：

- 不要在仓库模板未变更的情况下随意修改 `feature-brief.md` 的顶层标题结构。
- 不要把必填 YAML 字段移出前两个 fenced YAML 块。
- 不要因为当前 Gate 脚本暂未消费某些字段，就静默丢弃这些结构化字段。
- 当结构化数据明明存在且可显式渲染时，不要随意写成“无”。

只有在启用 AI 提取时才读取 [prompt.md](prompt.md)。
当你需要一个归一化输出示例时，再读取 [references/structured-prd.example.json](references/structured-prd.example.json)。
