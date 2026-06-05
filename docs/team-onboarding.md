# 团队接入规范

> 面向首次接入 SDD 的研发团队。目标：按统一阶段、统一产物命名、统一入口完成端到端流程。

## 1. 环境准备

- Python 3.13+（推荐 `uv` 管理环境）
- Node.js 20+（运行 MCP 实现层时需要）
- 一键健康检查：`python sdd_core/doctor.py`

## 2. 唯一推荐入口

对人和 Agent 一致：**统一从 `skills/` 接入**。

- 编排出口：`skills/sdd-assistant`
- 原子 Skill：`requirement-analyzer` / `sdd-generation` / `sdd-validate`

不要直接以 `sdd-pipeline` MCP 或 `run_pipeline.py` CLI 作为日常入口（它们是实现层）。

## 3. 统一阶段

分析需求 → 生成设计 → 设计门控 → 生成切片 → 实现门控 → 发布门控。

各阶段命名与对应 Skill 见 [Agent 接入说明](agent-integration.md) 的命名词表。

## 4. 产物命名约定

- 一律使用**中文显示名**沟通（如 `需求规格.md`、`技术方案-v{N}.md`、`设计包`、`门控报告.json`）。
- 物理文件名遵循统一映射，单一真相源：`sdd_core/infrastructure/artifact_names.py`。
- `.spec/` 下的 JSON 索引**禁止手动编辑**，只允许工具链写入。

## 5. 关键纪律

- 设计先行：需求结构化、设计通过门控前，不动实现代码。
- 不可跳步、不可伪造门控通过。
- 高风险（`risk_tier=high`）变更必须有 `审批记录.json`。
- 歧义先澄清：未解决的 `[AMBIGUOUS]` 不进入设计。

## 6. 常见问题

- **门控失败怎么办？** 把 `门控报告.json` 作为 `--feedback` 回灌给 `sdd-generation`，有限次重试后仍失败则升级人工。
- **多项目如何隔离？** 通过附着项目的基线 Bucket（项目名 + 路径 SHA1 前 8 位）天然隔离，详见 `SDD项目概述.md` 第九节。
