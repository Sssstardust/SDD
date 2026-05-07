# Skill 开发说明：requirement-analyzer

日期：2026-04-21  
来源依据：

- `D:\project\SDD\document\skill-mcp-harness-sdd-enhanced-v3.4.md`
- `D:\project\SDD\document\skill-mcp-harness-sdd.md`
- `D:\project\SDD\document\当前项目功能对比分析-2026-04-21.md`

---

## 1. 组件定位

`requirement-analyzer` 是 SDD 工作流中的需求解析 Skill。

它负责把用户输入的 PRD、需求单、业务说明等非结构化文本，转换成后续设计阶段可消费的结构化输入，避免设计生成阶段直接面对原始需求文本导致的遗漏、幻觉或字段不稳定。

在整体链路中的位置：

```text
PRD / 需求文本
  -> requirement-analyzer
  -> structured-prd.json / feature-brief 初始结构化结果
  -> sdd-generation / Feature Brief / 后续 Gates
```

---

## 2. 当前缺口

当前仓库中：

- 已有 `scripts/generate_feature_brief.py`
- 已有 `scripts/check_feature_brief.py`
- 但没有正式的 `skills/requirement-analyzer/`
- 没有 `SKILL.md`
- 没有 `prompt.md`
- 没有独立的结构化输出 JSON 规范
- 没有真正的 AI 调用层和反馈澄清机制

当前脚本只实现了一个“规则启发式版”的替代能力，还不是真正的 Skill。

---

## 3. 开发目标

本 Skill 需要实现以下目标：

1. 从 PRD 中抽取稳定的结构化字段
2. 输出后续阶段可直接消费的 JSON 结果
3. 明确 `project_mode`、`capability_tags`、`risk_tier` 的初判依据
4. 把歧义显式暴露出来，而不是静默猜测
5. 为后续 `sdd-generation` 和 `Feature Brief` 生成提供单一可信输入

---

## 4. 预期输入与输出

## 4.1 输入

- Markdown PRD
- 纯文本需求说明
- Word PRD
- 补充参数
  - `feature_name`
  - `feature_type`
  - 手工覆盖字段

## 4.2 输出

建议至少产出：

- `structured-prd.json`

建议字段：

- `feature_name`
- `feature_type`
- `one_liner`
- `project_mode`
- `project_mode_source`
- `project_mode_confidence`
- `project_mode_evidence`
- `capability_tags`
- `risk_tier`
- `requirements`
- `ambiguities`
- `entities`
- `apis`
- `business_rules`
- `dependencies`

---

## 5. 建议目录结构

```text
skills/
└── requirement-analyzer/
    ├── SKILL.md
    ├── prompt.md
    ├── run.py
    ├── extract.py
    ├── schema.json
    └── README.md
```

建议职责：

- `SKILL.md`
  - 定义触发条件、禁用条件、执行步骤
- `prompt.md`
  - 定义 AI 提示模板
- `run.py`
  - 负责调用 AI、写输出、处理 clarify 场景
- `extract.py`
  - 做确定性校验与格式化
- `schema.json`
  - 约束输出结构

---

## 6. 关键能力要求

## 6.1 结构化抽取

必须稳定抽取：

- 需求列表
- 优先级
- 业务规则
- 涉及接口
- 涉及实体
- 是否涉及支付、异步、外部调用、幂等、数据库变更

## 6.2 能力标签推导

必须输出：

- `capability_tags`

至少要覆盖：

- `api`
- `db-change`
- `payment`
- `idempotent`
- `async`
- `external-call`

## 6.3 风险等级推导

必须能按当前 v3.4 规则推导：

- `payment -> high`
- `async + db-change -> high`
- `security-sensitive -> high`
- `external-call + payment -> high`
- 其他默认 `low`

## 6.4 歧义暴露

如果无法确定，不能直接编造，必须输出：

- `ambiguities`
- 或写入明确的待澄清项

## 6.5 人工覆盖能力

应允许通过命令行或参数：

- 手动覆盖 `feature_name`
- 手动覆盖 `feature_type`
- 手动补充关键字段

---

## 7. 与现有仓库的衔接方式

建议采用以下衔接策略：

1. 保留现有 `scripts/generate_feature_brief.py` 作为降级方案
2. 新增 `skills/requirement-analyzer/run.py`
3. 在 `scripts/run_pipeline.py generate-feature-brief` 中优先调用 Skill
4. Skill 失败时允许回退到当前启发式实现
5. 最终输出仍兼容当前 `feature-brief.md` 所需字段

这样可以避免一次性推翻现有脚本。

---

## 8. 开发任务拆解

## 8.1 第一阶段：最小 Skill 形态

- 建立 `skills/requirement-analyzer/` 目录
- 编写 `SKILL.md`
- 编写 `prompt.md`
- 编写 `run.py`
- 编写 `extract.py`
- 定义 `structured-prd.json` 结构

## 8.2 第二阶段：与现有流程接线

- 让 `run_pipeline.py` 能调用该 Skill
- 输出结果映射到 `feature-brief.md`
- 保证 `check_feature_brief.py` 可消费

## 8.3 第三阶段：补 clarify / 重跑能力

- 缺字段时返回 clarify
- 支持人工补参后恢复执行
- 输出明确错误类型，而不是统一失败

## 8.4 第四阶段：准确率与评估

- 准备真实 PRD 样本
- 评估标签推导准确率
- 评估需求抽取完整度
- 评估歧义暴露率

---

## 9. 验收标准

至少满足以下验收条件：

1. 能从一份真实 PRD 中生成合法的 `structured-prd.json`
2. 输出结果包含 `capability_tags`
3. 输出结果包含 `risk_tier`
4. 输出结果能映射为当前仓库可用的 `feature-brief.md`
5. 歧义场景不会静默猜测
6. 缺失字段时能返回明确的 clarify 信号
7. 至少 10 个真实样本回归可用

---

## 10. 优先级判断

优先级：`高`

原因：

- 这是 Skill 层的入口能力
- 没有它，后续 `sdd-generation` 仍然依赖半结构化输入
- 它直接决定后续 `capability_tags`、`risk_tier`、需求追溯的质量

---

## 11. 建议交付物

建议最终交付：

- `skills/requirement-analyzer/SKILL.md`
- `skills/requirement-analyzer/prompt.md`
- `skills/requirement-analyzer/run.py`
- `skills/requirement-analyzer/extract.py`
- `skills/requirement-analyzer/schema.json`
- 示例 `structured-prd.json`
- 与 `run_pipeline.py` 的接线改造

