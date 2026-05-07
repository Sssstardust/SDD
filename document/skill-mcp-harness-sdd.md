# AI SDD 自动化系统设计文档
## 架构：Skill + MCP + Harness 三位一体落地方案

**版本:** 3.1
**日期:** 2026-04-16
**适用场景:** 存量 Java/Spring 工程，将 PRD 转化为可落地的技术设计文档（design.md）
**演进策略:** 分三个版本渐进落地，避免一次性引入过重的系统
**当前覆盖范围:** PRD → SDD（设计阶段）+ SDD → Code 闭环（Gate 4 测试骨架生成 / Gate 5 PRD 覆盖验证）

---

## 零、使用前必读

### 0.1 运行前置条件

新成员第一步先确认以下依赖已就绪，否则 V1 第一步就会卡住：

```bash
# 检查脚本：运行后所有项应为 [OK]
echo "=== 前置条件检查 ==="

# 1. ripgrep（gen-context.sh 和 check_class_references.py 依赖）
command -v rg &>/dev/null && echo "[OK] ripgrep" || echo "[FAIL] 请安装 ripgrep: https://github.com/BurntSushi/ripgrep#installation"

# 2. Python 3.10+（type hint list[str] 语法要求）
python3 -c "import sys; assert sys.version_info >= (3,10)" 2>/dev/null \
  && echo "[OK] Python $(python3 --version)" \
  || echo "[FAIL] 需要 Python 3.10+，当前: $(python3 --version 2>&1)"

# 3. Maven 标准目录结构（src/main/java / src/main/resources）
[ -d "src/main/java" ] && echo "[OK] Maven 目录结构" \
  || echo "[WARN] 非标准 Maven 目录，需修改 gen-context.sh 的 src/ 扫描路径"

# 4. polyquery MCP（db-schema 依赖，V2 起使用）
command -v python3 &>/dev/null \
  && python3 -c "import json" 2>/dev/null \
  && echo "[OK] polyquery MCP 通过 Kiro MCP 配置接入，无需本地安装" \
  || echo "[INFO] 确认 polyquery MCP 已在 .kiro/settings/mcp.json 中配置"

# 5. 本地脚本执行（V3 流水线依赖）
python3 -c "import subprocess; subprocess.run(['echo', 'ok'])" 2>/dev/null \
  && echo "[OK] Python subprocess 可用（V3 本地流水线）"

echo "=== 检查完成 ==="
```

**版本要求汇总：**
- ripgrep ≥ 13.0
- Python ≥ 3.10（list[str] type hint）
- Java/Maven 标准目录结构（`src/main/java`、`src/main/resources`）
- polyquery MCP（V2 db-schema 上下文依赖，需在 `.kiro/settings/mcp.json` 中配置数据库连接）
- 本地脚本执行环境（bash / Python，V3 流水线依赖）

---

### 0.2 使用前快速决策树

遇到具体情况不知道怎么处理时，先看这里：

```
我有一个 PRD，想生成设计文档
│
├── 是全新功能（工程里没有相关类）
│   └── project-explorer 会返回空 → sdd-generation 自动切换"新领域模式"
│       → 设计文档中新增类会被标注 [NEW]，Gate 2 会自动跳过 [NEW] 类的白名单校验
│       → 同名类存在于多个包时，用全限定类名消歧：`com.company.order.OrderService`
│       → 架构约束自查需人工确认命名规范
│
├── 是已有功能的迭代改造
│   ├── V1/V2：手动将旧设计文档 内容粘贴到对话上下文
│   │         运行 gen-context.sh 时追加参数：--old-sdd docs/design/{feature}/design-v1.md
│   │         （脚本会将旧设计文档 追加到快照末尾，供 AI 参考）
│   └── V3：run.py 在生成前检查 docs/design/{feature}/ 下是否有已有 design.md
│           有则自动读取并注入为补充上下文（需在 workflow 输入中传入 feature_name）
│
├── PRD 写得不完整（缺少实体/接口描述）
│   ├── 先对照 docs/design/_template/prd-checklist.md 自查（V1 起必须）
│   ├── V1/V2：脚本报错，提示缺少字段，手动补充后重试
│   └── V3：触发澄清模式，workflow 输出缺失字段列表，支持命令行补参
│
├── 质量门禁一直过不了（超过3次）
│   ├── 查看 docs/design/{feature}/design-v{N}-gate-report.json 看具体违规（N 为当前版本号）
│   ├── Gate 1 失败（结构）→ 检查 设计文档模板是否被 AI 改动
│   ├── Gate 2 失败（类名）→ 检查 project-explorer MCP 扫描范围配置
│   ├── Gate 3 失败（语义）→ 查看 arch-standard 规范文档是否有歧义
│   └── 超出重试上限 → 写入 escalation.log（被动记录，需开发者主动通知架构师）
│
└── 多模块工程（order-service / payment-service 分开）
    └── 配置 mcp-servers/project-explorer/config.yaml 的 scan_roots
        见 V2 多模块配置章节
```

---

## 一、总体架构

### 1.1 设计哲学

三层分工，各司其职：

```
┌─────────────────────────────────────────────────────────────────┐
│                          HARNESS 层                             │
│         流程约束 · 质量门禁 · 反馈闭环                           │
│         AGENTS.md / CI Linter / PR Check                       │
├─────────────────────────────┬───────────────────────────────────┤
│          SKILL 层           │           MCP 层                  │
│  Prompt 模板 + 确定性脚本   │  实时感知工程现状，提供动态上下文  │
│                             │                                   │
│  ┌──────────────────────┐   │  ┌─────────────────────────────┐  │
│  │  requirement-analyzer│◄──┼──│  project-explorer-mcp       │  │
│  │                      │   │  │                             │  │
│  │  sdd-generation      │◄──┼──│  db-schema-mcp              │  │
│  │                      │◄──┼──│  arch-standard-mcp          │  │
│  └──────────────────────┘   │  └─────────────────────────────┘  │
└─────────────────────────────┴───────────────────────────────────┘

职责分工：
  Harness = "规则执行者"  → 保证过程不走偏，CI 强制执行
  Skill   = "能力封装者"  → Prompt 模板 + 脚本，两者分离
  MCP     = "情报提供者"  → 解决 AI 幻觉，保证引用真实存在
```

### 1.2 核心问题与解法

AI 生成设计文档 最大的问题是**幻觉**：引用不存在的类名、字段名、接口路径。
三层架构的本质是在 AI 生成前注入真实上下文，生成后用确定性规则校验。

```
幻觉来源                    解法
─────────────────────────────────────────────
不知道工程里有哪些类    →   project-explorer 提供类索引
不知道数据库表结构      →   polyquery MCP 直连数据库实时查询
不知道团队架构规范      →   arch-standard 提供规范文档
生成结构不完整          →   Harness Linter 强制校验
```

### 1.3 端到端数据流（目标态）

```
用户输入 PRD (Markdown)
         │
         ▼
[Stage 1: PRD 解析]
   └─ requirement-analyzer Skill
      → structured-prd.json

         │
         ▼
[Stage 2: 上下文注入]
   ├─ project-explorer  → module-map.json    (现有类列表)
   ├─ polyquery MCP    → schema-context.json (实时表结构)
   └─ arch-standard     → constraints.json   (架构规范)

         │
         ▼
[Stage 3: 设计文档生成]
   └─ sdd-generation Skill
      → draft-design.md

         │
         ▼
[Stage 4: 质量门禁]
   ├─ 结构完整性 Linter    (确定性，毫秒级，必过)
   ├─ 类名存在性校验        (白名单模式，秒级，必过；字段/方法级校验见 V4 规划)
   └─ 架构规范语义审计     (AI 评审，30s，必过)
         │
    ┌────┴────┐
   Pass      Fail → 附带具体违规原因，反馈重新生成（最多3次）
    │                超出次数 → 人工介入
    ▼
[输出 final-design.md → docs/design/{feature}/]
```

---

## 二、三版本演进路线

### 版本总览

| 维度 | V1：人工辅助 | V2：半自动化 | V3：全自动闭环 |
|------|------------|------------|--------------|
| 上下文注入 | 脚本生成，手动粘贴 | MCP 自动注入 | MCP 实时注入 |
| 设计文档生成 | AI 辅助，人工触发 | 半自动，人工确认 | 全自动流水线 |
| 质量门禁 | CI 结构检查 | CI + 类名校验 | 本地脚本 + 语义审计 |
| 执行引擎 | 无（手动） | 无（手动触发脚本） | 本地脚本 / Jenkins |
| 团队成本 | 低 | 中 | 高 |
| 适合阶段 | 推广初期，建立规范 | 规范稳定后 | 团队完全接受后 |

---

### V1：人工辅助阶段（Week 1-3）

**目标：** 解决80%的幻觉问题，建立 设计文档规范，让团队形成习惯。不引入任何新的服务依赖。

**核心思路：** 用脚本生成上下文快照，手动粘贴给 AI，用 CI 做结构校验。

#### V1 需要做的事

**1. 建立目录结构**

```
repo-root/
├── docs/
│   ├── design/                     # 设计文档输出目录（Git 管理）
│   │   ├── _template/
│   │   │   ├── design-template.md     # 设计文档标准模板（团队评审确认）
│   │   │   └── prd-checklist.md    # PRD 最小质量要求（进入流程的前置条件）
│   │   └── {feature-name}/
│   │       └── design-v1.md
│   └── arch-standards/             # 架构规范文档（纯 Markdown）
│       ├── layering-rules.md
│       ├── exception-handling.md
│       ├── transaction-rules.md
│       └── api-contract-rules.md
├── scripts/
│   ├── gen-context.sh              # 上下文快照生成脚本
│   └── check_design_structure.py      # 本地结构校验脚本（手动运行或 pre-commit hook）
```

**2. 编写上下文快照脚本**

```bash
#!/bin/bash
# scripts/gen-context.sh
# 用法: ./scripts/gen-context.sh <feature-keyword> [table-keyword] [--old-sdd <path>]
# 示例: ./scripts/gen-context.sh Order order,payment
# 迭代改造示例: ./scripts/gen-context.sh Order order,payment --old-sdd docs/design/order-sync/design-v1.md

KEYWORD=$1
TABLE_KEYWORD=${2:-$KEYWORD}
OUTPUT="docs/design/_context-snapshot.md"

# 解析可选参数 --old-sdd
OLD_SDD=""
for i in "$@"; do
  if [ "$PREV" = "--old-sdd" ]; then OLD_SDD="$i"; fi
  PREV="$i"
done

echo "# 工程上下文快照 - $(date '+%Y-%m-%d %H:%M')" > $OUTPUT
echo "关键词: $KEYWORD" >> $OUTPUT
echo "" >> $OUTPUT

# 1. 相关类列表（Service / Repository / Controller / Entity / DTO）
echo "## 现有相关类" >> $OUTPUT
echo '```' >> $OUTPUT
# 注意：此正则只匹配类名含关键词的类，以下情况会漏扫：
# - 类名不含关键词但高度相关（如 TradeService 处理 Order 逻辑）
# - Interface 和 Abstract Class（class 关键词不同）
# V1 阶段可接受（人工辅助），V2 MCP 的 scan_modules 会补充包名搜索路径
rg --type java -l "class.*(${KEYWORD})" src/ | while read f; do
  classname=$(grep -oP "(?<=class )\w+" "$f" | head -1)
  pkg=$(grep -oP "(?<=^package )[\w.]+" "$f" | head -1)
  echo "${pkg}.${classname}  →  ${f}"
done >> $OUTPUT
echo '```' >> $OUTPUT
echo "" >> $OUTPUT

# 2. 相关类的公开方法签名
echo "## 关键类方法签名" >> $OUTPUT
echo '```java' >> $OUTPUT
rg --type java -l "class.*(${KEYWORD}Service|${KEYWORD}Repository)" src/ | while read f; do
  echo "// $(basename $f)"
  grep -P "public\s+\S+\s+\w+\s*\(" "$f" | grep -v "//" | head -10
  echo ""
done >> $OUTPUT
echo '```' >> $OUTPUT
echo "" >> $OUTPUT

# 3. 数据库表结构（通过 polyquery MCP 查询，V1 阶段手动执行后粘贴）
# V2 起由 polyquery MCP 自动注入，V1 阶段建议手动查询后追加到快照
echo "## 相关表结构（请手动补充，或 V2 起由 polyquery MCP 自动注入）" >> $OUTPUT
echo "# 示例查询（在 AI 工具中调用 polyquery MCP）：" >> $OUTPUT
echo "# mcp_polyquery_describe_table(db_type='oracle', table_name='ORDER', connection_name='pdc')" >> $OUTPUT

# 4. 架构规范摘要
echo "## 架构规范（必须遵守）" >> $OUTPUT
cat docs/arch-standards/layering-rules.md >> $OUTPUT
echo "" >> $OUTPUT
cat docs/arch-standards/transaction-rules.md >> $OUTPUT

# 5. 旧设计文档（迭代改造时使用，手动指定）
if [ -n "$OLD_SDD" ] && [ -f "$OLD_SDD" ]; then
  echo "" >> $OUTPUT
  echo "## 旧版设计文档（本次为迭代改造，请在此基础上修改）" >> $OUTPUT
  echo "来源: $OLD_SDD" >> $OUTPUT
  cat "$OLD_SDD" >> $OUTPUT
  echo "[已追加旧设计文档: $OLD_SDD]"
fi

echo "[完成] 上下文快照已生成: $OUTPUT"
echo "[下一步] 将 $OUTPUT 的内容连同 PRD 一起提供给 AI"
```

**3. 编写 PRD Checklist（进入流程的前置条件）**

PRD 质量是整套流程最大的单点依赖，不完整的 PRD 会在每个阶段产生放大效果。
在 V1 就定义最小质量要求，让问题在进入流程前被拦截，而不是让 AI 来发现。

```markdown
# PRD 最小质量 Checklist
# 文件：docs/design/_template/prd-checklist.md
# 用法：提交 PRD 前自查，所有必填项打勾后才能进入设计文档生成流程

## 必填项（缺少任一项，AI 无法生成有效设计文档）

### 功能描述
- [ ] 功能名称（用于文件命名，建议 snake_case）
- [ ] 功能类型（crud / sync / payment / notification / batch / 其他）
- [ ] 一句话描述：这个功能解决什么问题

### 业务实体
- [ ] 列出所有涉及的业务实体（如：订单、支付记录、用户）
- [ ] 每个实体的操作类型（新增 / 查询 / 修改 / 删除 / 同步）

### 接口需求
- [ ] 至少列出一个需要新增或修改的接口（HTTP 方法 + 路径 + 一句话描述）
- [ ] 调用方是谁（前端 / 其他服务 / 定时任务）

### 业务规则
- [ ] 核心业务规则（如：同一订单不能重复支付、库存不足时拒绝下单）
- [ ] 异常场景（如：支付超时、第三方接口不可用时的处理方式）

## 选填项（有则填，影响 设计文档生成质量）

- [ ] 性能要求（如：P99 < 200ms，日均调用量 10万次）
- [ ] 并发/幂等要求（如：需要防重复提交）
- [ ] 涉及消息队列（生产者/消费者，Topic 名称）
- [ ] 缓存需求（是否用 Redis，缓存粒度和失效策略）
- [ ] 依赖的外部服务或已有接口

## 快速自查命令
# 检查 PRD 是否包含必要关键词（辅助，不能替代人工判断）
grep -c "实体\|接口\|业务规则" your-prd.md
```

**4. 编写 AGENTS.md（AI 行为规范）**

```markdown
# AGENTS.md — 设计文档生成规范

## 你的任务
将 PRD 转化为可落地的技术设计文档（design.md）。

## 使用前提
在调用我之前，请先运行：
  ./scripts/gen-context.sh <feature-keyword>
并将生成的 _context-snapshot.md 内容粘贴到对话中。

## 生成规则（不可违反）
1. 只能引用上下文快照中存在的类名，禁止凭空创造
2. 字段名必须与表结构中的字段名完全一致
3. 必须按 docs/design/_template/design-template.md 的结构输出
4. 多模块工程中，若同名类存在于多个包，必须用全限定类名（FQN）消歧
   示例：`com.company.order.OrderService`、`com.company.payment.OrderService`
   Gate 2 会优先识别 FQN 格式做精确校验，无歧义时简单类名也可接受
4. 所有接口必须有 OpenAPI 格式的契约定义
5. 数据库变更必须包含回滚脚本
6. 认知复杂度预估 ≤ 15，超出则拆分子任务

## 设计文档必须包含的七个章节
1. 领域模型映射
2. 核心流程（含 Mermaid 序列图）
3. 接口契约（含 OpenAPI 片段）
4. 数据库变更（含回滚脚本）
5. 异常处理
6. 架构约束自查
12. 验收标准矩阵（Gate 4 测试骨架生成依赖此节）

## 可选章节（按 feature_type 决定是否需要）
- §7 缓存策略（涉及 Redis 时必填：缓存粒度、Key 设计、失效策略）
- §8 并发与幂等（高并发或需防重时必填：分布式锁方案、唯一键约束）
- §9 消息队列（涉及 MQ 时必填：Topic、生产者/消费者处理逻辑、失败重试）
- §10 性能非功能需求（P99 目标、批处理量级、连接池配置）

## 验收标准矩阵生成规则（§12，必须输出）
在 设计文档末尾必须生成 §12 验收标准矩阵，来源如下：
- REQ-ID：从输入的 structured-prd.json 的 requirements[] 数组中提取，每条需求对应一行
- 验收条件：从 §2 核心流程分支 + §5 异常处理表提炼为可测量的断言描述
- 测试类型：根据验收条件性质选择（集成测试 / 单元测试 / 接口测试 / 负向测试）
- P级：从 PRD 需求优先级字段直接继承（P0 = 阻断发布，P1 = 警告不阻断）

示例输出格式：
```markdown
## 12. 验收标准矩阵

| REQ-ID   | PRD 原文摘要            | 验收条件（可测量）                            | 测试类型   | P级 |
|----------|------------------------|---------------------------------------------|-----------|-----|
| REQ-001  | 下单后库存实时扣减       | 下单成功后 inventory.quantity -= orderQty    | 集成测试   | P0  |
| REQ-002  | 支付超时取消订单         | 超时 30min 后订单状态变为 CANCELLED           | 单元测试   | P0  |
| REQ-003  | 重复提交订单幂等保护     | 相同 idempotencyKey 第二次请求返回 200+原结果 | 接口测试   | P1  |
| REQ-004  | 库存不足时明确报错       | quantity=0 时返回 HTTP 400 + BizCode 1001   | 负向测试   | P0  |
```

**注意：** §12 是 Gate 4 测试骨架生成的直接输入，不得省略，且每个 REQ-ID 必须有对应的可测量验收条件，禁止使用"正常运行"、"按预期工作"等模糊描述。

## 迭代改造规则
- 当上下文中包含旧版设计文档 时，在新 设计文档末尾必须输出"## 变更摘要"章节
- 格式：新增 / 修改 / 删除，每条变更一行，说明变更原因
- 评审者通过变更摘要快速定位改动范围，不需要逐行对比

## 架构规范速查
- 分层：Controller → Service → Repository，禁止跨层调用
- 事务：@Transactional 只在 Service 层，不在 Controller
- 异常：业务异常统一抛 BizException，全局 @ControllerAdvice 处理
- 命名：Service 方法动词开头，Repository 方法 find/save/delete 开头
```

**4. 编写设计文档标准模板**

```markdown
# 技术设计方案：{{feature_name}}

**创建日期:** {{date}}
**功能类型:** {{feature_type}}
**PRD 来源:** {{prd_link}}
**状态:** Draft / Review / Approved
**评审人:** {{reviewer}}

---

## 1. 领域模型映射

### 1.1 涉及实体
| 实体 | 数据库表 | 现有类 | 操作类型 |
|------|---------|--------|---------|
|      |         |        |         |

### 1.2 实体关系图
```mermaid
erDiagram
```

---

## 2. 核心流程

### 2.1 主流程序列图
```mermaid
sequenceDiagram
```

### 2.2 异常流程
| 异常场景 | 处理方式 | 错误码 |
|---------|---------|-------|
|         |         |       |

---

## 3. 接口契约

```yaml
openapi: 3.0.0
info:
  title: {{feature_name}} API
paths:
```

---

## 4. 数据库变更

### 4.1 变更脚本
```sql
-- 变更脚本
```

### 4.2 回滚脚本
```sql
-- 回滚脚本
```

### 4.3 影响分析
- 影响表：
- 影响接口：
- 是否需要数据迁移：

---

## 5. 异常处理

| 异常类型 | 触发条件 | 错误码 | HTTP 状态码 | 处理方式 |
|---------|---------|-------|------------|---------|
|         |         |       |            |         |

---

## 6. 架构约束自查

- [ ] 无跨层调用（Controller 未直接调用 Repository）
- [ ] 事务边界在 Service 层
- [ ] 异常处理符合 BizException 规范
- [ ] 接口有 OpenAPI 契约定义
- [ ] 数据库变更有回滚脚本
- [ ] 认知复杂度预估 ≤ 15

---

<!-- 可选章节：仅在功能涉及对应场景时填写，不涉及则删除该章节 -->

## 7. 缓存策略（涉及 Redis 时填写）

- 缓存粒度：
- Key 设计（格式、TTL）：
- 失效策略（主动删除 / 被动过期 / 定时刷新）：
- 缓存击穿/穿透/雪崩防护方案：

## 8. 并发与幂等（高并发或需防重时填写）

- 并发风险点：
- 防重方案（分布式锁 / 唯一键约束 / 状态机）：
- 幂等键设计：

## 9. 消息队列（涉及 MQ 时填写）

| 角色 | Topic | 触发条件 | 消费逻辑 | 失败处理 |
|------|-------|---------|---------|---------|
| 生产者 | | | | |
| 消费者 | | | | 重试次数 / 死信队列 |

## 10. 性能非功能需求（有明确性能目标时填写）

- P99 目标：
- 估算日均调用量：
- 特殊资源约束（连接池大小、内存上限）：
- 压测方案（是否需要，量级）：

## 11. 变更摘要（迭代改造时必填，全新功能删除此章节）

- 新增：
- 修改：
- 删除：

## 12. 验收标准矩阵

| REQ-ID   | PRD 原文摘要            | 验收条件（可测量）                            | 测试类型   | P级 |
|----------|------------------------|---------------------------------------------|-----------|-----|
| REQ-001  | 下单后库存实时扣减       | 下单成功后 inventory.quantity -= orderQty    | 集成测试   | P0  |
| REQ-002  | 支付超时取消订单         | 超时 30min 后订单状态变为 CANCELLED           | 单元测试   | P0  |
| REQ-003  | 重复提交订单幂等保护     | 相同 idempotencyKey 第二次请求返回 200+原结果 | 接口测试   | P1  |
| REQ-004  | 库存不足时明确报错       | quantity=0 时返回 HTTP 400 + BizCode 1001   | 负向测试   | P0  |

这一节的生成来源：

REQ-ID 来自 structured-prd.json（requirement-analyzer 已解析）
验收条件 从 ##2 核心流程 + ##5 异常处理 提炼
P级 从 PRD 优先级字段继承
```

**5. 配置本地结构校验（pre-commit hook）**

设计文档只保留在本地，不走 CI/PR 流程。用 git pre-commit hook 在提交前自动校验：

```bash
# .git/hooks/pre-commit（或用 pre-commit 框架管理）
#!/bin/bash
# 只校验本次变更涉及的 设计文档
changed_sdds=$(git diff --cached --name-only | grep "docs/design/.*design.*\.md" | grep -v "_template")
if [ -z "$changed_sdds" ]; then
  exit 0
fi

echo "=== 设计文档结构校验 ==="
failed=0
for f in $changed_sdds; do
  python scripts/check_design_structure.py "$f"
  [ $? -ne 0 ] && failed=1
done
exit $failed
```

也可以手动运行：
```bash
# 校验单个文件
python scripts/check_design_structure.py docs/design/order-sync/design-v1.md

# 校验全部
python scripts/check_design_structure.py docs/design/
```

```python
# scripts/check_design_structure.py
import sys, re
from pathlib import Path

REQUIRED_SECTIONS = [
    r"## 1\. 领域模型",
    r"## 2\. 核心流程",
    r"## 3\. 接口契约",
    r"## 4\. 数据库变更",
    r"## 5\. 异常处理",
    r"## 6\. 架构约束自查",
    r"mermaid",
    r"openapi|paths:",
    r"回滚|ROLLBACK",
    r"## 12\. 验收标准矩阵",   # Gate4 依赖此节生成测试骨架
    r"REQ-\d+",               # 至少有一个 REQ-ID 条目
]

def check(path: str) -> list[str]:
    content = Path(path).read_text(encoding="utf-8")
    errors = []
    for pattern in REQUIRED_SECTIONS:
        if not re.search(pattern, content, re.IGNORECASE):
            errors.append(f"缺少必要内容: {pattern}")
    return errors

if __name__ == "__main__":
    target = Path(sys.argv[1])
    # 兼容两种调用方式：传目录（V1 CI）或传单文件（V3 Gate）
    files = [f for f in target.rglob("design*.md") if "_template" not in str(f)] \
            if target.is_dir() else [target]
    failed = False
    for sdd_file in files:
        errors = check(str(sdd_file))
        if errors:
            print(f"\n[FAIL] {sdd_file}")
            for e in errors:
                print(f"  - {e}")
            failed = True
        else:
            print(f"[OK]   {sdd_file}")
    sys.exit(1 if failed else 0)
```

**V1 验收标准：**
- 团队成员能用 `gen-context.sh` + AI 在30分钟内产出一份结构完整的设计文档
- pre-commit hook 能拦截结构不完整的设计文档 提交
- 用5个真实 PRD 验证，类名引用准确率 > 90%

---

### V2：半自动化阶段（Week 4-7，在 V1 稳定后启动）

**目标：** 用 MCP 替代手动脚本，上下文注入自动化，减少人工操作。CI 增加类名存在性校验。

**前提条件：** V1 已跑稳，团队对 设计文档规范有共识，`arch-standards/` 文档已完善。

**核心变化：**
- `gen-context.sh` 升级为三个 MCP Server（project-explorer / polyquery / arch-standard）
- CI 增加类名存在性校验（白名单模式；字段/方法级校验为 V4 规划）
- Skill 从"Prompt 模板"升级为"Prompt 模板 + 执行脚本"的组合

#### V2 新增目录结构

```
repo-root/
├── mcp-servers/                    # 新增：MCP Server 实现
│   ├── project-explorer/
│   │   ├── server.py
│   │   └── README.md
│   ├── db-schema/
│   │   └── README.md               # 已废弃：改用 polyquery MCP 直连数据库
│   └── arch-standard/
│       ├── server.py               # 读取 docs/arch-standards/ 目录
│       └── README.md
├── skills/                         # 新增：Skill 定义（Prompt + 脚本分离）
│   ├── requirement-analyzer/
│   │   ├── SKILL.md                # Agent 发现入口：触发条件、不触发条件、步骤说明
│   │   ├── prompt.md               # Prompt 模板（给 AI 看的，频繁迭代）
│   │   └── extract.py              # 确定性提取脚本（不依赖 AI，稳定）
│   └── sdd-generation/
│       ├── SKILL.md                # Agent 发现入口
│       ├── prompt.md               # Prompt 模板
│       └── assemble_context.py     # 上下文组装脚本
└── scripts/
    └── check_class_references.py   # 新增：类名存在性校验（pre-commit hook 调用）
```

#### V2 SKILL.md 格式规范

每个 Skill 目录下的 `SKILL.md` 是 Agent 的发现入口，必须包含触发条件，让 AI 知道何时、如何使用这个 Skill：

```markdown
# SKILL.md — requirement-analyzer

## 触发条件（满足任一即触发）
- 用户提供了 PRD 文档（Markdown 或纯文本）
- 对话中出现"解析需求"、"分析PRD"、"需求分析"等关键词
- workflow.yaml Stage 1 显式调用

## 不触发条件
- 用户直接要求生成设计文档（必须先经过 PRD 解析，不可跳过）
- 输入内容不是业务需求文档

## 执行步骤
1. 读取 PRD 文档全文
2. 调用 prompt.md 中的 Prompt 模板，提取结构化字段
3. 对提取结果做确定性校验（extract.py），确保 required 字段非空
4. 输出 structured-prd.json

## 文件说明
- prompt.md：发给 AI 的 Prompt，根据生成质量频繁迭代
- extract.py：确定性校验逻辑，不依赖 AI，修改需谨慎

## 验收标准
- feature_type 是有效值（crud/sync/payment/notification/batch 或自定义字符串）
- entities 列表至少含一个元素
- apis 列表至少含一个元素
```

```markdown
# SKILL.md — sdd-generation

## 触发条件（满足全部才触发）
- workflow.yaml Stage 3 显式调用
- workspace 下已存在：structured-prd.json / module-map.json / schema-context.json / constraints.json

## 不触发条件
- 上述任一上下文文件缺失（缺少上下文会导致幻觉，必须中止）
- 用户未经 PRD 解析直接要求生成

## 关键约束
- 只能引用 module-map.json 中存在的类名
- 字段名必须与 schema-context.json 中的字段名完全一致
- 如果是重试（gate-report.json 存在），必须逐条修复上一轮的违规项

## 文件说明
- prompt.md：核心 Prompt 模板，包含上下文注入占位符
- assemble_context.py：将四个 JSON 文件组装成 Prompt 输入，不依赖 AI
```

#### V2 MCP Server 实现

**project-explorer MCP（核心，优先实现）**

```python
# mcp-servers/project-explorer/server.py
from mcp.server import Server
from mcp.types import Tool, TextContent
import subprocess, json, re
from pathlib import Path

server = Server("project-explorer")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="scan_modules",
            description="扫描工程模块，返回与关键词相关的类列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "include_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["Service", "Repository", "Controller", "Entity", "DTO",
                                    "Mapper", "FeignClient", "Listener", "Consumer",
                                    "Job", "Task", "Handler", "Converter", "Assembler"]
                    }
                },
                "required": ["keywords"]
            }
        ),
        Tool(
            name="verify_class_exists",
            description="验证类名是否存在于当前代码库",
            inputSchema={
                "type": "object",
                "properties": {
                    "class_names": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["class_names"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "scan_modules":
        return await _scan_modules(arguments)
    elif name == "verify_class_exists":
        return await _verify_class_exists(arguments)

async def _scan_modules(args: dict) -> list[TextContent]:
    keywords = args["keywords"]
    force_refresh = args.get("force_refresh", False)
    include_types = args.get("include_types", [
        "Service", "Repository", "Controller", "Entity", "DTO",
        "Mapper", "FeignClient", "Listener", "Consumer",
        "Job", "Task", "Handler", "Converter", "Assembler"
    ])

    # 缓存命中：直接返回，跳过全量扫描（大型工程节省 5-10s）
    if not force_refresh and _cache_is_valid():
        cached = _load_cache()
        if cached is not None:
            # 从缓存中过滤出本次请求的 keywords
            return [TextContent(type="text", text=json.dumps(
                {k: cached.get(k, []) for k in keywords},
                ensure_ascii=False, indent=2
            ))]

    results = {}
    scan_roots = SCAN_ROOTS  # 来自 config.yaml，支持多模块工程

    for keyword in keywords:
        found_files: set[str] = set()

        for cls_type in include_types:
            for root in scan_roots:
                # 路径1：类名含关键词（大小写不敏感）
                pattern = f"(?i)class\\s+\\w*{keyword}\\w*{cls_type}|class\\s+{cls_type}\\w*{keyword}"
                cmd = ["rg", "--type", "java", "-l", pattern, root]
                result = subprocess.run(cmd, capture_output=True, text=True)
                found_files.update(f for f in result.stdout.strip().split("\n") if f)

        # 路径2：包名含关键词（补充漏扫，如 TradeService 在 com.company.order 包下）
        for root in scan_roots:
            pkg_pattern = f"(?i)^package\\s+[\\w.]*{keyword}"
            cmd = ["rg", "--type", "java", "-l", pkg_pattern, root]
            result = subprocess.run(cmd, capture_output=True, text=True)
            found_files.update(f for f in result.stdout.strip().split("\n") if f)

        # 路径3：Interface 和 Abstract Class（interface/abstract class 关键词不同）
        for root in scan_roots:
            iface_pattern = f"(?i)(?:interface|abstract\\s+class)\\s+\\w*{keyword}"
            cmd = ["rg", "--type", "java", "-l", iface_pattern, root]
            result = subprocess.run(cmd, capture_output=True, text=True)
            found_files.update(f for f in result.stdout.strip().split("\n") if f)

        found = [info for f in found_files if (info := _extract_class_info(f))]
        results[keyword] = found

    # 写入缓存（全量扫描结果，下次调用直接命中）
    if CACHE_ENABLED:
        # 合并已有缓存（避免覆盖其他 keyword 的结果）
        existing = _load_cache() or {}
        existing.update(results)
        _save_cache(existing)

    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]

async def _verify_class_exists(args: dict) -> list[TextContent]:
    results = {}
    for class_name in args["class_names"]:
        # 覆盖 class / interface / enum / record，与 _extract_class_info 保持一致
        # 使用 SCAN_ROOTS 支持多模块工程，与 _scan_modules 保持一致
        found_files = []
        for root in SCAN_ROOTS:
            cmd = ["rg", "--type", "java", "-l",
                   f"(?:class|interface|enum|record)\\s+{class_name}\\b", root]
            result = subprocess.run(cmd, capture_output=True, text=True)
            found_files.extend(f for f in result.stdout.strip().split("\n") if f)
        results[class_name] = {"exists": len(found_files) > 0, "files": found_files}
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]

def _extract_class_info(filepath: str) -> dict | None:
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        pkg = re.search(r"^package\s+([\w.]+);", content, re.MULTILINE)
        cls = re.search(r"(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum|record)\s+(\w+)", content)
        if not cls:
            return None
        # 只取 public 方法签名，最多10个
        methods = re.findall(r"public\s+[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)", content)
        return {
            "class_name": cls.group(1),
            "package": pkg.group(1) if pkg else "unknown",
            "file": filepath,
            "public_methods": [f"{m[0]}({m[1]})" for m in methods[:10]]
        }
    except Exception:
        return None

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    asyncio.run(stdio_server(server))
```

**db-schema → 改用 polyquery MCP 直连数据库**

原来的 `mcp-servers/db-schema/server.py`（解析 Flyway changelog）已废弃，改用 **polyquery MCP** 直接查询数据库。

优势对比：

| 维度 | 旧方案（Flyway changelog） | 新方案（polyquery MCP） |
|------|--------------------------|------------------------|
| 数据实时性 | 依赖 changelog 文件，可能滞后 | 直连数据库，实时准确 |
| 字段注释 | 需解析 SQL 注释，不稳定 | 直接读取数据库元数据 |
| 多模块支持 | 需配置多个 changelog 目录 | 通过 connection_name 区分数据源 |
| 维护成本 | 需维护 server.py + 正则解析 | 零维护，polyquery 已内置 |
| 已知限制 | Liquibase XML 不支持、多行 ALTER 解析不完整 | 无 |

**polyquery MCP 配置**

MCP 配置文件路径因 IDE/工具不同而异，选择你们团队使用的工具：

```
IDE / 工具                配置文件路径                                    备注
──────────────────────────────────────────────────────────────────────────────
Kiro                      .kiro/settings/mcp.json                        工作区级；~/.kiro/settings/mcp.json 为全局
Cursor                    .cursor/mcp.json                               工作区级；~/.cursor/mcp.json 为全局
Claude Code (CLI)         ~/.claude/claude_desktop_config.json           全局，无工作区级配置
VS Code + Copilot         .vscode/mcp.json                               需安装 MCP 扩展（如 Continue / Copilot MCP）
Windsurf                  ~/.codeium/windsurf/mcp_config.json            全局
Gemini CLI                ~/.gemini/settings.json                        或 gemini mcp add <server> 命令写入
Codex CLI                 ~/.codex/config.json                           或 codex mcp add <server> 命令写入
```

所有工具的配置内容格式相同（标准 MCP JSON），只是文件路径不同：

```json
{
  "mcpServers": {
    "polyquery": {
      "command": "uvx",
      "args": ["polyquery-mcp@latest"],
      "env": {
        "ORACLE_PDC_URL": "oracle+cx_oracle://user:pass@host:1521/pdc",
        "ORACLE_TOB_URL": "oracle+cx_oracle://user:pass@host:1521/tob",
        "MYSQL_DEFAULT_URL": "mysql+pymysql://user:pass@host:3306/dbname"
      }
    }
  }
}
```

> 团队统一工具时，建议把配置文件路径写进 `CONTRIBUTING.md`，避免新成员找不到配置位置。
> 同时把 `project-explorer` 和 `arch-standard` 两个自定义 MCP 的注册方式也一并写入，
> 格式参考：`"command": "python", "args": ["mcp-servers/project-explorer/server.py"]`。

**assemble_context.py 中调用 polyquery 获取表结构：**

```python
# skills/sdd-generation/assemble_context.py 中的 schema 获取逻辑
# 通过 polyquery MCP 的 describe_table / query_database 工具获取实时表结构

async def fetch_schema_via_polyquery(
    entities: list[str],
    db_type: str,
    connection_name: str
) -> dict:
    """
    调用 polyquery MCP 获取相关表结构。
    db_type: oracle / mysql / postgres 等
    connection_name: 对应 mcp.json 中配置的数据源名称
    """
    import subprocess, json

    results = {}
    for entity in entities:
        # 1. 先用 list_tables 模糊匹配表名
        list_cmd = {
            "tool": "mcp_polyquery_list_tables",
            "args": {"db_type": db_type, "connection_name": connection_name}
        }
        # 2. 对匹配到的表调用 describe_table 获取字段结构
        # 实际调用由 AI 工具层（Kiro/Claude）通过 MCP 协议执行
        # 这里记录调用意图，run.py 在 AI 上下文中触发
        results[entity] = {
            "query_intent": f"describe tables matching '{entity}' in {connection_name}",
            "mcp_tool": "mcp_polyquery_describe_table",
            "params": {
                "db_type": db_type,
                "connection_name": connection_name,
                "table_name": f"<matched_table_for_{entity}>"
            }
        }
    return results
```

**在 AGENTS.md / SKILL.md 中的调用约定：**

```markdown
## 数据库上下文获取（Stage 2）

使用 polyquery MCP 获取相关表结构，调用顺序：

1. 调用 `mcp_polyquery_list_tables` 列出所有表
   - db_type: oracle（或 mysql/postgres，根据工程配置）
   - connection_name: 对应数据源（如 pdc、tob）

2. 根据 PRD 中的业务实体名，模糊匹配相关表名

3. 对每个匹配表调用 `mcp_polyquery_describe_table` 获取字段结构
   - 返回字段名、类型、注释等元数据

4. 将结果写入 {{workspace}}/schema-context.json

注意：字段名和类型必须与 describe_table 返回结果完全一致，
设计文档中不得引用不存在的字段。
```

**arch-standard MCP（读文件，无外部依赖）**

```python
# mcp-servers/arch-standard/server.py
from mcp.server import Server
from mcp.types import Tool, TextContent
from pathlib import Path
import json

server = Server("arch-standard")
STANDARDS_DIR = Path("docs/arch-standards")

# feature_type → 需要重点关注的规范文件
FEATURE_RULE_MAP = {
    "crud":         ["layering-rules.md", "exception-handling.md"],
    "sync":         ["layering-rules.md", "exception-handling.md", "transaction-rules.md"],
    "payment":      ["layering-rules.md", "exception-handling.md", "transaction-rules.md", "api-contract-rules.md"],
    "notification": ["layering-rules.md", "exception-handling.md", "api-contract-rules.md"],
    "batch":        ["layering-rules.md", "exception-handling.md", "transaction-rules.md"],
}

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_applicable_rules",
            description="根据功能类型获取适用的架构规范",
            inputSchema={
                "type": "object",
                "properties": {
                    "feature_type": {"type": "string"},
                    "rule_files": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["feature_type"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_applicable_rules":
        feature_type = arguments["feature_type"]
        # 支持自定义规则文件，兜底用 feature_type 映射
        rule_files = arguments.get("rule_files") or FEATURE_RULE_MAP.get(feature_type, [
            "layering-rules.md", "exception-handling.md"
        ])
        rules = {}
        for filename in rule_files:
            rule_file = STANDARDS_DIR / filename
            if rule_file.exists():
                rules[filename] = rule_file.read_text(encoding="utf-8")
            else:
                rules[filename] = f"[文件不存在: {filename}，请在 docs/arch-standards/ 下创建]"
        return [TextContent(type="text", text=json.dumps({
            "feature_type": feature_type,
            "rules": rules
        }, ensure_ascii=False, indent=2))]

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    asyncio.run(stdio_server(server))
```

#### V2 CI 增强：类名存在性校验

```python
# scripts/check_class_references.py
# 在 CI 中运行，检查 设计文档引用的类名是否真实存在于代码库
# 白名单模式：module-map.json 里有的类才是合法引用
# 比后缀规则更健壮：不需要维护后缀列表，Event/Handler/Converter 等都能覆盖
import sys, re, json, subprocess
from pathlib import Path

# 匹配 设计文档中反引号包裹的所有大写开头的 Java 类名（不限后缀）
CLASS_PATTERN = re.compile(r"`([A-Z][a-zA-Z0-9]+)`")
# 全限定类名模式：`com.company.order.OrderService`
FQN_PATTERN = re.compile(r"`((?:[a-z][a-z0-9]*\.)+[A-Z][a-zA-Z0-9]+)`")

def load_whitelist(module_map_path: str) -> dict:
    """
    从 module-map.json 加载合法类名白名单。
    返回结构：
      {
        "fqn":    {"com.company.order.OrderService": True, ...},  # 全限定名集合
        "simple": {"OrderService": ["com.company.order", "com.company.payment"], ...}
      }
    Gate 2 优先用 FQN 精确匹配；无 FQN 时用 simple name + 消歧逻辑。
    """
    if not Path(module_map_path).exists():
        return {}
    module_map = json.loads(Path(module_map_path).read_text())
    fqn_set: set[str] = set()
    simple_map: dict[str, list[str]] = {}
    for keyword, classes in module_map.items():
        for cls in classes:
            name = cls["class_name"]
            pkg  = cls.get("package", "")
            if pkg:
                fqn_set.add(f"{pkg}.{name}")
            simple_map.setdefault(name, []).append(pkg or keyword)
    return {"fqn": fqn_set, "simple": simple_map}

def verify_class_via_rg(class_name: str) -> bool:
    """白名单不存在时的兜底：直接用 rg 搜索代码库"""
    result = subprocess.run(
        ["rg", "--type", "java", "-l", f"(?:class|interface|enum)\\s+{class_name}\\b", "src/"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())

def load_skip_words(config_path: str = "mcp-servers/project-explorer/config.yaml") -> set[str]:
    """
    从 config.yaml 加载 SKIP_WORDS，支持团队按业务领域扩展。
    文件不存在时使用内置默认值，避免强依赖配置文件。
    """
    defaults = {"GET", "POST", "PUT", "DELETE", "HTTP", "API", "URL", "JSON",
                "SQL", "DDL", "SDD", "PRD", "MCP", "CI", "PR", "OK"}
    try:
        import yaml
        cfg = yaml.safe_load(Path(config_path).read_text())
        extra = set(cfg.get("skip_words", []))
        return defaults | extra
    except Exception:
        return defaults

def check(design_path: str, whitelist: dict) -> list[str]:
    content = Path(design_path).read_text(encoding="utf-8")

    fqn_set    = whitelist.get("fqn", set())
    simple_map = whitelist.get("simple", {})

    # 1. 提取 [NEW] 标注的类名，跳过白名单校验
    new_class_pattern = re.compile(r"`([A-Z][a-zA-Z0-9]+)`\s*\[NEW\]|\[NEW\]\s*`([A-Z][a-zA-Z0-9]+)`")
    new_classes = {m.group(1) or m.group(2) for m in new_class_pattern.finditer(content)}

    # 2. 提取 设计文档中所有全限定类名引用（优先路径）
    #    格式：`com.company.order.OrderService`
    fqn_refs = {m.group(1) for m in FQN_PATTERN.finditer(content)}

    # 3. 提取 设计文档中所有简单类名引用（兜底路径）
    simple_refs = set(CLASS_PATTERN.findall(content))
    SKIP_WORDS = load_skip_words()   # 从 config.yaml 读取，支持团队扩展
    simple_refs -= SKIP_WORDS
    simple_refs -= new_classes
    # 已经用 FQN 表达的类，从 simple_refs 中移除（避免重复校验）
    fqn_simple_names = {fqn.rsplit(".", 1)[-1] for fqn in fqn_refs}
    simple_refs -= fqn_simple_names

    errors = []

    if whitelist:
        # --- FQN 校验（精确，无歧义）---
        for fqn in fqn_refs:
            if fqn not in fqn_set:
                simple_name = fqn.rsplit(".", 1)[-1]
                if simple_name in simple_map:
                    valid = ", ".join(f"`{pkg}.{simple_name}`" for pkg in simple_map[simple_name])
                    errors.append(f"全限定类名 `{fqn}` 不存在，有效引用：{valid}")
                else:
                    errors.append(f"全限定类名 `{fqn}` 不存在于代码库")

        # --- 简单类名校验（需消歧）---
        for name in simple_refs:
            if name not in simple_map:
                errors.append(f"引用了不在 module-map.json 中的类: `{name}`（如为新建类请加 [NEW] 标注）")
            elif len(simple_map[name]) > 1:
                # 同名类存在于多个包，必须用 FQN 消歧
                valid = ", ".join(f"`{pkg}.{name}`" for pkg in simple_map[name])
                errors.append(
                    f"类 `{name}` 存在于多个包（{', '.join(simple_map[name])}），"
                    f"请改用全限定类名消歧，有效引用：{valid}"
                )
            # else: 单包，简单类名即可，通过
    else:
        # 降级模式：rg 搜索（V1 兼容，无 module-map.json 时使用）
        for name in simple_refs | fqn_simple_names:
            if not verify_class_via_rg(name):
                errors.append(f"引用了不存在的类: `{name}`（如为新建类请加 [NEW] 标注）")

    return errors

if __name__ == "__main__":
    target = Path(sys.argv[1])
    # 尝试加载 module-map.json（V2+ 有，V1 没有）
    module_map_path = sys.argv[2] if len(sys.argv) > 2 else "docs/design/_module-map.json"
    whitelist = load_whitelist(module_map_path)

    # 兼容两种调用方式：传目录（V1 CI）或传单文件（V3 Gate）
    files = [f for f in target.rglob("design*.md") if "_template" not in str(f)] \
            if target.is_dir() else [target]
    failed = False
    for sdd_file in files:
        errors = check(str(sdd_file), whitelist)
        if errors:
            print(f"\n[FAIL] {sdd_file}")
            for e in errors:
                print(f"  - {e}")
            failed = True
    sys.exit(1 if failed else 0)
```

**V2 验收标准：**
- 三个 MCP Server 在 Cursor/Claude Code/Kiro 中均可正常调用
- pre-commit hook 能拦截引用不存在类名的设计文档（白名单模式，见下方 check_class_references.py）
- 上下文注入不再需要手动操作
- 用10个真实 PRD 验证，类名引用准确率 > 99%
- **polyquery MCP 连通性验收：** 确认 `mcp_polyquery_list_tables` 和 `mcp_polyquery_describe_table` 在 AI 工具中可正常调用，能返回目标数据库的表结构

#### V2 补充设计：Context Trimmer（上下文裁剪）

MCP 返回的原始数据在大型工程中可能很大（几十个类、多张大表），全量注入 Prompt 会撑爆上下文窗口或导致模型注意力分散。`assemble_context.py` 在组装 Prompt 前必须做裁剪：

```python
# skills/sdd-generation/assemble_context.py
"""
Context Trimmer：将 MCP 原始输出裁剪为精简上下文，再注入 Prompt
裁剪策略：相关性优先，控制总 token 数上限
预算配置：从 mcp-servers/project-explorer/config.yaml 读取，支持按工程规模调整
"""
import json, yaml
from pathlib import Path

def _load_budget() -> dict:
    """从 config.yaml 读取预算，不存在时使用默认值"""
    config_path = Path("mcp-servers/project-explorer/config.yaml")
    if config_path.exists():
        cfg = yaml.safe_load(config_path.read_text())
        b = cfg.get("context_budget", {})
        return {
            "classes": b.get("classes", 60),
            "columns": b.get("columns", 80),
            "rules":   b.get("rules_chars", 8000) // 2,  # chars → token 粗估
        }
    return {"classes": 60, "columns": 80, "rules": 4000}

BUDGET = _load_budget()

def trim_module_map(module_map: dict, entities: list[str]) -> dict:
    """
    按实体名相关性排序，只保留 Top-N 个类。
    优先级：完全匹配实体名 > 包含实体名 > 其他
    输出格式与输入保持一致：{keyword: [class_list]}
    """
    entity_names = [e.lower() for e in entities]
    scored = []
    for keyword, classes in module_map.items():
        for cls in classes:
            name = cls["class_name"].lower()
            score = 2 if any(e == name or name.startswith(e) for e in entity_names) \
                    else 1 if any(e in name for e in entity_names) \
                    else 0
            scored.append((score, keyword, cls))

    scored.sort(key=lambda x: -x[0])
    top_entries = scored[:BUDGET["classes"]]

    # 保持原始 {keyword: [class_list]} 结构，只是过滤掉低分类
    result: dict[str, list] = {}
    for _, keyword, cls in top_entries:
        result.setdefault(keyword, []).append(cls)
    return result

def trim_schema_context(schema_context: dict) -> dict:
    """
    每张表只保留前 N 个字段，过滤掉纯审计字段（create_time/update_time/is_deleted）
    """
    AUDIT_FIELDS = {"create_time", "update_time", "created_by", "updated_by",
                    "is_deleted", "del_flag", "version", "remark"}
    trimmed = {}
    for table, info in schema_context.items():
        columns = [c for c in info.get("columns", [])
                   if c["name"] not in AUDIT_FIELDS]
        trimmed[table] = {**info, "columns": columns[:BUDGET["columns"]]}
    return trimmed

def trim_constraints(constraints: dict) -> dict:
    """
    规范文档按 feature_type 已经做了筛选，这里只做长度截断
    """
    result = {}
    total_chars = 0
    char_limit = BUDGET["rules"] * 2  # 粗略估算：1 token ≈ 2 中文字符
    for rule_name, content in constraints.get("rules", {}).items():
        if total_chars >= char_limit:
            break
        remaining = char_limit - total_chars
        result[rule_name] = content[:remaining]
        total_chars += len(content[:remaining])
    return {**constraints, "rules": result}

def assemble(workspace: str, entities: list[str]) -> dict:
    ws = Path(workspace)
    module_map  = json.loads((ws / "module-map.json").read_text())
    constraints = json.loads((ws / "constraints.json").read_text())

    # schema-context.json 由 polyquery MCP 写入，需区分三种状态：
    # 1. 文件不存在或内容为 {}  → 空结果，表示无匹配表（new-table 场景），流程继续
    # 2. 文件包含 {"__error__": ...} → polyquery 调用失败（网络/权限/开发库不可达）
    #    此时不能用空结果推断 new-table，否则会生成本不需要新建的表
    #    必须中止流程，由开发者手动处理后重试（或降级为 V1 手动粘贴表结构）
    # 3. 正常表结构数据 → 直接使用
    schema_path = ws / "schema-context.json"
    if not schema_path.exists():
        schema_context = {}
        schema_error   = None
    else:
        raw = json.loads(schema_path.read_text())
        if "__error__" in raw:
            # polyquery 调用失败，不能用空结果推断 new-table，必须中止或降级
            schema_error   = raw["__error__"]
            schema_context = {}
        else:
            schema_error   = None
            schema_context = raw

    trimmed_map    = trim_module_map(module_map, entities)
    trimmed_schema = trim_schema_context(schema_context)
    # 注意：detect_scenario 在裁剪后的数据上运行。
    # 相关类理论上不会被裁剪，但若 context_budget.classes 设置过小，
    # 边缘相关类可能被截断，导致 existing 被误判为 new-domain。
    # 如出现误判，调大 config.yaml 的 context_budget.classes 即可。
    scenario = detect_scenario(trimmed_map, trimmed_schema)

    result = {
        "module_map":     trimmed_map,
        "schema_context": trimmed_schema,
        "constraints":    trim_constraints(constraints),
        "scenario":       scenario,
    }
    if schema_error:
        # 把错误信息透传给 run.py，由调用方决定是中止还是带警告继续
        # 注意：run.py 应当在检测到 schema_error 时中止流程并打印明确错误信息，
        # 而不是静默继续——静默继续会让 scenario 误判为 new-table，
        # 导致 设计文档里出现本不需要新建的表。
        # 降级选项：开发者可手动将表结构写入 schema-context.json 后重试（V1 兼容模式）
        result["schema_error"] = schema_error
    return result
```

#### V2 补充设计：多模块工程支持

单模块 Maven 工程直接扫 `src/`，多模块工程需要配置扫描根目录，避免类名冲突：

```yaml
# mcp-servers/project-explorer/config.yaml
scan_roots:
  - "order-service/src/main/java"
  - "payment-service/src/main/java"
  - "common/src/main/java"

# 模块前缀映射，用于在 设计文档中标注类所属模块
module_prefix_map:
  "com.company.order":   "order-service"
  "com.company.payment": "payment-service"
  "com.company.common":  "common"

# 当同名类出现在多个模块时的处理策略
# disambiguate: 在类名后附加模块标注，如 OrderService[order-service]
# first-match:  只返回第一个匹配（适合类名唯一的工程）
duplicate_strategy: disambiguate

# polyquery MCP 数据源配置（db_type 和 connection_name 对应 mcp.json 中的配置）
# 用于 assemble_context.py 调用 polyquery 获取表结构
polyquery:
  db_type: oracle          # oracle / mysql / postgres / sqlite 等
  connection_name: pdc     # 对应 mcp.json 中配置的数据源名称
  # 多数据源示例（按业务模块区分）：
  # connections:
  #   - name: pdc
  #     db_type: oracle
  #   - name: tob
  #     db_type: oracle

# 上下文裁剪预算（供 assemble_context.py 读取，按工程规模调整）
# 小型工程可适当降低，大型单体工程可适当提高
context_budget:
  classes: 60        # 最多保留的类签名条目数
  columns: 80        # 每张表最多保留的字段数
  rules_chars: 8000  # 规范文档最多字符数（约 4000 token）

# 扫描结果缓存（解决大型工程全量扫描性能问题）
# 中等规模 Java 工程（3000+ 类）每次全量扫描约 5-10s，缓存可将重复调用降至毫秒级
# polyquery 已是实时查 DB，class map 可以接受一定延迟
cache:
  enabled: true
  path: ".cache/module-map-snapshot.json"   # 缓存文件路径（建议加入 .gitignore）
  ttl_minutes: 30                           # 缓存有效期，0 表示禁用 TTL（手动刷新）
  # 失效策略：文件修改时间 + TTL 双重判断
  # - 任意 scan_roots 下有 .java 文件修改时间晚于缓存时间 → 自动失效
  # - 超过 ttl_minutes → 自动失效
  # 手动强制刷新：删除 cache.path 文件，或调用 scan_modules 时传入 force_refresh=true

# SKIP_WORDS：类名校验时跳过的大写词（从代码中提取到此处，团队可按需扩展）
# 每个团队的业务领域都有自己的缩写，在此处添加，无需修改脚本
skip_words:
  - GET
  - POST
  - PUT
  - DELETE
  - HTTP
  - API
  - URL
  - JSON
  - SQL
  - DDL
  - SDD
  - PRD
  - MCP
  - CI
  - PR
  - OK
  # 按业务领域扩展示例（ERP/OA/物流等）：
  # - ERP
  # - OA
  # - TMS
  # - WMS
  # - SKU
  # - BOM
```

`server.py` 读取配置：

```python
# mcp-servers/project-explorer/server.py 顶部增加配置加载
import yaml, time, hashlib
from pathlib import Path

_config_path = Path(__file__).parent / "config.yaml"
_config = yaml.safe_load(_config_path.read_text()) if _config_path.exists() else {}

# 默认兜底：单模块工程
SCAN_ROOTS = _config.get("scan_roots", ["src/main/java"])
MODULE_PREFIX_MAP = _config.get("module_prefix_map", {})
DUPLICATE_STRATEGY = _config.get("duplicate_strategy", "first-match")

# 缓存配置
_cache_cfg     = _config.get("cache", {})
CACHE_ENABLED  = _cache_cfg.get("enabled", False)
CACHE_PATH     = Path(_cache_cfg.get("path", ".cache/module-map-snapshot.json"))
CACHE_TTL_SECS = _cache_cfg.get("ttl_minutes", 30) * 60

def _cache_is_valid() -> bool:
    """检查缓存是否有效：TTL 未过期 + scan_roots 下无新修改的 .java 文件"""
    if not CACHE_ENABLED or not CACHE_PATH.exists():
        return False
    cache_mtime = CACHE_PATH.stat().st_mtime
    # TTL 检查
    if CACHE_TTL_SECS > 0 and (time.time() - cache_mtime) > CACHE_TTL_SECS:
        return False
    # 文件修改时间检查：任意 .java 文件比缓存新则失效
    for root in SCAN_ROOTS:
        for java_file in Path(root).rglob("*.java"):
            if java_file.stat().st_mtime > cache_mtime:
                return False
    return True

def _load_cache() -> dict | None:
    try:
        import json
        return json.loads(CACHE_PATH.read_text())
    except Exception:
        return None

def _save_cache(data: dict) -> None:
    try:
        import json
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        pass  # 缓存写入失败不影响主流程
```

#### V2 补充设计：无匹配类时的行为

`scan_modules` 返回空结果时（全新领域），`sdd-generation` 不能静默回退到凭空创造类名，必须切换到"新领域模式"：

```python
# skills/sdd-generation/assemble_context.py 中增加空结果检测
def detect_scenario(module_map: dict, schema_context: dict) -> str:
    """
    返回场景标识，影响 Prompt 策略选择
    - "existing": 有现有类和表，正常引用
    - "new-domain": 无现有类，全新领域，需要设计新类
    - "new-table": 有现有类但无匹配表，需要新建表
    """
    has_classes = any(v for v in module_map.values())
    has_tables  = bool(schema_context)
    if not has_classes and not has_tables:
        return "new-domain"
    if has_classes and not has_tables:
        return "new-table"
    return "existing"
```

在 `prompt.md` 中对应两套 Prompt 策略：

```markdown
<!-- skills/sdd-generation/prompt.md 片段 -->

{{#if scenario == "new-domain"}}
## 特别说明：全新领域
当前工程中没有与本功能相关的现有类。
请基于以下分层规范设计新类，命名遵循团队约定：
- Service 层：{FeatureName}Service
- Repository 层：{FeatureName}Repository / {FeatureName}Mapper
- Entity：{TableName}DO
- DTO：{FeatureName}DTO / {FeatureName}VO

在 设计文档的"架构约束自查"章节，所有新增类必须标注 [NEW]，
表示这是本次新建的类，未复用现有组件。
{{else if scenario == "new-table"}}
## 现有工程中可直接使用的类（禁止引用不在此列表中的类）
{{module_map}}

## 特别说明：需要新建表
当前工程无匹配表结构，需新建表及对应 Entity/Mapper 类。
新建类必须标注 [NEW]，命名遵循团队约定：
- Entity：{TableName}DO
- Mapper：{TableName}Mapper

Gate 2 会自动跳过 [NEW] 标注类的白名单校验，无需担心误报。
{{else}}
## 现有工程中可直接使用的类（禁止引用不在此列表中的类）
{{module_map}}
{{/if}}
```

---

### V3：全自动闭环阶段（Week 8+，在 V2 稳定后启动）

**目标：** 引入自动化流水线，实现 PRD → 设计文档的全自动生成和质量门禁闭环。

**前提条件：** V2 已稳定，MCP 服务可靠，团队对 设计文档质量标准有共识，有明确的 Eval 基准集。

**核心变化：**
- 引入本地执行脚本串联各阶段（不依赖 GitHub Actions）
- 增加 AI 语义审计 Gate
- 实现失败自动反馈重新生成（最多3次）
- 建立度量体系

#### V3 新增目录结构

```
repo-root/
├── .harness/
│   ├── quality-gates/
│   │   └── design-gate.yaml           # 质量门禁配置
│   └── hooks/
│       └── post-design-generate.sh    # 生成后将设计文档写入本地 docs/design/
├── .github/
│   └── workflows/
│       └── prd-to-design.yml          # 可选：团队有 CI 时启用；无 CI 时用本地脚本替代
└── skills/
    ├── requirement-analyzer/
    │   ├── SKILL.md
    │   ├── prompt.md
    │   └── run.py                  # 完整执行脚本（含 AI 调用）
    └── sdd-generation/
        ├── SKILL.md
        ├── prompt.md
        └── run.py                  # 完整执行脚本（含反馈重试）
```

#### V3 workflow 定义

> **架构决策：本地脚本是唯一执行真相。**
> 设计文档只保留在本地，不走 CI/PR 流程。
> 以下描述流程意图，实际执行由本地 Python 脚本串联。
> 团队有 CI 需求时可选择性迁移到 `.github/workflows/prd-to-design.yml`。

```yaml
# 设计参考（非可执行）：流程意图说明
# 实际执行：python scripts/run_pipeline.py --prd <prd_path>
pipeline:
  name: PRD-to-SDD
  version: "1.0"
  max_retries: 3          # 最多重试3次，超出升级人工

  stages:
    - id: parse-requirement
      name: "解析 PRD"
      run: python skills/requirement-analyzer/run.py {{input.prd_path}} {{workspace}}/structured-prd.json
      gate:
        required_fields: [feature_name, feature_type, entities, apis, business_rules]
      on_failure:
        action: clarify            # 不直接 abort，PRD 不完整时向用户提问
        clarify_prompt: |
          PRD 解析不完整，缺少以下字段：{{missing_fields}}
          请选择处理方式：
          1. 补充 PRD 内容后重新运行
          2. 命令行手动指定缺失字段：
               --entities "Order,Payment"
               --feature-type "sync"
               --apis "POST /api/v1/orders"
          注：如果 PRD 确实不包含这些信息，选择方式2手动补充

    - id: fetch-context
      name: "获取工程上下文"
      parallel: true           # 三个 MCP 调用并行执行
      on_partial_failure:      # 明确定义部分失败时的行为
        required: [project-explorer, arch-standard]   # 必须成功，失败则终止
        optional: [polyquery]                         # 允许空返回（全新功能可能没有现有表）
        on_optional_empty:
          # polyquery 返回空结果（无匹配表）→ 写入 {}，标记 scenario=new-table
          polyquery: write_empty_json
        on_optional_error:
          # polyquery 调用失败（网络故障/权限到期/开发库重建）→ 写入错误标记，不能推断 new-table
          # assemble_context.py 检测到 __error__ 字段后会中止流程并提示人工处理
          polyquery: write_error_json   # 写入 {"__error__": "<error_message>", "ts": "<timestamp>"}
      steps:
        - mcp: project-explorer
          tool: scan_modules
          params:
            keywords: "{{structured_prd.entities[*].name}}"
          output: "{{workspace}}/module-map.json"

        - mcp: polyquery
          tool: mcp_polyquery_describe_table
          params:
            db_type: "{{config.polyquery.db_type}}"
            connection_name: "{{config.polyquery.connection_name}}"
            table_name: "{{structured_prd.entities[*].name}}"   # 逐个实体查询匹配表
          output: "{{workspace}}/schema-context.json"
          # 返回空结果时写入 {}，不报错；assemble_context.py 会检测并切换 scenario

        - mcp: arch-standard
          tool: get_applicable_rules
          params:
            feature_type: "{{structured_prd.feature_type}}"
          output: "{{workspace}}/constraints.json"

    - id: generate-sdd
      name: "生成设计文档"
      run: >
        python skills/sdd-generation/run.py
          --workspace {{workspace}}
          --output {{workspace}}/draft-design.md
          --feedback {{workspace}}/gate-report.json        # 首次运行时文件不存在，run.py 内部做判断
          # --previous-design 由 run.py 自动查找 docs/design/{feature_name}/ 下版本号最大的 design-vN.md
          # 文件不存在（全新功能）时跳过，存在时注入为迭代改造上下文
        retry_with_feedback: true

    - id: quality-gate
      name: "质量门禁"
      gate_config: ".harness/quality-gates/design-gate.yaml"
      input:
        draft_design: "{{workspace}}/draft-design.md"
        constraints: "{{workspace}}/constraints.json"
      output: "{{workspace}}/gate-report.json"
      on_fail:
        return_to_stage: generate-sdd
        max_loops: 3
        escalate_on_max:
          action: human-review
          # 人工升级闭环：
          # 1. 自动创建 GitHub Issue，标题：[设计文档 Review] {feature_name} 质量门禁超出重试上限
          # 2. Issue body 包含：每轮 draft-design 内容 + 对应 gate-report.json
          # 3. 指定架构师为 Assignee（从 .harness/config.yaml 读取）
          # 4. 架构师修改 draft-design.md 后，手动重新触发脚本
          notify:
            method: local-log          # 写入 docs/design/{feature}/escalation.log
            assignee_from: ".harness/config.yaml#arch_reviewer"
          resume_trigger: "python skills/sdd-generation/run.py --workspace {{workspace}} --resume"

    - id: save-sdd
      name: "保存设计文档 到本地"
      run: |
        FEATURE_DIR="docs/design/{{structured_prd.feature_name}}"
        mkdir -p "$FEATURE_DIR"
        # 自动计算下一个版本号，避免覆盖历史版本
        VERSION=1
        while [ -f "$FEATURE_DIR/design-v${VERSION}.md" ]; do VERSION=$((VERSION+1)); done
        SDD_PATH="$FEATURE_DIR/design-v${VERSION}.md"
        cp {{workspace}}/draft-design.md "$SDD_PATH"
        cp {{workspace}}/gate-report.json "$FEATURE_DIR/design-v${VERSION}-gate-report.json"
        echo "[完成] 设计文档已保存至 $SDD_PATH"
        # 不做 git commit / PR，由开发者自行决定何时提交
```

#### V3 质量门禁配置

```yaml
# .harness/quality-gates/design-gate.yaml
gates:

  # Gate 1: 结构完整性（确定性，毫秒级）
  - id: structure-completeness
    type: script
    run: python scripts/check_design_structure.py {{draft_design}}
    on_fail: return_feedback   # 返回具体缺失章节

  # Gate 2: 类名存在性（MCP 调用，秒级）
  - id: class-existence
    type: script
    run: python scripts/check_class_references.py {{draft_design}} {{workspace}}/module-map.json
    on_fail: return_feedback

  # Gate 3: 架构规范语义审计（AI 评审，30s）
  # 注意：只在 Gate 1 和 Gate 2 都通过后才执行，避免浪费 token
  # 上下文控制：提取 §6（自查结论）+ §2（序列图）+ §3（接口契约）做交叉验证
  # 避免注入完整设计文档，防止评审模型上下文溢出
  - id: arch-compliance
    type: ai-review
    timeout: 60s               # 超时则跳过，不阻塞流程
    fallback: skip             # AI 调用失败时跳过，降级为人工评审（见下方 skip 责任归属）
    model: claude-sonnet       # 使用团队 AI Gateway
    # extract_section: 从 draft_design 中提取关键章节，而非传入全文
    extract_section:
      from: "{{draft_design}}"
      sections:
        - pattern: "## 6\\. 架构约束自查"   # 自查结论
          var: design_self_check
        - pattern: "## 2\\. 核心流程"       # 抽查序列图（交叉验证）
          var: design_flow
          max_lines: 50                     # 只取前50行，避免过长
        - pattern: "## 3\\. 接口契约"       # 抽查接口定义（交叉验证）
          var: design_api
          max_lines: 30
    prompt: |
      你是首席架构师，请审查以下设计文档 是否符合架构规范。
      重点：对 §6 自查结论做交叉验证，不要完全信任 AI 的自我审计。

      审查策略：
      1. 先看 §6 自查结论，记录声称"已通过"的规范项
      2. 抽查 §2 序列图和 §3 接口契约，验证自查结论是否真实
      3. 只报告明确违反规范的问题（如：§6 说"无跨层调用"但 §2 序列图显示 Controller→Repository）

      架构规范：
      {{constraints}}

      设计文档架构约束自查（§6）：
      {{design_self_check}}

      设计文档核心流程（§2，抽查用）：
      {{design_flow}}

      设计文档接口契约（§3，抽查用）：
      {{design_api}}

      输出格式（JSON）：
      {
        "pass": true/false,
        "violations": [
          {"rule": "规范名", "severity": "ERROR/WARN", "message": "描述", "fix": "修复建议", "cross_check": "§6 声称通过但 §2 显示违规"}
        ]
      }



  # Gate 4: 测试骨架生成（设计文档通过 Gate 1/2/3 审批后触发，开发编码前）
  - id: test-skeleton-generation
    type: script
    phase: post-approve          # 设计文档通过审批后自动触发，而非编码后
    run: >
      python scripts/generate_test_skeleton.py
        {{design_path}}
        --output src/test/java/{{package_path}}/sdd/
        --req-matrix docs/design/{{feature}}/test-skeleton-report.json
    on_fail: warn                # 生成失败不阻断开发，但写入日志

  # Gate 5: PRD 覆盖验证（PR 合并前，CI pre-merge 阶段触发）
  - id: prd-coverage-check
    type: script
    phase: pre-merge
    run: >
      python scripts/check_design_test_coverage.py
        --test-report {{test_report_path}}
        --req-matrix docs/design/{{feature}}/test-skeleton-report.json
        --fail-on-uncovered-p0
    on_fail: block               # P0 需求 TODO 未消除则硬阻断合并
```

#### V3 度量体系

建立 Eval 基准集，持续度量系统质量：

| 指标 | 目标值 | 测量方式 |
|------|--------|---------|
| 设计文档首次质量门禁通过率 | > 70% | gate 通过次数 / 总生成次数 |
| 平均迭代收敛次数 | < 2 次 | gate_loop_count 均值 |
| 类名引用准确率 | > 99% | class-existence gate 通过率 |
| 字段映射准确率 | > 99% | 人工抽查 |
| PRD 解析完整率 | > 95% | required_fields 全部非空比例 |
| 端到端生成时长 | < 90s | pipeline 总耗时 |

**V3 验收标准：**
- 跑通完整闭环：PRD 输入 → 自动生成 → 质量门禁 → 失败反馈 → 重新生成 → 通过 → 保存到本地
- 首次通过率 > 70%
- 平均迭代次数 < 2 次
- 建立 Eval 基准集（至少10个有参考答案的 PRD→设计文档对）

---

## 三、目录结构（完整落地版，V3 目标态）

```
repo-root/
│
├── AGENTS.md                          # AI 行为规范（V1 建立，持续更新）
├── ARCHITECTURE.md                    # 工程分层说明
│
├── docs/
│   ├── design/                        # 设计文档输出目录（Git 版本管理）
│   │   ├── _template/
│   │   │   ├── design-template.md        # 设计文档标准模板
│   │   │   └── prd-checklist.md       # PRD 最小质量要求
│   │   └── {feature-name}/
│   │       ├── design-v1.md
│   │       └── design-v1-gate-report.json    # 版本号与 design 文件对应，如 design-v2-gate-report.json
│   ├── arch-standards/                # 架构规范（MCP 数据源，V1 开始维护）
│   │   ├── layering-rules.md
│   │   ├── exception-handling.md
│   │   ├── transaction-rules.md
│   │   └── api-contract-rules.md
│   └── eval/                          # V3 新增：Eval 基准集
│       ├── README.md                  # 基准集说明和评分方式
│       ├── case-01-order-sync/
│       │   ├── input-prd.md           # 输入 PRD
│       │   └── expected-design.md        # 参考答案设计文档
│       └── case-02-payment/
│           ├── input-prd.md
│           └── expected-design.md
│
├── scripts/                           # V1 开始建立
│   ├── gen-context.sh                 # V1: 手动上下文生成
│   ├── check_design_structure.py         # V1: CI 结构校验
│   └── check_class_references.py      # V2: CI 类名校验
│
├── mcp-servers/                       # V2 开始建立
│   ├── project-explorer/
│   │   ├── server.py
│   │   ├── config.yaml                # scan_roots / module_prefix_map / polyquery 配置
│   │   └── README.md
│   └── arch-standard/
│       ├── server.py
│       └── README.md
│   # db-schema/ 目录已废弃，改用 polyquery MCP 直连数据库（见 .kiro/settings/mcp.json）
│   └── arch-standard/
│
├── skills/                            # V2 开始建立
│   ├── requirement-analyzer/
│   │   ├── SKILL.md                   # Agent 发现入口（触发条件/不触发条件）
│   │   ├── prompt.md
│   │   └── run.py
│   └── sdd-generation/
│       ├── SKILL.md                   # Agent 发现入口
│       ├── prompt.md
│       ├── prompt-v1.md               # 归档版本
│       └── run.py
│
└── .harness/                          # V3 开始建立
    ├── workflow.yaml
    ├── quality-gates/
    │   └── design-gate.yaml
    └── hooks/
        └── post-design-generate.sh
```

---

## 四、关键设计决策说明

### 4.1 为什么改用 polyquery MCP 替代自定义 db-schema Server

原方案（解析 Flyway changelog）存在以下问题：
1. Liquibase XML 格式不支持
2. 多行 ALTER TABLE 解析不完整，字段可能漏扫
3. 需要维护正则解析逻辑，随 SQL 方言变化需持续更新
4. 数据实时性差，changelog 可能落后于实际数据库状态

polyquery MCP 直连数据库，通过 `describe_table` 直接读取数据库元数据，字段注释、类型、索引全部实时准确，零维护成本。

**安全考量：** polyquery MCP 通过 `.kiro/settings/mcp.json` 配置连接串，建议使用只读账号，连接开发/测试库而非生产库。生产库的表结构通常与开发库一致，不需要直连生产。

### 4.2 为什么 feature_type 不用枚举

原始设计用了固定枚举（crud/sync/payment 等），但实际业务场景远不止这几种。
改为开放字符串，arch-standard MCP 用 `FEATURE_RULE_MAP` 做映射，未知类型兜底返回基础规范。

### 4.3 为什么 AI 语义审计 Gate 要设置 fallback: skip

AI 调用有不确定性（超时、限流、模型变更）。如果 AI Gate 失败就阻塞整个流程，会让团队对系统失去信任。
Gate 1（结构）和 Gate 2（类名）是确定性的，必须通过。Gate 3（语义）是增强检查，失败时降级跳过。

**skip 时的责任归属：** Gate 3 被跳过时，设计文档保存到本地后，必须由指定架构师（配置在 `.harness/config.yaml#arch_reviewer`）人工评审后才能视为通过，将机器审计降级为人工审计，不能直接跳过。跳过事件会写入当前版本的 gate-report 文件（如 `design-v2-gate-report.json`）的 `gate3_skipped: true` 字段，便于追溯。

> **通知局限性（显式说明）：** `gate3_skipped: true` 是被动写文件，不会自动推送通知。
> 开发者有责任在保存设计文档 后主动告知架构师（如在需求群发送文件路径）。
> 为降低遗漏风险，`run.py` 在检测到 Gate 3 skip 时会在终端打印醒目提示，
> 并在 `escalation.log` 中追加一条记录，方便迭代末盘点时发现遗漏。
> V4 可考虑接入 Webhook / 钉钉机器人实现自动推送。

```python
# run.py 中 Gate 3 skip 时的提示逻辑（在 run_gates 或 run_pipeline.py 中实现）
if gate3_skipped:
    import datetime
    msg = (f"\n{'='*60}\n"
           f"[WARN] Gate 3（AI 语义审计）已跳过\n"
           f"  设计文档路径：{output_path}\n"
           f"  指定评审人：{arch_reviewer}\n"
           f"  请在提交代码前通知 {arch_reviewer} 完成人工评审\n"
           f"{'='*60}\n")
    print(msg)
    with open(escalation_log, "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} | gate3_skipped | {output_path} | 待 {arch_reviewer} 人工评审\n")
```

```yaml
# .harness/config.yaml
arch_reviewer: "张三"   # Gate 3 skip 时由此人人工审计
```

### 4.4 Skill 中 Prompt 和脚本为什么要分离

原始设计把 Prompt 和执行脚本混在一个"Skill"概念里。实际上：
- Prompt 需要频繁调整（根据生成质量迭代）
- 脚本是确定性逻辑（不需要 AI，不应该频繁变动）

两者分离，修改 Prompt 不影响脚本，修改脚本不影响 Prompt。

### 4.5 Prompt 版本管理策略

`prompt.md` 被设计为频繁调整的文件，但 Prompt 变更会直接影响所有后续 设计文档的生成质量。

- Prompt 变更前，必须在 Eval 基准集（见 V3 检查清单）上跑回归，通过率不低于当前版本
- 重大变更（影响输出结构的）用新文件存档：`prompt-v1.md`、`prompt-v2.md`，`prompt.md` 始终指向当前生产版本
- 小幅调整（措辞优化、示例补充）直接修改 `prompt.md`，Git commit message 注明变更原因和测试结果

```
skills/sdd-generation/
├── prompt.md          # 当前生产版本（软链接或直接文件）
├── prompt-v1.md       # 归档版本，不删除
└── prompt-v2.md       # 归档版本，不删除
```

### 4.6 generate-sdd 首次运行时 gate-report.json 不存在

`run.py` 的 `--feedback` 参数指向上一轮的质量门禁报告，首次运行时该文件不存在。
`run.py` 内部必须做判断，文件不存在时跳过反馈注入，正常生成：

```python
# skills/sdd-generation/run.py 中的反馈加载逻辑
feedback_section = ""
if args.feedback:
    feedback_path = Path(args.feedback)
    if feedback_path.exists():                    # 首次运行时文件不存在，直接跳过
        feedback = json.loads(feedback_path.read_text())
        violations = feedback.get("violations", [])
        if violations:
            feedback_section = "\n\n## 上一版本的问题，本次必须修复：\n"
            for v in violations:
                feedback_section += f"- [{v['rule']}] {v['message']} → 修复: {v['fix']}\n"
```

### 4.7 方法/字段级真实性门禁（当前未实现，V4 规划）

当前 Gate 2 只校验类名是否存在，设计文档仍可在真实存在的 `OrderService` 上编造不存在的方法，或写出不存在的字段映射并通过门禁。这类幻觉比"类名不存在"更常见，也更难靠人工快速发现。

**当前缓解措施：** Gate 3 的 AI 语义审计会对 §2 序列图做交叉验证，能部分发现方法名编造问题，但不是确定性检查。

**V4 规划方向：**
- Gate 2 增加方法签名校验：从 `module-map.json` 的 `public_methods` 字段提取合法方法名，对 设计文档中 `` `service.methodName()` `` 格式的引用做白名单校验
- Gate 2 增加字段映射校验：从 `schema-context.json` 提取合法字段名，对 设计文档中字段引用做存在性校验
- 实现前提：`public_methods` 提取准确率需先达到 > 95%（当前正则对泛型、注解方法覆盖不完整）

### 4.8 能力标签驱动的可选章节（当前未实现，V4 规划）

当前 设计文档模板提供了 §7-§10 可选章节，但触发填写依赖开发者自觉，没有系统性约束。`requirement-analyzer` 的结构化产物也没有显式能力标签来驱动这些章节。

**当前状态：** "提供了可填写的模板"，未达到"PRD 提到 MQ/幂等/缓存 → 系统确定性要求补全"的治理强度。

**V4 规划方向：**

```python
# requirement-analyzer 输出增加 capability_tags 字段
{
  "feature_name": "order_sync",
  "feature_type": "sync",
  "capability_tags": ["mq", "idempotent", "cache"],  # 新增
  ...
}

# sdd-generation 根据 capability_tags 决定必填章节
REQUIRED_SECTIONS_BY_TAG = {
    "mq":         ["§9 消息队列"],
    "idempotent": ["§8 并发与幂等"],
    "cache":      ["§7 缓存策略"],
    "perf":       ["§10 性能非功能需求"],
}

# Gate 1 增加能力标签驱动的章节完整性校验
# 有 mq tag → §9 必须存在且非空
```

**实现前提：** `requirement-analyzer` 对 PRD 中 MQ/缓存/幂等关键词的识别准确率需先在 Eval 基准集上验证。

---

## 五、实施检查清单

### V1 检查清单
- [ ] 创建 `docs/design/_template/design-template.md`，经团队评审确认
- [ ] 创建 `docs/design/_template/prd-checklist.md`
- [ ] 填充 `docs/arch-standards/` 下的规范文档（至少4个）
- [ ] 编写并测试 `scripts/gen-context.sh`
- [ ] 编写 `AGENTS.md`
- [ ] 配置 git pre-commit hook，验证能拦截结构不完整的设计文档 提交
- [ ] 用5个真实 PRD 跑通流程，收集问题，迭代 Prompt 和模板

### V2 检查清单
- [ ] 部署 `project-explorer` MCP，验证在 AI 工具中可调用
- [ ] 部署 `arch-standard` MCP（无外部依赖，优先）
- [ ] 配置 polyquery MCP（`.kiro/settings/mcp.json`），验证 `mcp_polyquery_list_tables` 和 `mcp_polyquery_describe_table` 可正常调用
- [ ] 编写 `scripts/check_class_references.py`，集成到 pre-commit hook
- [ ] 用10个真实 PRD 验证，类名准确率 > 99%

### V3 检查清单
- [ ] 实现 `scripts/run_pipeline.py`（本地串联各阶段的入口脚本）
- [ ] 实现 `skills/requirement-analyzer/run.py`（**必须交付物**，见下方骨架）
- [ ] 实现 `skills/sdd-generation/run.py`（**必须交付物**，见下方骨架，含反馈重试逻辑）
- [ ] 配置 `.harness/quality-gates/design-gate.yaml`
- [ ] 配置 `.harness/config.yaml`（arch_reviewer 等）
- [ ] 建立 Eval 基准集（10个 PRD→设计文档对）
- [ ] 跑通完整闭环，验证首次通过率 > 70%
- [ ] 建立度量 Dashboard（本地 JSON 或简单脚本统计）

> **落地风险提示：** `run.py` 是最大的隐藏工作量。文档定义了 workflow 和 gate 配置，
> 但 AI 调用、重试逻辑、workspace 管理都需要在 `run.py` 里实现。
> 以下提供可直接运行的骨架，团队只需填入 AI Gateway 的调用方式即可。

#### V3 run.py 骨架实现

**requirement-analyzer/run.py**

```python
# skills/requirement-analyzer/run.py
"""
PRD 解析 Skill 执行脚本
用法: python skills/requirement-analyzer/run.py <prd_path> <output_json_path>
"""
import sys, json, re, argparse
from pathlib import Path

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("prd_path",    help="PRD 文件路径")
    p.add_argument("output_path", help="输出 structured-prd.json 路径")
    # 允许命令行手动补充缺失字段（对应 workflow 的 clarify 模式）
    p.add_argument("--feature-name",  default=None)
    p.add_argument("--feature-type",  default=None,
                   choices=["crud","sync","payment","notification","batch"])
    p.add_argument("--entities",      default=None, help="逗号分隔，如 Order,Payment")
    p.add_argument("--apis",          default=None, help="逗号分隔，如 'POST /api/v1/orders'")
    return p.parse_args()

def call_ai(prompt: str) -> str:
    """
    调用 AI Gateway 提取结构化字段。
    替换此函数以适配团队的 AI 接入方式（OpenAI / Claude / 内部 Gateway）。
    """
    # ---- 替换为实际 AI 调用 ----
    # 示例（OpenAI）：
    # from openai import OpenAI
    # client = OpenAI(api_key=os.environ["AI_GATEWAY_API_KEY"],
    #                 base_url=os.environ.get("AI_GATEWAY_BASE_URL"))
    # resp = client.chat.completions.create(
    #     model="gpt-4o",
    #     messages=[{"role": "user", "content": prompt}],
    #     response_format={"type": "json_object"},
    # )
    # return resp.choices[0].message.content
    raise NotImplementedError("请在 call_ai() 中填入团队的 AI Gateway 调用方式")

def extract_structured_prd(prd_text: str, overrides: dict) -> dict:
    prompt_template = Path("skills/requirement-analyzer/prompt.md").read_text(encoding="utf-8")
    prompt = prompt_template.replace("{{prd_content}}", prd_text)
    raw = call_ai(prompt)
    result = json.loads(raw)
    # 命令行覆盖优先
    for k, v in overrides.items():
        if v is not None:
            result[k] = v
    return result

REQUIRED_FIELDS = ["feature_name", "feature_type", "entities", "apis", "business_rules"]

def validate(data: dict) -> list[str]:
    missing = []
    for f in REQUIRED_FIELDS:
        if not data.get(f):
            missing.append(f)
    return missing

def main():
    args = parse_args()
    prd_text = Path(args.prd_path).read_text(encoding="utf-8")
    overrides = {
        "feature_name": args.feature_name,
        "feature_type": args.feature_type,
        "entities":     [e.strip() for e in args.entities.split(",")] if args.entities else None,
        "apis":         [a.strip() for a in args.apis.split(",")]     if args.apis     else None,
    }
    result = extract_structured_prd(prd_text, overrides)
    missing = validate(result)
    if missing:
        print(f"[ERROR] PRD 解析不完整，缺少字段：{missing}")
        print("请选择处理方式：")
        print("  1. 补充 PRD 内容后重新运行")
        print(f"  2. 命令行手动指定：--entities '...' --feature-type '...' --apis '...'")
        sys.exit(2)   # exit code 2 = clarify（区别于 exit 1 = 系统错误）
    Path(args.output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[OK] structured-prd.json 已写入 {args.output_path}")

if __name__ == "__main__":
    main()
```

**sdd-generation/run.py**

```python
# skills/sdd-generation/run.py
"""
设计文档生成 Skill 执行脚本（含反馈重试逻辑）
用法: python skills/sdd-generation/run.py --workspace <dir> --output <path> [--feedback <gate_report>]
"""
import sys, json, argparse
from pathlib import Path

MAX_RETRIES = 3

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", required=True, help="上下文文件目录")
    p.add_argument("--output",    required=True, help="输出 draft-design.md 路径")
    p.add_argument("--feedback",  default=None,  help="上一轮 gate-report.json 路径")
    p.add_argument("--resume",    action="store_true", help="人工修改后恢复执行")
    return p.parse_args()

def call_ai(prompt: str) -> str:
    """替换为团队 AI Gateway 调用，同 requirement-analyzer/run.py"""
    raise NotImplementedError("请在 call_ai() 中填入团队的 AI Gateway 调用方式")

def build_prompt(workspace: Path, feedback_section: str) -> str:
    from skills.sdd_generation.assemble_context import assemble
    prd = json.loads((workspace / "structured-prd.json").read_text())
    ctx = assemble(str(workspace), [e["name"] if isinstance(e, dict) else e
                                    for e in prd.get("entities", [])])

    # polyquery 调用失败时中止，不能带着假的 new-table 信号继续
    if "schema_error" in ctx:
        print(f"[ERROR] polyquery MCP 调用失败：{ctx['schema_error']}")
        print("请检查数据库连接后重试，或手动将表结构写入 schema-context.json 后重新运行")
        sys.exit(1)

    template = Path("skills/sdd-generation/prompt.md").read_text(encoding="utf-8")
    prompt = (template
              .replace("{{module_map}}",     json.dumps(ctx["module_map"],     ensure_ascii=False))
              .replace("{{schema_context}}", json.dumps(ctx["schema_context"], ensure_ascii=False))
              .replace("{{constraints}}",    json.dumps(ctx["constraints"],    ensure_ascii=False))
              .replace("{{scenario}}",       ctx["scenario"])
              .replace("{{prd}}",            json.dumps(prd, ensure_ascii=False)))
    return prompt + feedback_section

def load_feedback(feedback_path: str | None) -> str:
    if not feedback_path:
        return ""
    p = Path(feedback_path)
    if not p.exists():
        return ""   # 首次运行，无历史报告
    report = json.loads(p.read_text())
    violations = report.get("violations", [])
    if not violations:
        return ""
    lines = ["\n\n## 上一版本的问题，本次必须修复："]
    for v in violations:
        lines.append(f"- [{v['rule']}] {v['message']} → 修复: {v['fix']}")
    return "\n".join(lines)

def run_gates(draft_design: Path, workspace: Path) -> dict:
    """运行 Gate 1 + Gate 2，返回 gate-report 结构"""
    import subprocess
    report = {"pass": True, "violations": []}

    # Gate 1: 结构完整性
    r1 = subprocess.run(
        ["python", "scripts/check_design_structure.py", str(draft_design)],
        capture_output=True, text=True
    )
    if r1.returncode != 0:
        report["pass"] = False
        for line in r1.stdout.splitlines():
            if line.strip().startswith("-"):
                report["violations"].append({
                    "rule": "structure-completeness", "severity": "ERROR",
                    "message": line.strip("- "), "fix": "补充缺失章节"
                })

    # Gate 2: 类名存在性
    module_map = str(workspace / "module-map.json")
    r2 = subprocess.run(
        ["python", "scripts/check_class_references.py", str(draft_design), module_map],
        capture_output=True, text=True
    )
    if r2.returncode != 0:
        report["pass"] = False
        for line in r2.stdout.splitlines():
            if line.strip().startswith("-"):
                report["violations"].append({
                    "rule": "class-existence", "severity": "ERROR",
                    "message": line.strip("- "), "fix": "使用 [NEW] 标注新建类，或修正类名"
                })

    # Gate 3: AI 语义审计（超时/失败时跳过，不阻塞）
    # 此处留空，由 design-gate.yaml 配置驱动，run_pipeline.py 统一调用
    return report

def main():
    args = parse_args()
    workspace = Path(args.workspace)
    output    = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    feedback_section = load_feedback(args.feedback)

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[生成] 第 {attempt}/{MAX_RETRIES} 次尝试...")
        prompt = build_prompt(workspace, feedback_section)
        design_content = call_ai(prompt)
        output.write_text(design_content, encoding="utf-8")

        gate_report = run_gates(output, workspace)
        report_path = workspace / "gate-report.json"
        report_path.write_text(json.dumps(gate_report, ensure_ascii=False, indent=2))

        if gate_report["pass"]:
            print(f"[OK] 设计文档生成成功，已写入 {output}")
            return

        print(f"[FAIL] Gate 未通过，违规 {len(gate_report['violations'])} 项，准备重试...")
        # 把本轮报告作为下一轮的反馈
        feedback_section = load_feedback(str(report_path))

    # 超出重试上限
    print(f"[ESCALATE] 超出最大重试次数（{MAX_RETRIES}），需要人工介入")
    escalation_log = workspace.parent / "escalation.log"
    with escalation_log.open("a") as f:
        import datetime
        f.write(f"{datetime.datetime.now().isoformat()} | {args.output} | 超出重试上限\n")
    print(f"[INFO] 已写入 {escalation_log}，请通知架构师人工评审")
    sys.exit(3)   # exit code 3 = escalation

if __name__ == "__main__":
    main()
```

---

## 六、MCP 服务部署检查

```bash
#!/bin/bash
# scripts/health-check.sh
echo "=== MCP 服务健康检查 ==="

echo "1. project-explorer MCP..."
python -c "from mcp.server import Server; print('[OK] mcp 依赖已安装')" 2>/dev/null \
  || echo "[FAIL] 请安装: pip install mcp"

echo "2. polyquery MCP（替代原 db-schema）..."
# polyquery MCP 通过 MCP 协议接入，配置文件路径因 IDE 不同而异
MCP_CONFIGS=(
  ".kiro/settings/mcp.json"
  ".cursor/mcp.json"
  "$HOME/.cursor/mcp.json"
  "$HOME/.claude/claude_desktop_config.json"
  ".vscode/mcp.json"
  "$HOME/.codeium/windsurf/mcp_config.json"
  "$HOME/.gemini/settings.json"
  "$HOME/.codex/config.json"
)
FOUND_CONFIG=""
for cfg in "${MCP_CONFIGS[@]}"; do
  if [ -f "$cfg" ] && grep -q "polyquery" "$cfg" 2>/dev/null; then
    FOUND_CONFIG="$cfg"; break
  fi
done
[ -n "$FOUND_CONFIG" ] \
  && echo "[OK] polyquery 已在 $FOUND_CONFIG 中配置" \
  || echo "[WARN] 未找到 polyquery MCP 配置，请参考文档在对应 IDE 的 mcp.json 中配置"
echo "      支持的配置路径：Kiro(.kiro/settings/mcp.json) | Cursor(.cursor/mcp.json)"
echo "      Claude Code(~/.claude/claude_desktop_config.json) | Gemini CLI(~/.gemini/settings.json)"
echo "      Codex CLI(~/.codex/config.json) | Windsurf(~/.codeium/windsurf/mcp_config.json)"

echo "3. arch-standard MCP..."
[ -d "docs/arch-standards" ] && ls docs/arch-standards/*.md > /dev/null 2>&1 \
  && echo "[OK]" \
  || echo "[FAIL] docs/arch-standards/ 无规范文档，请先创建"

echo "4. AI Gateway..."
[ -n "$AI_GATEWAY_API_KEY" ] && echo "[OK]" || echo "[FAIL] AI_GATEWAY_API_KEY 未配置"

echo "=== 检查完成 ==="
```

---

## 七、本地优先模式下的协作约定

设计文档只保留在本地，没有 CI 强制拦截，流程容易被悄悄绕过。以下约定用来防止这种情况：

### 7.1 什么情况必须产出设计文档

团队需要明确约定触发条件，否则"本地优先"会退化成"没有流程"：

```
必须产出设计文档 的场景：
- 新增接口（无论几个）
- 涉及数据库表结构变更（新建表 / 加字段 / 改索引）
- 跨服务调用（调用其他微服务或被其他服务调用）
- 业务规则变更（不只是代码重构）

可以不产出设计文档 的场景：
- 纯 bugfix（不涉及逻辑变更）
- 配置项调整
- 代码重构（无行为变更）
- 文案/日志修改
```

建议把这个约定写进团队 Wiki 或 `CONTRIBUTING.md`，而不只是放在这份文档里。

### 7.2 设计文档评审约定

本地优先模式下，设计文档不走 PR 流程，评审需要主动触发：

> **通知局限性（显式说明）：** `escalation.log` 和 `gate3_skipped` 均为被动写文件，
> 不会自动推送通知。开发者有责任主动通知架构师，系统不会自动推送。
> `run.py` 在 Gate 3 skip 和超出重试上限时会在终端打印醒目提示，
> 并追加到 `escalation.log`，方便迭代末盘点时发现遗漏。
> V4 可考虑接入 Webhook / 钉钉机器人。

```
评审流程（建议）：
1. 开发者生成设计文档 后，在需求群/技术群发送文件路径或截图（人工触发，非自动）
2. 指定评审人（架构师或 Tech Lead）在 X 个工作日内完成评审
3. 评审意见直接在 设计文档中批注（Markdown 注释或单独的 review.md）
4. 评审通过后，开发者在 设计文档头部将状态改为 Approved，再开始编码

状态流转：
  Draft → Review（发出评审请求）→ Approved（评审通过）→ Implemented（功能上线）
```

### 7.3 防绕过机制

没有 CI 强制，依赖以下轻量机制保证流程不被跳过：

```
机制1：pre-commit hook（V1 起配置）
  - 对已有 设计文档做结构完整性校验（已实现，见 §V1 pre-commit hook 配置）
  - 注意：hook 不会自动判断"本次 Java 变更是否需要产出设计文档"——
    这个判断依赖业务上下文，无法用脚本可靠实现
  - 实际做法：开发者提交时自行对照 §7.1 的场景清单判断，
    hook 只做"有设计文档则校验，无设计文档则不拦截"

机制2：Code Review checklist
  - PR 模板中加一条：[ ] 本次变更是否需要设计文档？如需要，设计文档路径：___
  - Reviewer 有责任检查这一项

机制3：定期 设计文档盘点（建议每个迭代末）
  - 对比本迭代的功能列表和 docs/design/ 下的 设计文档
  - 缺失的设计文档在下个迭代补齐，记录在 docs/exec-plans/tech-debt.md
```

### 7.4 设计文档命名和版本约定

```
docs/design/
└── {feature-name}/          # 用 kebab-case，如 order-sync、payment-refund
    ├── design-v1.md             # 初版
    ├── design-v2.md             # 迭代改造（保留旧版，不覆盖）
    ├── design-v1-gate-report.json
    └── design-v2-gate-report.json   # 与对应版本 design 文件同步递增
```

- `feature-name` 与 PRD 的 `feature_name` 字段保持一致（snake_case 转 kebab-case）
- 迭代改造时新建 `design-v2.md`，不覆盖 `design-v1.md`，保留历史可追溯
- `design-v{n}.md` 头部的状态字段是唯一的状态来源，不另建状态表

---

## 八、V3+ 展望（当前版本不实现，作为演进方向）

### 8.1 SDD → Code：设计驱动代码生成

当前文档覆盖 PRD → SDD 这半段。设计文档的结构已经被设计成代码生成的直接输入，以下是各章节与代码产物的对应关系：

```
设计文档章节                    可驱动生成的代码产物
─────────────────────────────────────────────────────────────
§3 接口契约（OpenAPI）   →  Controller 接口骨架 + 参数校验注解
§1 领域模型（实体表）    →  Entity（@Table/@Column）+ Repository 接口
§2 核心流程（序列图）    →  Service 方法骨架（方法签名 + 注释）
§4 数据库变更（DDL）     →  Flyway migration 文件（直接可用）
§5 异常处理（错误码表）  →  BizException 枚举 + @ControllerAdvice 映射
```

实现路径（V4 规划）：
- 新增 `code-generation` Skill，消费 `final-design.md` 作为输入
- 使用 OpenAPI Generator 处理接口契约部分（确定性，不依赖 AI）
- 使用 AI 处理 Service 骨架生成（非确定性，需要 Gate 校验）
- 生成产物作为 PR 的一部分，和设计文档一起进入 code review

**当前限制：** 序列图（Mermaid）到 Service 骨架的转换目前没有成熟工具，需要自定义解析器或依赖 AI，准确率不稳定，不建议在 V3 之前引入。

### 8.2 设计文档依赖关系管理

复杂功能的设计文档往往引用其他设计文档的接口（Feature A 依赖 Feature B 的 API）。当前每个设计文档是孤岛，Feature B 更新后 Feature A 无感知。

演进方向：
- 在设计文档模板中增加 `## 0. 依赖声明` 章节，显式列出依赖的其他设计文档
- `project-explorer` MCP 增加 `get_sdd_interface` 工具，读取已有 设计文档的接口契约
- CI 增加依赖一致性检查：当 Feature B 的 设计文档变更时，扫描所有声明依赖它的设计文档，创建 Review Issue

**引入时机：** 当团队积累超过20个设计文档 且出现跨 设计文档引用不一致的问题时再引入，过早引入会增加维护负担。

---

## 九、SDD → Code 闭环：Gate 4 与 Gate 5

### 9.1 两类不一致来源

"编码与 PRD 不一致"实际有两类来源，处理方式不同：

```
类型一：结构性不一致
  → 接口签名、字段类型、HTTP 状态码与 设计文档不符
  → 可确定性验证，不需要 AI

类型二：业务逻辑不一致
  → 流程分支、异常处理、幂等逻辑与 PRD 描述不符
  → 需要用例驱动的测试执行来验证
```

现有系统（V1–V3）解决了 PRD → SDD 的保真问题。本章补全 SDD → Code 的闭环验证。

**核心原则：** 不是"编码完了再生成测试"，而是在 设计文档审批时就确定验收标准，编码阶段必须满足这些标准。这是 设计文档驱动开发的本质。

---

### 9.2 扩展后的完整流水线

原有 5 阶段流水线扩展为 7 阶段：

```
[现有] PRD解析 → 上下文注入 → SDD生成 → Gate1/2/3 → 设计文档归档
                                                         ↓
[新增]                                             Gate4: 测试骨架生成
                                                         ↓
                                                    开发编码（人工）
                                                    ↕（实现业务逻辑 + 填充测试断言）
                                                   Gate5: PRD覆盖验证
                                                         ↓
                                                    允许 PR 合并
```

**整体数据流：**

```
PRD.md
  │
  ▼ Stage 1
structured-prd.json ──────────────────────────────────────────┐
  │                                                            │
  ▼ Stage 2/3                                                  │
design-v1.md                                                      │
  │                                                            │
  ├─ Gate1 (结构完整性)                                         │
  ├─ Gate2 (类名存在性)                                         │
  └─ Gate3 (架构语义)                                           │
       │ 通过                                                   │
       ▼                                                        │
  Gate4: 生成测试骨架  ←── §3 接口契约 + §5 异常处理 + §12 验收矩阵 ◄─┘
       │
       ▼ 开发者实现业务代码 + 填充测试断言（TODO → 真实断言）
       │
       ▼ PR 提交
  Gate5-层一: check TODO 消除（确定性）
       │ P0 全消除
       ▼
  Gate5-层二: 运行测试 + 对齐 REQ-ID
       │ P0 全通过
       ▼
  允许 PR 合并
```

---

### 9.3 Gate 4：测试骨架生成

**触发时机：** 设计文档通过 Gate 1/2/3，状态变为 `Approved` 时自动触发（开发编码前）。

**输入来源：**
- §3 接口契约（OpenAPI YAML）→ 生成接口测试
- §5 异常处理表 → 生成负向测试用例
- §12 验收标准矩阵 → 生成业务场景测试注释框架

**脚本：** `scripts/generate_test_skeleton.py`

```python
# 从 §3 OpenAPI 片段提取接口信息
def extract_api_contracts(design_content: str) -> list[ApiContract]:
    # 解析 设计文档中的 openapi: 代码块
    # 返回：路径、方法、请求体 schema、响应 schema、HTTP 状态码

# 从 §5 异常处理表提取负向场景
def extract_exception_cases(design_content: str) -> list[ExceptionCase]:
    # 解析 §5 表格：异常类型 / 触发条件 / BizCode / HTTP状态

# 生成 Spring Boot 测试骨架（JUnit 5 + MockMvc）
def generate_test_class(
    api_contracts: list[ApiContract],
    exception_cases: list[ExceptionCase],
    req_matrix: list[RequirementRow]
) -> str:
    # 每个 REQ-ID 对应一个 @Test 方法
    # 每个异常场景对应一个 @Test 方法
    # 方法体为 // TODO: 实现断言，骨架由脚本生成
```

**生成的测试骨架示例：**

```java
/**
 * 自动生成自设计文档 §3 和 §12
 * 生成时间: 2026-04-16
 * 对应设计文档: docs/design/order-create/design-v1.md
 *
 * !! 警告: 此文件包含 TODO 标记，必须由开发者补全断言逻辑
 * !! Gate5 会在 CI 中检查 TODO 是否已消除
 */
@SpringBootTest
@AutoConfigureMockMvc
class OrderCreateSddVerificationTest {

    // REQ-001: 下单后库存实时扣减
    @Test
    @DisplayName("[REQ-001] 下单成功后库存数量减少")
    void req001_inventory_should_decrease_after_order() {
        // TODO: 调用下单接口，验证 inventory.quantity 减少了 orderQty
        // SDD §2 流程节点: OrderService.createOrder -> InventoryService.deduct
        // 验收条件: inventory.quantity(after) == inventory.quantity(before) - orderQty
    }

    // REQ-002: 支付超时取消订单
    @Test
    @DisplayName("[REQ-002] 支付超时后订单状态为 CANCELLED")
    void req002_order_should_be_cancelled_on_payment_timeout() {
        // TODO: 模拟 30 分钟超时，验证订单状态变更
        // SDD §2 异常分支: timeout -> OrderStatus.CANCELLED
    }

    // §5 负向测试: 库存不足
    @Test
    @DisplayName("[NEG-001] 库存不足时返回 400 + BizCode 1001")
    void neg001_insufficient_inventory_should_return_400() {
        // TODO: 构造 quantity=0 的库存状态，下单，验证 HTTP 400 和 BizCode 1001
    }
}
```

**Gate 4 输出文件：**
- `src/test/java/.../sdd/{feature}SddVerificationTest.java`（测试骨架文件）
- `docs/design/{feature}/test-skeleton-report.json`（REQ-ID 到测试方法的映射表）

---

### 9.4 Gate 5：PRD 覆盖验证

**触发时机：** CI pipeline 的 pre-merge 阶段（PR 提交时触发）。

验证分两层，依次执行：

#### 层一：TODO 消除检查（确定性，毫秒级）

```python
# scripts/check_design_test_coverage.py

def check_todo_completion(test_file_path: str, req_matrix_path: str) -> CheckResult:
    """
    检查 Gate4 生成的测试骨架中的 TODO 是否已被开发者实现。
    未实现 = TODO 注释仍存在 = 对应 REQ-ID 未被覆盖。
    """
    with open(test_file_path) as f:
        content = f.read()

    todo_pattern = re.compile(r"// TODO:.*\n.*\[REQ-(\d+)\]", re.MULTILINE)
    uncovered_reqs = todo_pattern.findall(content)

    # 区分 P0 和 P1
    result = {
        "uncovered_p0": [],
        "uncovered_p1": [],
    }
    for req_id in uncovered_reqs:
        row = req_matrix[f"REQ-{req_id}"]
        if row["priority"] == "P0":
            result["uncovered_p0"].append(req_id)
        else:
            result["uncovered_p1"].append(req_id)

    return result
```

**阻断规则：**
- P0 需求有 TODO 未消除 → Gate 5 **硬阻断**（`exit 1`）
- P1 需求有 TODO 未消除 → 警告，不阻断（写入 `gate5-report.json`）

#### 层二：测试执行结果与 REQ-ID 对齐（CI 阶段）

```yaml
# .github/workflows/sdd-verification.yml（或 Jenkinsfile 片段）

- name: Run SDD Verification Tests
  run: |
    mvn test -pl order-service \
      -Dtest="*SddVerificationTest" \
      -Dsurefire.reportFormat=json

- name: Check PRD Coverage
  run: |
    python scripts/check_design_test_coverage.py \
      --test-report target/surefire-reports/sdd-verification.json \
      --req-matrix docs/design/order-create/test-skeleton-report.json \
      --fail-on-uncovered-p0
```

#### Gate 5 输出报告

```json
// docs/design/order-create/gate5-report.json
{
  "timestamp": "2026-04-16T10:30:00",
  "design_version": "design-v1.md",
  "coverage": {
    "total_requirements": 4,
    "covered_passing": 3,
    "covered_failing": 0,
    "uncovered": 1
  },
  "uncovered_requirements": [
    {
      "req_id": "REQ-003",
      "priority": "P1",
      "description": "重复提交订单幂等保护",
      "status": "todo_not_implemented",
      "blocker": false
    }
  ],
  "result": "WARN"
}
```

> `result` 取值：`PASS`（P0 全覆盖且全通过）、`WARN`（P1 有遗漏但 P0 全覆盖）、`FAIL`（P0 未覆盖，阻断合并）

---

### 9.5 与 run.py 的集成

在 `skills/sdd-generation/run.py` 现有流程末尾追加 Gate 4 调用：

```python
# skills/sdd-generation/run.py

def run_full_pipeline(prd_path: str, feature_name: str):
    # --- 现有 V3 逻辑（不变）---
    structured_prd = run_stage1_parse(prd_path)
    context = run_stage2_inject(structured_prd)
    draft_design = run_stage3_generate(structured_prd, context)
    gate_result = run_gates_1_2_3(draft_design)
    approved_sdd = save_approved_sdd(draft_design, feature_name)

    # --- 新增：Gate 4（设计文档审批后立即执行）---
    test_skeleton = generate_test_skeleton(
        design_path=approved_sdd,
        output_dir=f"src/test/java/.../sdd/{feature_name}/",
        req_matrix_path=f"docs/design/{feature_name}/test-skeleton-report.json"
    )
    print(f"[Gate4] 已生成测试骨架: {len(test_skeleton.methods)} 个测试方法")
    print(f"[Gate4] P0 需求: {test_skeleton.p0_count} 个必须在合并前实现")
    print(f"[Gate4] 骨架位置: {test_skeleton.output_path}")
    print(f"[Gate4] 映射表: docs/design/{feature_name}/test-skeleton-report.json")

    # Gate 5 由 CI 在 PR 合并前触发，不在本地 run.py 中执行
```

---

### 9.6 新增文件清单

| 文件路径 | 说明 | 引入阶段 |
|---------|------|---------|
| `scripts/generate_test_skeleton.py` | Gate 4：从设计文档 §3/§5/§12 生成 JUnit 5 测试骨架 | Gate 4 |
| `scripts/check_design_test_coverage.py` | Gate 5 层一：检查 TODO 是否消除 + P级阻断判断 | Gate 5 |
| `.github/workflows/sdd-verification.yml` | Gate 5 层二：CI 运行测试并对齐 REQ-ID | Gate 5 |
| `docs/design/{feature}/test-skeleton-report.json` | REQ-ID 到测试方法的映射表（Gate 4 生成，Gate 5 读取） | Gate 4 |
| `docs/design/{feature}/gate5-report.json` | PRD 覆盖验证报告（Gate 5 输出） | Gate 5 |
| `src/test/java/.../sdd/{feature}SddVerificationTest.java` | 测试骨架文件（Gate 4 生成，开发者填充） | Gate 4 |

---

### 9.7 实施检查清单

**Gate 4 上线前（设计文档审批后自动触发）：**

- [ ] 实现 `scripts/generate_test_skeleton.py`（解析 §3 OpenAPI + §5 异常表 + §12 矩阵）
- [ ] 在 `design-gate.yaml` 中配置 `test-skeleton-generation` gate（`phase: post-approve`）
- [ ] 在 `run.py` 末尾接入 `generate_test_skeleton()` 调用
- [ ] 验证：设计文档审批后自动在正确路径生成骨架文件，P0/P1 标记准确

**Gate 5 上线前（PR 合并前 CI 触发）：**

- [ ] 实现 `scripts/check_design_test_coverage.py`（TODO 扫描 + REQ-ID 映射 + P级判断）
- [ ] 配置 `.github/workflows/sdd-verification.yml`（运行 `*SddVerificationTest` + 覆盖检查）
- [ ] 在 `design-gate.yaml` 中配置 `prd-coverage-check` gate（`phase: pre-merge`，`on_fail: block`）
- [ ] 验证：P0 TODO 未消除时 CI 返回 `exit 1`；P1 未消除时仅写入 `gate5-report.json`
