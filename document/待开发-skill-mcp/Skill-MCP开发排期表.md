# Skill / MCP 开发排期表

日期：2026-04-21  
适用范围：

- `requirement-analyzer`
- `sdd-generation`
- `project-explorer`
- `polyquery` 接入层
- `arch-standard`

关联文档：

- `D:\project\SDD\document\待开发-skill-mcp\Skill-requirement-analyzer.md`
- `D:\project\SDD\document\待开发-skill-mcp\Skill-sdd-generation.md`
- `D:\project\SDD\document\待开发-skill-mcp\MCP-project-explorer.md`
- `D:\project\SDD\document\待开发-skill-mcp\MCP-polyquery-接入.md`
- `D:\project\SDD\document\待开发-skill-mcp\MCP-arch-standard.md`

---

## 1. 排期结论

建议的整体开发顺序不是“先把 5 个都做完再联调”，而是：

```text
Phase 1
  requirement-analyzer
  + project-explorer
  + polyquery 接入

Phase 2
  sdd-generation（先接最小上下文）

Phase 3
  arch-standard
  + Gate 3 / sdd-generation 规则接线

Phase 4
  全链路联调与回归
```

核心原则：

1. 先补“输入事实”和“结构化需求”
2. 再补“基于事实生成设计”
3. 最后补“规范驱动约束”

原因是：

- `sdd-generation` 依赖 `requirement-analyzer`
- `sdd-generation` 依赖 `project-explorer`
- `sdd-generation` 依赖 `polyquery`
- `arch-standard` 对质量提升很重要，但不是最早的阻塞项

---

## 2. 依赖关系

## 2.1 强依赖

| 组件 | 依赖项 | 说明 |
| --- | --- | --- |
| `sdd-generation` | `requirement-analyzer` | 没有结构化需求，设计生成输入不稳定 |
| `sdd-generation` | `project-explorer` | 需要真实类、方法、模块事实 |
| `sdd-generation` | `polyquery` 接入 | 需要真实表结构事实 |
| Gate 3 规范驱动化 | `arch-standard` | 没有统一规则源就只能继续硬编码 |

## 2.2 弱依赖

| 组件 | 弱依赖项 | 说明 |
| --- | --- | --- |
| `requirement-analyzer` | 无 | 可以最先启动 |
| `project-explorer` | 无 | 可以最先启动 |
| `polyquery` 接入 | 数据源配置 | 需要环境支持，但不依赖其他代码组件 |
| `arch-standard` | 规范文档整理 | 需要先把规则文档沉淀出来 |

---

## 3. 推荐排期

## 3.1 Phase 1：打基础输入层

目标：

- 先把 Skill / MCP 的基础输入层补齐
- 让后续生成阶段不再依赖纯手工和启发式脚本

包含组件：

- `requirement-analyzer`
- `project-explorer`
- `polyquery` 接入层

阶段交付物：

- `skills/requirement-analyzer/`
- `mcp-servers/project-explorer/`
- `scripts/polyquery_adapter.py`
- 可用的 `structured-prd.json`
- 可由 MCP 生成的 `module-map.json`
- 可由 polyquery 生成的 `schema-context.json`

建议优先级：

- `requirement-analyzer`：P0
- `project-explorer`：P0
- `polyquery` 接入：P0

建议并行方式：

- 一人负责 `requirement-analyzer`
- 一人负责 `project-explorer`
- 一人负责 `polyquery` 接入

阶段验收：

- 三者都可以单独运行
- 三者都能产出兼容当前仓库格式的输出
- 不要求这一阶段就把全链路接通

## 3.2 Phase 2：打通设计生成层

目标：

- 基于结构化需求和事实来源生成设计文档

包含组件：

- `sdd-generation`

阶段交付物：

- `skills/sdd-generation/`
- 可生成 `design-v{N}.md`
- 可联动生成最小 `design-pack/`
- 能通过当前 `check_design_structure.py`
- 能通过当前 `check_design_pack.py`

为什么放在第二阶段：

- 它最依赖前三个组件
- 如果前三个事实源没稳定，设计生成很容易做成“伪自动化”

建议优先级：

- `sdd-generation`：P0

阶段验收：

- 至少 2 条现有试点可以用 Skill 生成一版设计
- 输出结果可进入现有 Gate 2 / 3

## 3.3 Phase 3：补规范约束层

目标：

- 让架构规范从“硬编码脚本规则”演进成“可复用规范事实源”

包含组件：

- `arch-standard`

阶段交付物：

- `docs/arch-standards/`
- `mcp-servers/arch-standard/`
- 可结构化输出约束
- Gate 3 局部改造成规则驱动

为什么放在第三阶段：

- 它对长期平台化很重要
- 但不阻塞最小的结构化需求与事实注入链路

建议优先级：

- `arch-standard`：P1

阶段验收：

- Skill 能读取规范
- Gate 3 至少有一部分逻辑改为规范驱动

## 3.4 Phase 4：全链路联调与回归

目标：

- 把 5 个组件真正并入当前主流程

包含工作：

- `run_pipeline.py` 接线
- `refresh_module_map.py` 接线
- `refresh_schema_context.py` 接线
- Gate 2 / Gate 3 联调
- 两条试点样例回归
- 至少一条新增样例演练

阶段交付物：

- 完整联调说明
- 回归测试记录
- 问题清单与后续优化项

---

## 4. 推荐里程碑

## 4.1 里程碑 M1：结构化输入成型

完成标准：

- `requirement-analyzer` 可输出 `structured-prd.json`
- `project-explorer` 可通过 MCP 查询类信息
- `polyquery` 可拉取真实表结构

里程碑价值：

- 表示 Skill / MCP 的输入层已经具备基础能力

## 4.2 里程碑 M2：设计生成跑通

完成标准：

- `sdd-generation` 能生成设计文档
- 能生成最小设计包
- 生成结果可通过基础结构校验

里程碑价值：

- 表示 Skill 层开始真正接管设计生成

## 4.3 里程碑 M3：规范驱动接入

完成标准：

- `arch-standard` 可被 Skill 和 Gate 消费
- Gate 3 有部分规则从硬编码迁移到规范驱动

里程碑价值：

- 表示平台化约束层开始成型

## 4.4 里程碑 M4：全链路回归通过

完成标准：

- 现有 2 条试点回归通过
- 至少 1 条新增样例完整走通
- 关键脚本无明显倒退

里程碑价值：

- 表示 Skill + MCP + Harness 三层开始真正协同

---

## 5. 推荐任务拆分方式

## 5.1 如果只有 1 个人开发

建议顺序：

1. `requirement-analyzer`
2. `project-explorer`
3. `polyquery` 接入
4. `sdd-generation`
5. `arch-standard`
6. 全链路联调

原因：

- 这条路径最符合依赖关系
- 能减少反复返工

## 5.2 如果有 2 个人开发

建议分工：

- 开发 A：
  - `requirement-analyzer`
  - `sdd-generation`
- 开发 B：
  - `project-explorer`
  - `polyquery` 接入
  - `arch-standard`

联调时机：

- A 完成 `requirement-analyzer`
- B 完成 `project-explorer + polyquery` 最小可用版
- 之后进入 `sdd-generation` 联调

## 5.3 如果有 3 个人开发

建议分工：

- 开发 A：`requirement-analyzer`
- 开发 B：`project-explorer + polyquery`
- 开发 C：`arch-standard`

第二阶段：

- 三人合力推进 `sdd-generation` 和主流程接线

这是最适合当前项目的并行方式。

---

## 6. 风险提示

## 6.1 最大风险不是 MCP，而是 `sdd-generation`

原因：

- 它需要真正消费多源上下文
- 需要处理反馈重试
- 需要兼容现有 Gate 产物
- 需要控制幻觉

因此虽然它排在第二阶段，但实际开发复杂度最高。

## 6.2 `polyquery` 的风险主要在环境，不在代码

风险点：

- 数据源配置
- 网络连通性
- 账号权限
- 开发环境数据库可用性

因此它的代码量未必最大，但联调风险不小。

## 6.3 `arch-standard` 的难点在规范治理，不在 Server 本身

风险点：

- 团队规范不统一
- 规则写不清楚
- 文档和代码规则口径不一致

所以它的难点不只是写个 MCP Server，而是先沉淀规则。

---

## 7. 推荐优先级总表

| 组件 | 优先级 | 推荐阶段 | 是否阻塞后续 |
| --- | --- | --- | --- |
| `requirement-analyzer` | P0 | Phase 1 | 是 |
| `project-explorer` | P0 | Phase 1 | 是 |
| `polyquery` 接入 | P0 | Phase 1 | 是 |
| `sdd-generation` | P0 | Phase 2 | 是 |
| `arch-standard` | P1 | Phase 3 | 否，但影响平台化质量 |

---

## 8. 最终建议

当前最合理的推进节奏是：

```text
先做输入层
  -> 再做生成层
  -> 再做规范层
  -> 最后做全链路联调
```

换句话说：

- 不建议先做 `arch-standard`
- 不建议先做 `sdd-generation` 而不补事实源
- 不建议把 5 个组件拆成完全无依赖并行开发

最推荐的执行路径是：

1. `requirement-analyzer`
2. `project-explorer`
3. `polyquery` 接入
4. `sdd-generation`
5. `arch-standard`
6. 主流程联调与回归

一句话总结：

**先补输入事实，再补设计生成，最后补规范驱动，这是当前项目最稳、返工最少的开发顺序。**

