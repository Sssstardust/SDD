# SDD 项目深度剖析与改进建议

> 仓库：[Sssstardust/SDD](https://github.com/Sssstardust/SDD)
> 评估时间：2026-05-17
> 评估范围：仓库结构、架构分层、流程编排、Gate 体系、MCP/Skill 接入、跨平台、可演进性

---

## 0. TL;DR（执行摘要）

SDD 是一套面向 **Java/Spring 棕地项目** 的 **规格驱动开发（Spec-Driven Development）** 工具链。它把 "需求 → 设计 → 任务 → 测试 → 实现 → 发布" 6 个阶段串成了一条由 **5 道 Gate + 1 道发布门禁** 守护的流水线，依靠 **双态 Baseline（设计态 / 实现态）** + **capability_tags** + **MCP 工具** 来抑制 AI 幻觉、强制可追溯。

整体上方法论清晰、产物体系齐整、治理思路领先；但工程层面尚处于 **MVP 升级到生产级的过渡期**，在以下几方面存在系统性短板：

1. **scripts/ 单仓巨石**：`run_pipeline.py` 1739 行 / 79 函数、多个 1000+ 行检查器，CLI 与领域逻辑耦合；
2. **事实源可信度不足**：`project-explorer` 仍是 lexical-v2（正则/词法）扫描，Lombok/泛型/MyBatis/反射均为低可信；polyquery 回退本地易产生 "假 PASS"；
3. **跨技术栈不通用**：领域、模板、检查器全部围绕 Java/Spring 设计，前端/Go/Python/多语言微服务尚无一等支持；
4. **跨平台一致性弱**：README 与 CI 全部偏 Windows + PowerShell，doctor 同时存在 `.ps1/.sh/.py` 三份；
5. **流程成本与轻量化分级不彻底**：`sdd_level` 仍主要靠人工填写，未做事实驱动推导；
6. **测试与依赖治理不严**：`tests/` 仅含 `__pycache__`、`pyproject.toml` 依赖为空、`uv.lock` 几乎为空；
7. **AutoPilot Skill 行权过激**：sdd-assistant 鼓励 "无须请示，连续递归"，但前置事实源可信度并未达到匹配等级；
8. **流程命名/目录冗余**：`.spec/` 与 `specs/`、`document/` 与 `docs/` 同时存在，命令别名（bootstrap-attached-project / greenfield-init / scaffold）数量膨胀。

下文按 **架构** 与 **功能设计** 两个维度展开问题清单与改进建议，并给出落地优先级。

---

## 1. 项目定位与现状速览

### 1.1 仓库结构

```
SDD/
├── .spec/                  # 流程产物（schemas / templates / baselines / project-artifacts）
├── .github/workflows/      # CI 示例（仅 Windows runner）
├── config/                 # polyquery 等运行时配置
├── docs/                   # 团队接入 / 改进 backlog / 开放清单
├── document/               # 设计蓝图、v3.4 工作流、模板
├── examples/fixtures/      # 4 类示例：lightweight / standard / multi-component / payment-full
├── mcp-servers/            # 4 个 MCP：project-explorer / polyquery / sdd-pipeline / arch-standard
├── scripts/                # 70+ Python 脚本，含 application/domain/infrastructure/ports/gates/entrypoints
├── skills/                 # sdd-assistant / sdd-generation / requirement-analyzer
├── specs/                  # 业务 feature 目录（pilot-payment-review、task-board）
├── templates/              # codex / gemini / opencode 三类 agent 接入模板
├── tests/                  # （仅 __pycache__）
├── pyproject.toml          # dependencies = []（未声明依赖）
└── uv.lock                 # 123 bytes（实际为空）
```

### 1.2 流程主链

```
Phase 0  Baseline 治理       refresh-baseline / refresh-module-map / refresh-schema-context
Phase 1  Feature Brief       generate-feature-brief → verify
Phase 2  Design + Multi-Gate gate1（结构）→ gate2（真实性）→ gate3（架构语义）
                              risk_tier=high 走 init-approval / check-approval
Phase 3  Task Slice          generate-task-slices（垂直 + 横切）
Phase 4  Test Skeleton       gate4（基于验收矩阵生成测试骨架）
Phase 5  Implementation      gate5（覆盖验证）→ sync-baseline
Phase 6  Release Gate        release-gate（回滚 / 监控 / 灰度）
```

### 1.3 我看到的"亮点"

- **双态 Baseline**：把 "已审批设计意图" 与 "实际落地代码" 分两份索引，避免新需求基于旧实现做错误假设；
- **capability_tags + risk_tier 驱动产物与门禁**：替代单一 feature_type，能更精确地决定哪些设计章节必填；
- **`[AMBIGUOUS]` 内联标记**：把模糊点显式化，强迫澄清；
- **Gate 1 通过即冻结 design-pack snapshot**：版本化证据链思路正确；
- **附着模式（attached-project）**：工具仓库与业务源码解耦，可一仓多项目；
- **MCP + Skill + Pipeline 三层切分**：Agent 接入点设计合理。

---

## 2. 架构层面的问题

### 2.1 P0 - `scripts/` 是分层未到位的"半 DDD 巨石"

**现象：**

- 仓库里同时存在 `scripts/application/`、`scripts/domain/`、`scripts/infrastructure/`、`scripts/ports/`、`scripts/entrypoints/`、`scripts/gates/`，看起来已经做了 DDD/六边形分层；
- 但 `scripts/` 根目录依然散落了 70+ 个 `.py` 文件（gate1.py、gate_adapters.py、check_design_truthfulness.py 等），与子层级文件互相 import：
  - `from infrastructure.baseline_extractors import ...`
  - `from gate_adapters import ...`（根目录）
  - `from application.feature_brief import ...`
  - `from bootstrap_utils import ...`（根目录）
- **`run_pipeline.py`：1739 行，79 个函数**，集中处理参数解析、子命令分派、子进程执行、产物写出、错误归因；
- **`check_design_test_coverage.py`：1538 行**、**`check_design_truthfulness.py`：1300 行**、**`gate_adapters.py`：1217 行** —— 单文件超长，违反 SRP；
- 入口同时存在 `scripts/run_pipeline.py` 与 `scripts/entrypoints/run_pipeline.py`，开发者难判定权威入口。

**风险：**

- Onboarding 困难：新成员要追懂 "一个 gate 实际从哪进、走到哪、产物在哪写" 难度极高；
- 修改放大：一处 import 改名要扫全仓；
- 单元测试粒度无法细到领域层（被 IO/子进程耦合拖垮）。

**改进建议：**

1. **彻底执行六边形分层**：根目录只保留 `run_pipeline` shim，把所有业务模块下沉到 `application/` / `domain/` / `infrastructure/`，由 `entrypoints/` 唯一对外；
2. **`run_pipeline.py` 改为 Command Registry**：每个子命令做成 `commands/<name>.py`，自动注册（用 entry point 或简单 dict），1739 行裁到 ≤300 行；
3. **拆分 1000+ 行检查器**：按 "校验项类型" 切——结构校验 / 命名校验 / 数据库映射校验 / 接口契约校验 各自单独文件，统一通过 `CheckResult` DTO 汇总；
4. **包化与 `pyproject.toml` 纳管**：把 `scripts/` 改造成 `sdd_pipeline` 包，发布到内部 PyPI 或用 `pip install -e .`，CLI 通过 `[project.scripts]` 暴露 `sdd-pipeline` 命令；
5. **一处入口**：删除重复入口，docs 里也只留一个权威路径。

---

### 2.2 P0 - 事实源（Baseline）可信度被高估

**现象：**

- **`project-explorer` 仍是 `scanner=java-lexical-v2`**：基于词法/正则识别 Java 类、字段、方法。开发者自己在 `docs/sdd-architecture-open-items.md` P0-2 也承认：Lombok 生成方法、复杂泛型、继承方法、MyBatis XML 与接口绑定 **无法可靠识别**；
- **`polyquery` 支持 `--polyquery-fallback local`**：当连不上数据库时，落到本地快照仍可继续。Gate 2 虽然会 WARN，但严格模式默认未全链路打开 fail-fast；
- **Baseline 的产物本身是脚本生成的**：`sdd-index-real.json` 由 `module-map.json` 推导，`module-map.json` 由低可信扫描器生成 —— 等于 **AI 的唯一事实源仍依赖一个低可信度组件**，方法论"消除幻觉"目标被打折。

**风险：**

- Gate 2 真实性校验对 Lombok/MyBatis/继承场景出现"看似 PASS、实际不一致"；
- 当 Java 项目大量使用 `@Mapper` 接口 + XML SQL，方法签名和 SQL 字段映射在 Baseline 里几乎缺失；
- 对前端、Go、Python 等非 Java 栈，project-explorer 直接不可用。

**改进建议：**

1. **scanner 升级为 AST/Symbol 级**：
   - 短期接入 [JavaParser](https://javaparser.org/) 或 `com.github.javaparser` Symbol Solver；
   - 中期可选 `javac` Symbol API / Eclipse JDT，覆盖泛型擦除前类型与继承图；
2. **多语言扫描器抽象**：定义 `BaselineScanner` 接口（语言无关），实现 `JavaParserScanner` / `TsCompilerScanner` / `GoAstScanner` / `PythonAstScanner`，按 `module-map.json` 的 `language` 分派；
3. **在 `module-map.json` 上加显式 `confidence` 与 `unsupported_features`，并绑定 Gate 决策**：
   - `confidence=low` 的类不允许直接 PASS Gate 2/5，必须人工标注豁免；
4. **polyquery 必须强制双源比对**：DDL 文件 + 在线 metadata 双源（local-fallback 仅在非 strict + 非 high risk 下允许，严格模式 / 支付类自动 fail-fast）；
5. **新增"事实源可信等级矩阵"文档**：把 db_live / code_ast / ddl_file / design_doc / human_assertion 5 类来源标出可信度，并在每个 Gate 报告里注明本次决策依赖了哪一级。

---

### 2.3 P1 - 跨平台一致性差（Windows/PowerShell 偏置）

**现象：**

- README 全部命令都用 `powershell` 反引号续行；
- `.github/workflows/sdd-pipeline.example.yml` 显式 `runs-on: windows-latest` 并使用 `npm.cmd`；
- 仓库同时存在 `scripts/doctor.ps1`、`scripts/doctor.sh`、`scripts/doctor.py`，三份内容很可能漂移；
- 路径示例固定为 `D:\project\SDD\...`。

**风险：**

- macOS / Linux 开发者 Onboarding 体验差，CI 不能直接复用；
- 三份 doctor 维护代价 = 3×。

**改进建议：**

1. **doctor 唯一化**：`doctor.py` 作为唯一实现，`.ps1/.sh` 退化成 1 行 wrapper（或删除）；
2. **README 命令统一用 POSIX shell 写法**，Windows 用户可在 PowerShell 直接运行（`python scripts/run_pipeline.py ...` 是跨平台的）；
3. **CI 同时跑 ubuntu-latest + windows-latest 矩阵**，并把 macOS-latest 列为可选。

---

### 2.4 P1 - 依赖与构建治理空白

**现象：**

- `pyproject.toml` 中 `dependencies = []`，但代码里大量引用第三方库（pyyaml、jsonschema、pytest 等隐式存在）；
- `uv.lock` 仅 123 bytes，等同未生成；
- `tests/` 目录下只有 `__pycache__/*.pyc`，没有源 `.py` —— 可能：a) .gitignore 漏配把 `tests/*.py` 误忽略；b) 仓库主测试在 `examples/fixtures/` 与 `mcp-servers/*/tests` 分散；c) 历史迁移遗漏；
- 没有 `requirements.txt`、`Makefile`、`Justfile` 等统一入口。

**风险：**

- 新机器 `pip install -e .` 装不全；
- `.pyc` 进 git 是反模式，且其源缺失说明测试体系断裂；
- 升级 Python 版本无锁定不可重现。

**改进建议：**

1. **补全 `pyproject.toml.dependencies`**：声明所有运行时与开发依赖（含可选 extras: `[dev]`、`[mcp]`、`[polyquery]`）；
2. **生成完整 `uv.lock` / `requirements-lock.txt`**；
3. **修复 tests 目录**：检查 `.gitignore`，把丢失的 `tests/*.py` 提回；并建立 "scripts/ 改动必跑 pytest" 的 pre-commit hook；
4. **加 `.gitignore` 规则忽略 `__pycache__/`，并清掉仓库中已提交的 `.pyc`**；
5. **加 Makefile / Justfile**，统一 `make doctor / test / gate / release-check`。

---

### 2.5 P1 - 命令与目录命名冗余、心智模型割裂

**现象：**

| 类型 | 重复 / 混淆点 |
| --- | --- |
| 目录 | `.spec/` vs `specs/`、`document/` vs `docs/`、`templates/` vs `.spec/templates/` |
| 命令别名 | `bootstrap-attached-project` ≡ `onboard-project`、`greenfield-init` ≡ `bootstrap` ≡ `scaffold`、`pre-release-check` ≡ `go-live-check` ≡ `release-gate` |
| 设计/项目 schema 分散 | `.spec/schemas/` vs `mcp-servers/*/src/.../schema.ts` |

**风险：**

- README 下 ~50 个命令，对新人是认知灾难；
- 同一概念多个名字，文档检索体验差；
- Bug fix 容易只改一份 schema，另一份漂移。

**改进建议：**

1. **命令收敛**：保留 `onboard / refresh-baseline / design-cycle / impl-cycle / release` 作为一级动词，二级用子命令而非别名；
2. **目录合并**：
   - `.spec/` 仅保留 **运行时产物**（baselines / project-artifacts / ops / attached-project.json）；
   - **schemas / templates** 合并到顶层 `templates/` 或 `schemas/`；
   - `document/` 与 `docs/` 合并为 `docs/`，`document/template/` 移到 `templates/spec/`；
3. **schema 单源管理**：在仓库根定义一次（如 `schemas/`），MCP TS 工程通过 `import-from-json-schema` 生成 TS 类型，避免双向漂移。

---

### 2.6 P1 - MCP 与 Pipeline 边界不清晰

**现象：**

- `mcp-servers/sdd-pipeline` 内部其实是 Node 包装层，最终又调用 `python scripts/run_pipeline.py`：MCP 只是把 CLI 子进程透出给 Agent；
- 这意味着 **"用 Python 还是用 MCP" 由 Agent / 调用方决定**，但两条路径产物、错误码、JSON 输出格式可能漂移；
- `arch-standard` MCP 与 `docs/arch-standards/` 的同步靠脚本 `check_arch_standards_sync.py` 校验，本质是 "复制粘贴" 模式。

**改进建议：**

1. **把 Python pipeline 暴露为 HTTP / stdio JSON-RPC 服务**（FastAPI 或简单 stdio JSON server），MCP server 直接对接服务而非 spawn 子进程；
2. **明确 MCP 是"瘦层"**：MCP 只做协议适配 + 参数校验，业务一律落在 Python；
3. **arch-standard 文档单源**：仓库根 `arch-standards/*.md`，MCP server 启动时直接读，不再生成副本。

---

### 2.7 P2 - 缺乏可观测性 / 度量体系

**现象：**

- 仓库有 `ops_log.py` 与 `.spec/ops/project-ops.jsonl` 记录操作，但缺 **adoption metrics**：哪些 feature 用了轻量 SDD？Gate 失败 Top N？AutoPilot 自动决策 vs 人工干预的比例？
- 没有 dashboard 展示项目级健康度。

**改进建议：**

1. 在 `ops_log` 里追加 `gate_outcome / sdd_level / risk_tier / auto_decision_count / human_override_count` 字段；
2. 在 `project-console.html` 中加入趋势图（Gate PASS 率、平均周期时间、AMBIGUOUS 留滞数）；
3. 提供 `pipeline metrics export --to prometheus|csv`，方便接入团队 BI。

---

## 3. 功能 / 流程层面的问题

### 3.1 P0 - SDD 分级（轻量/标准/完整）未做事实驱动自动判定

**现象：**（与 `docs/sdd-architecture-open-items.md` P0-1 一致）

- `feature-brief.md` 已有 `sdd_level` 字段；
- 但当前仍主要由人工填写 `risk_tier` / `capability_tags`，系统根据 tag 决定文件集合；
- "支付/资金/跨系统写自动进入 full" 这一关键承诺尚未真正自动化；
- `requirement-analyzer` skill 虽在但未集成成强制前置。

**风险：**

- 团队在自填 tag 时倾向"少打"，规避完整 SDD 的成本；
- 高风险需求可能被错误降级为标准甚至轻量。

**改进建议：**

1. **强制把 `requirement-analyzer` 嵌入 `generate-feature-brief`**：先做语义抽取（关键词：钱、支付、对账、库存、外部系统、转账、密钥、PII），再产出 `risk_tier`/`capability_tags`/`sdd_level` 提案；
2. **AI 推断 + 规则联合裁判**：人工只能升级不能降级；
3. **把分级判定逻辑落成可单测的纯函数 + 黄金集合（fixture）**，明确 "支付下单" / "只读查询" / "DB 字段加列" 三类典型应得到什么 sdd_level；
4. **失败兜底**：当模型置信度低（多关键词命中或冲突）时，强制 `sdd_level=full`。

---

### 3.2 P0 - AutoPilot Skill 行权过激，但事实源支撑不够

**现象：**

`skills/sdd-assistant/SKILL.md` 写道：

> "你必须无需请示，连续调用 `sdd-pipeline` 的所有必要工具（Phase 0 -> 4），直到生成完精准对齐的测试骨架为止。"
> "状态驱动…严禁在回复中询问'是否继续'。"

但与此同时：

- project-explorer 还是 lexical-v2；
- polyquery 可能 fallback 到本地；
- risk_tier 由人工填写；
- Gate 5 真实业务测试需要在 attached project 自行配置 verification_commands，仓库自身给的是 fixture。

**风险：**

- AutoPilot 在事实源不可信时 **"高速生成低质量产物"**，反而放大幻觉而不是消除；
- 一旦 Gate 1/2 误 PASS（低可信源 + 严格模式未启用），错误会沿着流水线传播到 Gate 4 的测试骨架，污染下游；
- "硬阻断" 仅在命名/反向依赖/契约/对齐 4 类红线上，缺 "事实源可信度过低" 这一通用熔断条件。

**改进建议：**

1. **AutoPilot 的进入条件设硬门槛**：
   - `module-map.confidence ≥ medium`；
   - `schema-context.source ≠ local-fallback` 或 risk_tier=low；
   - `requirement-analyzer` 已成功执行且无矛盾 tag；
   不达标自动降级为 "Manual-Review Mode"，每个 Gate 后必须人工确认；
2. **新增 "事实可信度熔断" 红线**：confidence=low 且 risk_tier=high 直接停流，而不是 WARN；
3. **报告 = AutoPilot 的强制契约**：每条 AutoPilot 决策必须写入 `auto_pilot_log.json`，含决策理由 + 引用证据 hash，便于事后审计；
4. **加"是否暂停在审批前"开关（默认开启）**：让团队渐进信任 AutoPilot。

---

### 3.3 P1 - 仅面向 Java/Spring，跨技术栈是二等公民

**现象：**

- 模板（`接口文档.template.md`、`数据模型.template.md`、`支付状态机.template.md`）默认 Java 工程心智；
- `module-map.json` schema 偏 Java 语义（FQN、包、注解）；
- arch-standards 含 "Controller 调 Repository" 这类 Spring MVC 红线，对 Go/Python/前端无意义；
- `examples/fixtures/*` 4 个示例全是 Java 类型场景。

**风险：**

- 一仓多语言团队（典型：后端 Java + 前端 React + 数据 Python）只能在后端享受 SDD；
- 微服务异构栈下，跨服务设计无法在同一 Baseline 内对齐。

**改进建议：**

1. **抽象 "技术栈 Profile"**：`profiles/{java-spring,node-nest,go-gin,python-fastapi,react-spa}/` 各自带：
   - 模板（接口文档、数据模型、模块布局…）
   - arch-standards
   - scanner 实现
   - Gate 红线规则
2. **`feature-brief.md` 增加 `tech_profile` 字段**，pipeline 加载对应 profile；
3. **微服务多 profile**：`attached-project.json` 支持 `components: [{name, root, profile}]`，每个组件独立产 module-map，跨组件契约靠"事件/接口契约"显式登记；
4. **示例 fixtures 至少新增 2 个**：`node-api-light` 和 `python-async-event`。

---

### 3.4 P1 - Constitution / 架构红线缺失"feature 级"演化空间

**现象：**

- `constitution.md` 是项目级单点，所有 feature 共用；
- 当不同 feature 需要不同纪律（例如老模块允许临时违反、新模块强约束），目前只能 `tech-debt.md` 注释；
- 红线缺乏"豁免审批"流程。

**改进建议：**

1. **支持 `feature-constitution-overrides.md`**（feature 目录内）声明本 feature 内的临时豁免，由 Gate 3 解析；
2. **豁免必须带过期时间 + 责任人 + 还款计划**，否则 Release Gate 拒绝；
3. **Constitution 引入版本号**：未来红线升级不影响存量 feature 的回放。

---

### 3.5 P1 - Gate 5 "覆盖验证"与真实业务测试解耦不彻底

**现象：**

- README 自陈："Gate 5 当前仍以设计验证测试为主，真实业务测试需要在 attached project 中配置 verification_commands"；
- 也就是说：仓库自身只能跑 fixture，业务方真实跑测试要自己接命令；
- `module-map` 低可信时（已知问题）追溯也不准。

**风险：**

- "测试覆盖通过" 的语义不稳定，业务方可能误以为 Gate 5 PASS 等于"P0/P1 用例全过"；
- 接入成本高（每个项目都要单独配 verification_commands）。

**改进建议：**

1. **明确 Gate 5 的两层语义**：
   - L1：设计验证测试（fixture）—— 仓库自跑；
   - L2：业务真实测试（attached）—— 由 attached project 提供，必须给出 `junit-xml / pytest-xml / go-test-json` 标准化报告；
2. **报告字段对齐**：`verify-report.json` 必须显式标 `level=L1|L2|both`，输出"哪些 REQ 在哪一层被覆盖"；
3. **常见框架开箱即用 verification 模板**：Maven Surefire、Gradle Test、Jest、PyTest、go test —— 每种给一份默认 verification_commands；
4. **覆盖度 >= P0 100% / P1 90%** 等阈值由 capability_tags 自动决定（支付强制 100%）。

---

### 3.6 P1 - 设计版本管理过于线性

**现象：**

- `design-v1.md → design-v2.md` 单调递增；
- 没有"分支设计"概念（同一 feature 同时探索两套实现方案）；
- `superseded_by` 仅指向最新 ACTIVE，无法追"被废弃方案的失败原因"。

**改进建议：**

1. 引入 `design-vN-{slug}.md`（slug 是简短候选名）支持并行探索；
2. `sdd-index-design.json` 增加 `lineage` 字段记录决策树；
3. 在 ADR（架构决策记录）目录里同步留底"为什么淘汰 vN-alt"。

---

### 3.7 P2 - `[AMBIGUOUS]` 解决率没有度量

**现象：**

- AMBIGUOUS 标记机制是亮点，但没有统计：跨 feature 平均每条 brief 留 N 个、解决耗时多久、被 RESOLVED 的比例；
- 没有"未解决留滞超 X 天报警"。

**改进建议：**

1. `ambiguity_tracker.py` 已存在，扩展为生成 `ambiguity-overview.json/md`；
2. project-console 加面板：留滞 > 3 天的 AMBIGUOUS 高亮；
3. 严格模式下 AMBIGUOUS 未解决禁止 design-cycle 进入 Gate 1。

---

### 3.8 P2 - 国际化 / 文档语言治理

**现象：**

- 仓库内部模板是中文，但很多代码注释、CLI help、错误信息是英文；
- 文档也是中英混排（README 中文、架构标准英文）。

**改进建议：**

1. 选定 **唯一第一语言**（建议英文，便于开源传播；中文版作为 `*.zh-CN.md` 镜像）；
2. CLI 错误信息支持 `LANG=zh_CN` 切换；
3. 模板用占位符（如 `{{interface_name}}`）+ i18n bundle 而不是硬编码中文章节名（"接口文档" vs "API Spec"）。

---

### 3.9 P2 - 安全与凭据治理

**现象：**

- `.env.example` 列出了 Postgres / Oracle 多套密码字段；
- polyquery 通过本地配置接入数据库，`config/polyquery.json` 在仓库内；
- 没有提示用 Vault / SOPS / 1Password CLI 之类。

**改进建议：**

1. 文档里强调 **生产强烈不建议把任何凭据写入仓库**；
2. polyquery 配置支持 `${VAULT:secret/db#password}` 风格变量解析；
3. 加一份 `SECURITY.md`，覆盖：连接池权限、最小权限、审计、漏洞披露、对外 PR 审查清单。

---

## 4. 改进路线图（优先级 / 估算）

> 估算粒度：S=≤1 周、M=1-3 周、L=≥1 月（按 1-2 人投入）

| 优先级 | 主题 | 关键任务 | 估算 |
| --- | --- | --- | --- |
| **P0** | scripts 包化 + run_pipeline 解耦 | 引入 Command Registry、拆分 1000+ 行检查器、单一入口、`pyproject.toml` 暴露 console scripts | M |
| **P0** | scanner 升级到 AST | 接入 JavaParser / Symbol Solver；`module-map.confidence` 联动 Gate 决策 | M-L |
| **P0** | sdd_level 自动推导 | `requirement-analyzer` 强前置，黄金集合测试，高风险关键词自动 full | S-M |
| **P0** | AutoPilot 熔断条件 | confidence/source/AMBIGUOUS 三道前置门 + auto_pilot_log 审计 | S |
| **P0** | polyquery 严格模式默认 fail-fast | 严格模式贯穿所有刷新入口 | S |
| **P1** | 跨平台一致性 | doctor 唯一化、CI 多平台矩阵、文档去 PowerShell 偏置 | S |
| **P1** | 依赖与测试治理 | 修复 tests 源码丢失、补 dependencies、生成 lock、加 Makefile | S |
| **P1** | 多技术栈 Profile | profiles/{java,node,go,py} + tech_profile 字段 + 新示例 | L |
| **P1** | Gate 5 真实测试标准化 | L1/L2 分层、junit-xml 协议、覆盖阈值与 capability_tags 联动 | M |
| **P1** | 命名/目录收敛 | 别名清理、`.spec` 与 `specs` 边界、schemas 单源 | S-M |
| **P1** | MCP 与 Pipeline 边界 | 把 pipeline 暴露为 stdio JSON-RPC 服务 | M |
| **P2** | 可观测性 | ops_log 字段扩展 + project-console 趋势图 + metrics 导出 | M |
| **P2** | 设计分支与 ADR | design-vN-slug + lineage + ADR 目录 | S |
| **P2** | AMBIGUOUS 度量与拦截 | tracker 升级 + 严格模式拦截 | S |
| **P2** | i18n / 安全 | 统一第一语言 + SECURITY.md + 凭据外置 | S |

---

## 5. 风险与反向意见（值得自我警惕）

为避免给出"全是问题"的偏颇结论，列两个 **反向观察**：

1. **复杂度有其必要性**：SDD 试图把"AI 自动化设计"约束到生产可信级别，本身就需要事实源、双态索引、版本冻结、capability 治理这套体系。盲目"瘦身" 会把核心价值砍掉。重构时必须把"为什么 Gate 2 / Gate 5 这么写"作为不可妥协的语义前提。
2. **MVP 状态披露已较充分**：仓库已经有 `sdd-architecture-improvement-backlog.md` 与 `sdd-architecture-open-items.md` 自陈短板，态度坦诚。这意味着上文很多 P0 其实作者已知，**优先级排序与跨语言扩展** 才是真正"作者尚未充分思考的"维度。

---

## 6. 一句话总结

> SDD 在"方法论"上已经走得很远——双态 Baseline + capability_tags + 5 道 Gate 是一套有想法的治理框架；
> 但在"工程化"上仍是 **MVP 阶段的巨石**：把 `scripts/` 包化、把 scanner 升到 AST、把分级与 AutoPilot 用事实驱动、把跨平台 / 跨技术栈做成一等公民，
> 才能把它从"试点工具"推到"团队可规模化使用的生产级 SDD 平台"。
