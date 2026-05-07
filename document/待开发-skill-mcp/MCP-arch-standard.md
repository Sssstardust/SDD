# MCP 开发说明：arch-standard

日期：2026-04-21  
来源依据：

- `D:\project\SDD\document\skill-mcp-harness-sdd-enhanced-v3.4.md`
- `D:\project\SDD\document\skill-mcp-harness-sdd.md`
- `D:\project\SDD\document\当前项目功能对比分析-2026-04-21.md`

---

## 1. 组件定位

`arch-standard` 是面向团队架构规范的自定义 MCP。

它的职责是向设计生成和 Gate 校验提供统一的架构规范、分层约束、事务规则、命名规范和横切约束，避免这些规则分散在文档、人工经验和零散模板里。

在整体架构中的位置：

```text
架构规范文档
  -> arch-standard MCP
  -> 约束上下文 / constraints
  -> sdd-generation / Gate 3
```

---

## 2. 当前缺口

当前仓库中：

- 没有 `docs/arch-standards/`
- 没有 `mcp-servers/arch-standard/`
- 没有统一的约束输出结构
- Gate 3 当前主要是脚本硬编码规则校验

因此当前架构约束更多体现在代码规则里，而不是来自统一规范事实源。

---

## 3. 开发目标

该 MCP 需要实现：

1. 统一管理团队架构规范
2. 让 Skill 和 Gate 都能读取同一份规范事实
3. 让 Gate 3 从“硬编码规则”逐步演进为“规范驱动校验”
4. 为新团队成员和新项目提供明确的约束来源

---

## 4. 预期能力

建议至少提供以下 Tool：

- `list_rules`
  - 列出可用规范
- `get_rule`
  - 读取单条规范内容
- `get_constraints`
  - 返回给 `sdd-generation` 消费的结构化约束
- `get_feature_rules`
  - 根据 `feature_type` 或 `capability_tags` 返回相关规则子集

---

## 5. 建议目录结构

```text
docs/
└── arch-standards/
    ├── layering-rules.md
    ├── transaction-rules.md
    ├── api-rules.md
    ├── naming-rules.md
    └── exception-rules.md

mcp-servers/
└── arch-standard/
    ├── server.py
    ├── rule_map.py
    └── README.md
```

建议职责：

- `docs/arch-standards/`
  - 规范原文
- `server.py`
  - MCP Server 入口
- `rule_map.py`
  - Feature / Tag 到规范集合的映射

---

## 6. 关键能力要求

## 6.1 规范统一来源

规范至少要覆盖：

- 分层依赖规则
- 事务边界规则
- 接口设计规范
- 异常处理规范
- 命名规范
- 外部调用约束

## 6.2 可按场景裁剪

不同 Feature 不需要注入全部规则。

因此建议：

- 可按 `feature_type`
- 可按 `capability_tags`
- 可按规则类型

返回裁剪后的约束集合。

## 6.3 结构化输出

除了返回 Markdown 原文，建议还返回：

- 规则标题
- 规则类型
- 适用标签
- 关键禁止项
- 关键必须项

这样更方便 Skill 和 Gate 消费。

## 6.4 与 Gate 3 联动

最终目标不是“只把文档读出来”，而是：

- 让 Gate 3 能根据规范校验设计
- 让 `sdd-generation` 在生成时就受规范约束

---

## 7. 与现有仓库的衔接方式

建议分阶段推进：

### 第一步：先把规范文档补齐

- 建立 `docs/arch-standards/`
- 填充至少 4 到 5 份基础规范文档

### 第二步：建立 MCP Server

- 实现 `list_rules`
- 实现 `get_rule`
- 实现 `get_constraints`

### 第三步：主流程接线

- `sdd-generation` 从 MCP 读取约束
- Gate 3 从 MCP 读取约束
- 逐渐把硬编码规则迁移到规范驱动模式

---

## 8. 开发任务拆解

## 8.1 第一阶段：规范文档整理

- 输出最小架构规范文档集合
- 统一文档格式和命名

## 8.2 第二阶段：MCP Server 最小实现

- 建立 `mcp-servers/arch-standard/`
- 实现规则读取和列举

## 8.3 第三阶段：结构化约束输出

- 增加规则映射
- 输出结构化约束

## 8.4 第四阶段：与 Gate 3 联动

- 让 Gate 3 优先读取约束来源
- 减少脚本中的硬编码规则

---

## 9. 验收标准

至少满足：

1. 已有基础架构规范文档目录
2. 可通过 MCP 列出规范文件
3. 可通过 MCP 获取单条规范内容
4. 可返回结构化约束供上层消费
5. 至少有一部分 Gate 3 校验逻辑切换到规范驱动

---

## 10. 优先级判断

优先级：`中高`

原因：

- 它直接决定 Gate 3 是否能继续平台化演进
- 没有它，Gate 3 只能长期维持在脚本硬编码规则阶段
- 但相对 `project-explorer` 和 `polyquery`，它对 Brownfield 真实性的直接影响稍弱

---

## 11. 建议交付物

建议最终交付：

- `docs/arch-standards/` 基础规范集
- `mcp-servers/arch-standard/server.py`
- `mcp-servers/arch-standard/rule_map.py`
- 结构化约束输出示例
- 与 Gate 3 / `sdd-generation` 的接线改造

