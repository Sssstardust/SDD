# Baseline Constitution

- generated_at: 2026-04-23T09:45:07.610852+00:00
- source_specs_dir: D:/project/SDD/specs
- source_count: 0

## 1. 项目级硬约束

- 所有设计与实现必须遵守分层边界，禁止跨层直连或绕过既有门禁。
- P0/P1 需求必须可追溯到测试或验证入口，未覆盖前不得视为完成。
- 高风险设计必须先完成审批，审批通过后才能进入实现阶段。
- Gate 5 未通过前不得写入实现态 baseline。
- 上线前必须完成回滚方案、监控与告警、灰度策略三项检查。

## 2. Greenfield 来源

- 当前未发现 greenfield bootstrap constitution，暂以主流程硬约束作为项目级红线基线。

## 3. 维护说明

- 该文件是 baseline 的治理快照，用于沉淀当前项目默认适用的工程红线。
- 若后续出现新的 greenfield bootstrap 宪法或项目级约束调整，应重跑生成流程更新本文件。
