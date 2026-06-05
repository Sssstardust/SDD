# SDD 架构与功能改进建议

> 本文记录 SDD 仓库的架构诊断、改进方案和 2026-06-05 的落地结果。目标是让 SDD 回到清晰的初衷：一个可供 OpenAI / Claude / Gemini 等 Agent 直接接入的标准化 SDD skill。

## 1. 架构判断

SDD 当前应采用“内核 + 门面 + 工具协议”的分层：

- `sdd_core/`：确定性内核，承载 DDD 建模、Gate 校验、基线、产物路径和流程编排。
- `skills/`：唯一推荐给 Agent 的对外门面。`sdd-assistant` 是编排提示词入口，`requirement-analyzer`、`sdd-generation`、`sdd-validate` 是确定性原子能力。
- `mcp-servers/`：工具协议层，服务于深度集成，不作为新 Agent 的首选入口。
- `sdd_core/run_pipeline.py`：CLI 实现层，供 skill、MCP、CI 和高级本地调用复用。

推荐策略仍是 A3 + B3：分层共存，但对 Agent 只宣传 skill；原子能力保持可执行 + schema，整体编排交给 Agent 提示词。

## 2. 原问题清单

| 项 | 问题 | 处理结论 |
| :--- | :--- | :--- |
| P0-1 | 命名词表不统一 | 已完成 |
| P0-2 | `sdd-assistant` 宣称与 `run.py` 实际能力不符 | 已完成 |
| P0-3 | `sdd-validate` 缺少 `SKILL.md` | 已完成 |
| P0-4 | README 文档死链 | 已完成 |
| P1-5 | 缺少唯一推荐接入路径 | 已完成 |
| P1-6 | skill / MCP / CLI 重复编排 | 已完成 |
| P1-7 | skill 目录契约缺少校验 | 已完成 |
| P2-8 | 语言无关扫描未真正落地 | 已完成 |
| P2-9 | 产物命名中英文混杂 | 已完成 |
| P2-10 | 缺少 skill 数据流协议 | 已完成 |

## 3. 落地结果

| 项 | 状态 | 落地位置 |
| :--- | :--- | :--- |
| 统一命名词表 | 已完成 | `README.md`、`skills/*/SKILL.md`、`skills/*/manifest.yaml` |
| `sdd-assistant` 改为提示词编排门面 | 已完成 | `skills/sdd-assistant/SKILL.md`、`skills/sdd-assistant/run.py` |
| 补齐 `sdd-validate` skill 契约 | 已完成 | `skills/sdd-validate/SKILL.md` |
| 修复 README 链接与快速上手 | 已完成 | `README.md`、`docs/agent-integration.md`、`docs/skill-data-flow.md`、`docs/team-onboarding.md` |
| skill 目录契约校验 | 已完成 | `sdd_core/generate_agent_configs.py` 的 `check_skill_contract` |
| 语言画像注册表 | 已完成 | `sdd_core/domain/language_profiles.py`、`sdd_core/domain/attached_project.py` |
| 多语言 project-explorer scanner | 已完成 | `mcp-servers/project-explorer/src`、`mcp-servers/project-explorer/dist` |
| CLI 门控断裂修复 | 已完成 | `sdd_core/run_pipeline.py`、`sdd_core/application/semantic_validate.py`、`sdd_core/application/gates/gate_runtime.py` |
| Gate catalog 去旧脚本引用 | 已完成 | `sdd_core/application/gates/catalog.py` |
| baseline 刷新接入 scanner | 已完成 | `refresh-baseline` 优先调用 `project-explorer refresh_module_map` |
| 产物命名映射 | 已完成 | `sdd_core/infrastructure/artifact_names.py` |

## 4. P2-8 语言无关扫描说明

此前 `project-explorer` 的 TS 源和 `dist/server.js` 不在工作树，导致只能先补 Python 侧语言画像。现在已补齐扫描器本体：

- 支持语言：Java、Python、TypeScript、JavaScript、Go。
- MCP 工具：`scan_modules`、`verify_class_exists`、`get_class_detail`、`refresh_module_map`。
- `refresh-baseline` 会优先委托 `project-explorer` 生成 `module-map.json`，失败时才回退 Python 轻量扫描。
- `doctor.py --json` 中 `project-explorer MCP dist` 与 `scan_modules` 已可通过。

## 5. CLI 断裂修复说明

此前 `run_pipeline.py` 和 `semantic_validate.py` 仍引用已删除脚本，如 `gate1.py`、`check_design_truthfulness.py`、`check_arch_semantics.py`、`refresh_module_map.py`。现在已改为应用层实现：

- Gate 1/2/3 走 `sdd_core/application/gates/gate_runtime.py`。
- `validate` 复用同一套 Gate runtime。
- `refresh-baseline` 走 `project-explorer` + fallback。
- `doctor` 的 baseline key 检查也不再依赖已删除脚本。

## 6. 验证记录

已执行：

- `node mcp-servers/project-explorer/dist/scanner.test.js`
- MCP stdio `tools/list`
- MCP stdio `tools/call scan_modules`
- `python sdd_core/run_pipeline.py --help`
- `python sdd_core/run_pipeline.py --json gate1 <temp-feature>`
- `python sdd_core/run_pipeline.py refresh-baseline`
- `python sdd_core/doctor.py --json`

已知环境项：`doctor.py --json` 仍会因当前机器 Python 3.12、未安装 pytest、缺少 polyquery 示例/治理脚本、缺少 `doctor_smoke.py` 返回失败；这些不是本轮 P0-P2 架构改造与 scanner/CLI 修复的阻塞项。
