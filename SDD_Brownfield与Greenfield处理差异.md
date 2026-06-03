# SDD 项目：Brownfield 与 Greenfield 处理差异分析

> **文档用途**：说明 SDD 工具链针对存量项目（Brownfield）与新建项目（Greenfield）的差异化处理机制 **项目仓库**：https://github.com/Sssstardust/SDD **文档日期**：2026-05-10

---

## 一、三种项目模式定义

`requirement-analyzer` Skill 在解析 PRD 时，会自动识别并在 `structured-prd.json` 中输出 `project_mode` 字段：

字段值含义典型场景`brownfield`存量项目，有已有代码库和数据库在已上线系统上迭代新功能`greenfield`全新系统，从零开始全新业务域建设`hybrid`在已有基础设施上新建功能最常见：现有系统新模块

相关 Schema 字段：

```json
{
  "project_mode": "brownfield | greenfield | hybrid",
  "project_mode_source": "heuristic | ai | manual | mixed",
  "project_mode_confidence": 0.95,
  "project_mode_evidence": ["存在现有类引用", "..."],
  "project_mode_confirmed_by": "zhaoxingchen"
}
```

---

## 二、核心分支机制：运行时场景检测

设计生成阶段，工具通过检查两个上下文文件的状态来决定走哪条执行路径：

```python
def detect_scenario(module_map: dict, schema_context: dict) -> str:
    has_classes = any(v for v in module_map.values())  # 是否有已有类（来自 project-explorer MCP）
    has_tables  = bool(schema_context)                  # 是否有已有表（来自 polyquery MCP）

    if not has_classes and not has_tables:
        return "new-domain"   # 纯 Greenfield：无任何已有产物
    if has_classes and not has_tables:
        return "new-table"    # Hybrid：有代码，新增数据表
    return "existing"         # 纯 Brownfield：代码和表均已存在
```

三种运行时场景驱动完全不同的生成行为：

场景标识`has_classeshas_tables`对应模式`new-domain`FalseFalse纯 Greenfield`new-table`TrueFalseHybrid`existing`TrueTrue纯 Brownfield

---

## 三、两大上下文文件的差异化来源

### 3.1 `module-map.json`（由 `project-explorer` MCP 生成）

- **Brownfield**：扫描真实 Java 源码（`src/main/java`），提取类名、包路径、方法签名。设计中引用的任何类名**必须存在于此白名单**中。
- **Hybrid**：同 Brownfield，扫描已有代码，但允许新增类标注 `[NEW]`。
- **Greenfield**：文件为空。Gate 2 白名单校验**完全跳过**，所有生成类均标注 `[NEW]`。

### 3.2 `schema-context.json`（由 `polyquery` MCP 或本地 SQL 扫描生成）

- **Brownfield**：包含真实表结构、字段名、类型、约束、索引，优先通过 `refresh-schema-context --from-polyquery` 从数据库实时获取。
- **Greenfield**：文件为空，`new-domain` 场景由此触发。
- **错误哨兵机制**：若 `polyquery` 连接失败，文件写入 `{"__error__": "连接失败原因"}`，流程**立即中止**，防止把"查不到数据库"误判为"这是个 Greenfield 项目"。

---

## 四、Gate 2（设计真实性校验）的差异化行为

Gate 2 是两种模式差异最大的质量门。

### Brownfield / `existing` 场景：严格三级白名单校验

**第一级 — FQN 全限定名匹配**：

- 设计中出现的 `com.company.order.OrderService` 必须与 `module-map.json` 中的真实类路径完全匹配

**第二级 — 简单名消歧**：

- 若 `OrderService` 同时存在于 `order-service` 模块和 `payment-service` 模块，简单名**被拒绝**，必须使用 FQN，并列出所有可用选项

**第三级 — ripgrep 兜底扫描**：

- `module-map.json` 不可用时的降级方案（V1 兼容模式）

**其他校验项**：

- 表名和字段名必须与 `schema-context.json` 一致
- 模块签名与架构约束对照 `constitution.md` 验证
- **绝对禁止**：AI 编造听起来合理但不存在的类名或表名

### Greenfield / `new-domain` 场景：绑过白名单，进入建模模式

- 白名单存在性校验**完全绕过**
- 所有生成类加 `[NEW]` 注解
- AI 对尚未确定的实体写 `"awaiting scaffolding confirmation"`，而非自行编造

---

## 五、AI 提示词的场景化分支

`sdd-generation` Skill 的提示词模板在场景检测后注入不同指令块：

```markdown
{{#if scenario == "new-domain"}}
  ## 新领域建模规则：
  - Service 层：{FeatureName}Service
  - Repository 层：{FeatureName}Repository
  - 所有新类必须标注 [NEW]

{{else if scenario == "new-table"}}
  ## Hybrid 规则：
  - 复用已有类；仅允许新增数据表
  - 新实体：{TableName}DO
  - 新 Mapper：{TableName}Mapper

{{else}}
  ## Brownfield 规则：
  - 必须引用真实已有代码
  - 禁止编造不存在的类名
{{/if}}
```

---

## 六、全维度差异对照表

维度Brownfield (`existing`)Hybrid (`new-table`)Greenfield (`new-domain`)`module-map.json` 状态有真实类列表有真实类列表空`schema-context.json` 状态有真实表结构空空**Gate 2 白名单校验强制 FQN + 简单名校验**对已有类强制**完全跳过**新类名注解要求必须标 `[NEW]`新实体标 `[NEW]`全部标 `[NEW]`AI 编造类名**硬性禁止**仅允许新实体必须写"待确认"AI 提示词分支`{{else}}` — 引用现有代码`{{else if new-table}}{{#if new-domain}}sdd-index-real.json`**最高优先级事实来源**增量增长初始为空`tech-debt.md` 技术债基线必须维护部分适用不适用Gate 5 自定义验证命令支持（已有运行环境）支持不适用Attached Project 扫描核心依赖代码侧扫描无意义错误哨兵保护`__error__` 触发流程中止同左不适用

---

## 七、双索引策略（Brownfield 专属设计）

存量项目维护两份独立索引，Greenfield 项目随功能落地逐步建立：

索引文件作用优先级`sdd-index-design.json`已批准的设计意图，防止并行功能冲突次要`sdd-index-real.json`已落地实现的接口和实体（真实基线）**最高**

**AI 决策优先级**：`sdd-index-real.json` &gt; `sdd-index-design.json` &gt; 通用知识

Greenfield 项目两文件初始为空，每次 Gate 5 通过后 `sync_baseline.py` 自动更新 `sdd-index-real.json`，项目随时间自然过渡为 Brownfield 行为模式。

---

## 八、核心设计哲学

整个差异化架构防止两个**相反方向**的 AI 失误：

### 防止 Brownfield 幻觉

Gate 2 强制比对 `module-map.json`，AI 写的任何类名必须在代码库中真实存在，否则门控失败。杜绝"起了个好听的类名但根本不存在"的设计。

### 防止 Greenfield 误判

`polyquery` 连接失败时，`schema-context.json` 写入 `{"__error__": "..."}` 哨兵值，流程立即中止——而不是把"查不到数据库"误当作"这是 Greenfield 项目"来绕过所有验证。

`detect_scenario()` **是全流程唯一的场景判断入口**，所有下游的提示词注入、门控规则、验证逻辑都通过该函数返回值分叉，保证两种模式下 AI 行为边界清晰、互不干扰。

---

*文档生成日期：2026-05-10 | 项目维护者：stardust_08*