# Skill 开发说明：sdd-generation

日期：2026-04-21  
来源依据：

- `D:\project\SDD\document\skill-mcp-harness-sdd-enhanced-v3.4.md`
- `D:\project\SDD\document\skill-mcp-harness-sdd.md`
- `D:\project\SDD\document\当前项目功能对比分析-2026-04-21.md`

---

## 1. 组件定位

`sdd-generation` 是 SDD 工作流中的设计生成 Skill。

它的职责不是简单生成一篇设计文档，而是基于：

- 结构化需求
- 类与模块事实
- 数据库表结构事实
- 架构规范约束

生成可进入 Gate 校验的设计产物，并在失败时根据 Gate 反馈做迭代修复。

在整体链路中的位置：

```text
structured-prd.json
  + module-map.json
  + schema-context.json
  + constraints / arch rules
  -> sdd-generation
  -> design-v{N}.md + design-pack/
  -> Gate 1 / 2 / 3
```

---

## 2. 当前缺口

当前仓库中：

- 已有 `scripts/init_design.py`
- 已有 `scripts/init_design_pack.py`
- 已有 `scripts/check_design_structure.py`
- 已有 `scripts/check_design_pack.py`
- 但没有正式的 `skills/sdd-generation/`
- 没有统一上下文组装器
- 没有 AI 生成与 Gate 反馈重试闭环
- 目前设计内容主要仍靠人工编辑和模板初始化

因此当前实现的是“设计模板与校验流程”，还不是“设计生成 Skill”。

---

## 3. 开发目标

该 Skill 需要实现以下目标：

1. 使用结构化需求和事实来源自动生成设计文档草稿
2. 按 `capability_tags` 自动决定必须生成的设计包内容
3. 与 Gate 反馈联动，支持重试修复
4. 避免引用不存在的类、表、字段
5. 输出可直接进入现有 Gate 2 / 3 / 4 / 5 链路的产物

---

## 4. 预期输入与输出

## 4.1 输入

至少包括：

- `structured-prd.json`
- `module-map.json`
- `schema-context.json`
- 架构规范约束
- 上一轮 `gate-report.json`（可选）

## 4.2 输出

至少包括：

- `design-v{N}.md`
- `design-pack/` 下必要文件
- 重试修复后的新版本设计

---

## 5. 建议目录结构

```text
skills/
└── sdd-generation/
    ├── SKILL.md
    ├── prompt.md
    ├── run.py
    ├── assemble_context.py
    ├── render_design_pack.py
    └── README.md
```

建议职责：

- `SKILL.md`
  - 定义触发条件与关键约束
- `prompt.md`
  - 设计文档生成 Prompt
- `run.py`
  - 主执行入口，负责生成、重试、恢复
- `assemble_context.py`
  - 统一读取和裁剪上下文
- `render_design_pack.py`
  - 渲染设计包辅助逻辑

---

## 6. 关键能力要求

## 6.1 上下文组装

必须能稳定读取：

- 结构化需求
- 类快照
- 表结构快照
- 架构规范

并控制上下文体积，避免把全部原始信息直接塞给模型。

## 6.2 事实约束

必须满足：

- 类名只能来自 `module-map.json`
- 表名、字段名只能来自 `schema-context.json`
- 架构规则必须来自规范上下文

如果关键事实缺失：

- 不允许静默编造
- 必须中止或进入明确降级模式

## 6.3 设计包联动

必须根据 `capability_tags` 决定生成哪些设计包文件。

至少要能联动：

- `api`
- `db-change`
- `idempotent`
- `payment`
- `async`
- `external-call`

## 6.4 Gate 反馈重试

如果上一轮 `gate-report.json` 存在：

- 必须读取违规项
- 必须逐条修复
- 必须带着“修复约束”进入下一轮生成

## 6.5 新领域模式

当 `project-explorer` 返回空结果时：

- 不能凭空伪造“已有类”
- 必须切换为“新领域模式”
- 明确标记当前是增量适配还是新领域设计

---

## 7. 与现有仓库的衔接方式

建议采用渐进式接入：

1. 保留 `scripts/init_design.py` 负责生成设计文件版本号和落点
2. 新增 `skills/sdd-generation/run.py` 负责实际内容生成
3. 先只让 Skill 生成 `design-v{N}.md`
4. 第二阶段再让 Skill 联动生成 `design-pack/`
5. 继续沿用当前已有的 Gate 校验脚本

这样既能补 Skill 层，又不会破坏现有主链路。

---

## 8. 开发任务拆解

## 8.1 第一阶段：Skill 基础骨架

- 建立 `skills/sdd-generation/`
- 编写 `SKILL.md`
- 编写 `prompt.md`
- 编写 `run.py`
- 编写 `assemble_context.py`

## 8.2 第二阶段：只生成设计主文档

- 读取 `structured-prd.json`
- 读取本地事实快照
- 生成 `design-v{N}.md`
- 与 `check_design_structure.py` 打通

## 8.3 第三阶段：联动设计包

- 按 `capability_tags` 生成 `design-pack`
- 与当前模板目录兼容
- 与 `check_design_pack.py` 打通

## 8.4 第四阶段：接 Gate 反馈重试

- 读取 `gate-report.json`
- 解析违规项
- 定向重试生成
- 支持 resume / feedback 模式

## 8.5 第五阶段：补稳定性治理

- 加上下文裁剪
- 增加失败降级路径
- 增加样例回归

---

## 9. 验收标准

至少满足：

1. 能基于 `structured-prd.json` 生成可通过 `check_design_structure.py` 的设计文档
2. 能按 `capability_tags` 生成最小可用 `design-pack`
3. 输出内容与 `module-map.json`、`schema-context.json` 一致
4. 在有 `gate-report.json` 时能执行一轮修复重试
5. 至少在 2 条现有试点上可运行
6. 输出结果能继续进入当前 `run_pipeline.py` 后续流程

---

## 10. 优先级判断

优先级：`高`

原因：

- 它是 Skill 层中最核心的生成能力
- 当前仓库缺的不是“模板”，而是“利用事实上下文生成设计”的统一能力
- 它直接关系到 Skill + MCP + Harness 三层架构是否真正成立

---

## 11. 建议交付物

建议最终交付：

- `skills/sdd-generation/SKILL.md`
- `skills/sdd-generation/prompt.md`
- `skills/sdd-generation/run.py`
- `skills/sdd-generation/assemble_context.py`
- `skills/sdd-generation/render_design_pack.py`
- 与 `run_pipeline.py` 的接线
- 至少 2 个试点样例的回归验证记录

