# MCP 开发说明：polyquery 接入与封装

日期：2026-04-21  
来源依据：

- `D:\project\SDD\document\skill-mcp-harness-sdd-enhanced-v3.4.md`
- `D:\project\SDD\document\skill-mcp-harness-sdd.md`
- `D:\project\SDD\document\当前项目功能对比分析-2026-04-21.md`

当前状态更新：

- 2026-04-29 已完成项目侧接入。
- 已新增 `scripts/polyquery_adapter.py`。
- 已新增 `config/polyquery.example.json`。
- `scripts/refresh_schema_context.py` 已支持 `--from-polyquery`、`--polyquery-config`、`--polyquery-snapshot`、`--polyquery-fallback`。
- `scripts/run_pipeline.py refresh-schema-context` 已透出 polyquery 参数。
- 使用说明见 `D:\project\SDD\docs\polyquery-integration.md`。

---

## 1. 组件定位

`polyquery` 不是本项目从零实现的自定义 MCP Server，而是一个需要正式接入到当前 SDD 工作流中的外部数据库事实源。

它承担的职责是：

- 读取真实数据库元数据
- 返回表、字段、索引、注释等结构信息
- 为 `schema-context.json`、Gate 2、`sdd-generation` 提供数据库事实

在整体链路中的位置：

```text
数据库
  -> polyquery MCP
  -> 实时表结构 / 字段 / 索引元数据
  -> schema-context.json / Gate 2 / sdd-generation
```

---

## 2. 当前缺口

当前仓库中：

- 已有 `scripts/refresh_schema_context.py`
- 但它主要是从 `design-pack/数据模型.md` 和 `数据库变更.sql` 反推表结构
- 没有真正接入数据库
- 没有 polyquery 的配置文件
- 没有连接状态检查
- 没有调用失败后的错误标记机制

因此当前的 `schema-context.json` 更像“设计产物快照”，不是真实数据库事实。

---

## 3. 开发目标

本组件的开发重点不是“重写 polyquery”，而是把 polyquery 正式接入当前项目流程。

目标包括：

1. 配置 polyquery 数据源
2. 为当前 SDD 流程建立统一调用方式
3. 将 polyquery 查询结果沉淀为 `schema-context.json`
4. 明确空结果与调用失败的区分
5. 让 `sdd-generation` 和 Gate 2 能基于真实数据库元数据工作

---

## 4. 预期能力

建议至少具备以下调用能力：

- `list_tables`
- `describe_table`
- 必要时 `query_database`

对当前项目而言，最核心的两个调用是：

- 列出候选表
- 拉取目标表结构

---

## 5. 建议目录结构

因为 polyquery 本身是外部 MCP，这里更适合建设“接入层”而非“重写一个 server”：

```text
scripts/
├── refresh_schema_context.py
└── polyquery_adapter.py

config/
└── polyquery.yaml
```

或者：

```text
mcp-servers/
└── polyquery-adapter/
    ├── README.md
    └── sample-config.md
```

推荐做法：

- 保持 polyquery 为外部依赖
- 在本项目内部只开发适配与调用封装层

---

## 6. 关键能力要求

## 6.1 真实数据库事实接入

必须支持：

- 指定 `db_type`
- 指定 `connection_name`
- 指定候选表名

## 6.2 错误与空结果区分

必须区分三种情况：

1. 查询成功且有结果
2. 查询成功但无匹配表
3. 查询失败

第 2 种和第 3 种不能混为一谈。

建议约定：

- 空结果：写入空对象或空数组，并标记 `scenario=new-table`
- 调用失败：写入错误标记，如 `{"__error__": "...", "ts": "..."}``

## 6.3 与本地快照兼容

在 polyquery 不可用时，流程不能完全崩掉。

建议：

- 允许本地 `schema-context.json` 作为降级输入
- 但要明确标记当前不是实时库事实

## 6.4 安全要求

建议遵循：

- 只读账号
- 开发/测试库，不直连生产
- 配置文件不写死敏感信息到仓库

---

## 7. 与现有仓库的衔接方式

建议分阶段接入：

### 第一步：适配层接入

- 保留现有 `refresh_schema_context.py`
- 在其中增加 polyquery 调用能力
- 无法调用时再回退到当前本地反推逻辑

### 第二步：事实优先

- 优先使用 polyquery 真实结果
- 只有在连接失败或项目离线时才回退本地快照

### 第三步：服务全链路消费

- `sdd-generation` 改为直接消费 polyquery 结果
- Gate 2 改为优先校验真实数据库表结构

---

## 8. 开发任务拆解

## 8.1 第一阶段：配置打通

- 定义 polyquery 配置方式
- 明确 `db_type` 和 `connection_name`
- 提供本项目调用示例

## 8.2 第二阶段：本地适配层

- 新增 `polyquery_adapter.py`
- 封装列出表和描述表结构的方法
- 明确错误结构

## 8.3 第三阶段：接入 `refresh_schema_context.py`

- 支持从 polyquery 拉真实元数据
- 落地到 `schema-context.json`
- 保持兼容现有格式

## 8.4 第四阶段：接入 Skill / Gate

- `sdd-generation` 消费真实表结构
- Gate 2 优先校验真实表结构

---

## 9. 验收标准

至少满足：

1. 能在当前环境成功调用 polyquery 列出表
2. 能成功获取指定表结构
3. 能把结果写成当前兼容格式的 `schema-context.json`
4. 能区分空结果与调用失败
5. 在数据库可达场景下，Gate 2 校验以真实表结构为准

---

## 10. 优先级判断

优先级：`高`

原因：

- 它是数据库真实性的核心事实源
- 没有它，当前 `schema-context.json` 只是由设计产物反推，无法真正防止数据库层幻觉
- 它直接决定 Brownfield 场景下的表结构校验可信度

---

## 11. 建议交付物

建议最终交付：

- `scripts/polyquery_adapter.py`
- polyquery 配置说明文档
- `refresh_schema_context.py` 改造
- `schema-context.json` 实时生成能力
- 连接性检查脚本
