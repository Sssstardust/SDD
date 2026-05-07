# MCP 开发说明：project-explorer

日期：2026-04-21  
来源依据：

- `D:\project\SDD\document\skill-mcp-harness-sdd-enhanced-v3.4.md`
- `D:\project\SDD\document\skill-mcp-harness-sdd.md`
- `D:\project\SDD\document\当前项目功能对比分析-2026-04-21.md`

---

## 1. 组件定位

`project-explorer` 是面向代码库事实的自定义 MCP。

它的职责是为设计生成和 Gate 校验提供“真实存在的类、包、方法、模块”信息，避免模型凭空编造类名和调用链。

在整体架构中的位置：

```text
代码仓库
  -> project-explorer MCP
  -> 类 / 包 / 方法 / 模块结构事实
  -> sdd-generation / Gate 2
```

---

## 2. 当前缺口

当前仓库中：

- 已有 `scripts/refresh_module_map.py`
- 会通过正则扫描 Java 和设计文档生成 `module-map.json`
- 但没有 `mcp-servers/project-explorer/`
- 没有真正的 MCP Server
- 没有对外可调用的 MCP Tool
- 没有扫描范围配置和缓存策略的正式实现

因此当前只是“本地离线快照版”，不是正式的 MCP 能力。

---

## 3. 开发目标

`project-explorer` 需要实现以下目标：

1. 向上层提供可调用的类扫描和存在性校验能力
2. 支持多模块工程扫描
3. 支持关键词相关类搜索
4. 支持类名存在性验证
5. 最终为 `module-map.json` 和 Gate 2 提供更真实的来源

---

## 4. 预期能力

建议至少提供以下 Tool：

- `scan_modules`
  - 根据关键词返回相关类、包、类型、来源文件
- `verify_class_exists`
  - 校验指定类名是否存在
- `list_methods`
  - 返回类的公开方法签名
- `get_class_detail`
  - 返回类的包名、文件、方法、简单依赖信息

可选增强：

- `get_sdd_interface`
- `find_related_classes`
- `scan_module_boundaries`

---

## 5. 建议目录结构

```text
mcp-servers/
└── project-explorer/
    ├── server.py
    ├── config.yaml
    ├── scanner.py
    ├── cache.py
    └── README.md
```

建议职责：

- `server.py`
  - MCP Server 入口
- `config.yaml`
  - 扫描根目录、类型白名单、缓存策略
- `scanner.py`
  - 代码扫描与信息抽取
- `cache.py`
  - 扫描缓存

---

## 6. 关键能力要求

## 6.1 多模块扫描

必须支持：

- 单模块工程
- 多模块 Java/Spring 工程
- 自定义 `scan_roots`

## 6.2 结果真实性

返回结果至少应包含：

- 类名
- 简单名
- FQN
- 包名
- 文件路径
- 类型
- 公开方法列表

## 6.3 性能与缓存

大型工程下不能每次都全量扫。

因此建议支持：

- 本地缓存
- 强制刷新
- 按关键词增量过滤

## 6.4 结果可直接被 Skill 消费

输出结构应方便：

- `sdd-generation` 组装上下文
- Gate 2 校验类名
- 生成 `module-map.json`

---

## 7. 与现有仓库的衔接方式

建议分两步接入：

### 第一步：MCP 和现有快照并存

- 保留 `scripts/refresh_module_map.py`
- 同时新增 `project-explorer MCP`
- 允许 MCP 输出被序列化为 `module-map.json`

### 第二步：逐步替换快照来源

- `refresh_module_map.py` 改为调用 MCP
- Gate 2 的类名校验逐渐从本地正则扫描切到 MCP 输出

这样能降低迁移风险。

---

## 8. 开发任务拆解

## 8.1 第一阶段：最小 MCP Server

- 建立 `mcp-servers/project-explorer/`
- 编写 `server.py`
- 实现 `scan_modules`
- 实现 `verify_class_exists`

## 8.2 第二阶段：方法签名能力

- 提取公开方法
- 提供 `list_methods`
- 提供更稳定的类详情结构

## 8.3 第三阶段：配置与缓存

- 增加 `config.yaml`
- 增加缓存机制
- 支持强制刷新

## 8.4 第四阶段：与主流程接线

- 让 `refresh_module_map.py` 可调用 MCP
- 让 Gate 2 可选使用 MCP 输出
- 让 `sdd-generation` 用 MCP 而不是直接扫代码

---

## 9. 验收标准

至少满足：

1. 在当前仓库中可以通过 MCP 调用到 `scan_modules`
2. 在当前仓库中可以通过 MCP 调用到 `verify_class_exists`
3. 返回结果包含文件路径、类名、方法签名
4. 至少能覆盖两条试点涉及的类校验
5. `module-map.json` 可以基于 MCP 输出生成
6. 大型扫描不会明显阻塞主流程

---

## 10. 优先级判断

优先级：`高`

原因：

- 它是 Brownfield 真实性校验的核心事实源
- 没有它，Gate 2 仍然更多依赖本地快照和设计文档反推
- 它是 MCP 层中最值得优先实现的组件

---

## 11. 建议交付物

建议最终交付：

- `mcp-servers/project-explorer/server.py`
- `mcp-servers/project-explorer/config.yaml`
- `mcp-servers/project-explorer/scanner.py`
- `mcp-servers/project-explorer/cache.py`
- MCP 调用示例
- 与 `refresh_module_map.py` 的接线改造

