---
name: sdd-validate
description: 对 specs/<feature> 下的技术方案-v{N}.md 与设计包执行架构门控校验（设计门控 Gate 1/2/3，可选实现门控 Gate 4/5）。当 Agent 需要在设计完成后做完整性、真实性、架构规范联合校验，或需要把门控报告.json 作为定向修复输入时使用本 Skill。
---

# 架构校验器（设计门控）

使用 [run.py](run.py) 作为执行入口。

本 Skill 是 SDD 流水线中「设计门控」与「实现门控」的统一校验出口，
对应统一阶段命名（见仓库根 `docs/SDD架构与功能改进建议.md` 的命名词表）：

- `设计门控`（design-gate）：Gate 1（完整性）/ Gate 2（真实性）/ Gate 3（架构规范）。
- `实现门控`（impl-gate）：Gate 4（骨架对齐）/ Gate 5（覆盖率），按需启用。

按以下流程执行：

1. 读取入参 `workspace`（即 specs/<feature> 目录）。
2. 默认执行 `gate1`、`gate2`、`gate3`；可通过 `--gates` 显式指定子集或追加 `gate4`/`gate5`。
3. 每个 Gate 独立产出结果，统一汇总为 `output.schema.json` 约定的结构化结果。
4. 任一 Gate 失败时，整体 `status=fail`，并保留各 Gate 的 `exit_code` 供定向修复。
5. 校验前必须保证设计已生成：缺少 `技术方案-v{N}.md` 时直接判失败，而不是静默跳过。

遵循以下规则：

- 只校验、不修改：本 Skill 绝不写回设计文档或 `.spec/` 下的 JSON 索引。
- 门控产物（`门控报告.json`，物理名 `gate-report.json`）是下一轮 `sdd-generation --feedback` 的输入，必须保持机器可读。
- `strict` 模式启用架构红线严格检查（命名、分层、外部调用契约等），用于发布前把关。
- 产物命名以中文显示名为准；物理文件名遵循仓库统一映射（`sdd_core/infrastructure/artifact_names.py`）。

输入 / 输出契约：

- 入参见 [input.schema.json](input.schema.json)：`workspace`（必填）、`gates`、`strict`、`attachment_file`、`profile`。
- 出参见 [output.schema.json](output.schema.json)：`status`、`results[]`（每个 Gate 的 `gate`/`success`/`exit_code`/`message`）、`summary`。

不要做以下事情：

- 不要在缺少设计文档时返回 `status=ok`。
- 不要把多个 Gate 的失败压缩成一句模糊结论；每个 Gate 的结果必须单独保留。
- 不要绕过门控直接宣称通过；门控的严肃性是 SDD 的核心价值。
