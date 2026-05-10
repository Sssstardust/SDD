# Team Onboarding Entry

## 一条命令接入

推荐团队成员使用这条标准入口：

```powershell
python scripts/run_pipeline.py onboard-project `
  --project-root D:\your-target-project `
  --design-root D:\your-design-root `
  --schema-root D:\your-target-project\src\main\resources
```

别名：

```powershell
python scripts/run_pipeline.py bootstrap-attached-project `
  --project-root D:\your-target-project `
  --design-root D:\your-design-root `
  --schema-root D:\your-target-project\src\main\resources
```

---

## 这条命令会做什么

会顺序完成以下动作：

1. 保存附着目标项目配置
2. 刷新 baseline 快照
3. 生成项目级控制台产物

实际链路等价于：

```powershell
python scripts/run_pipeline.py attach-project ...
python scripts/run_pipeline.py refresh-baseline --strict
python scripts/run_pipeline.py project-console-cycle
```

---

## 完成后你会得到什么

附着配置：

- [../.spec/attached-project.json](../.spec/attached-project.json)

baseline 分桶目录：

- `.spec/baselines/<attached-project-bucket>/`

项目级产物分桶目录：

- `.spec/project-artifacts/<attached-project-bucket>/`

常用产物：

- `module-map.json`
- `schema-context.json`
- `constitution.md`
- `tech-debt.md`
- `project-next.json`
- `flow-overview.json`
- `project-console.json`
- `tooling-hygiene.json`

---

## Onboarding 后的常用命令

查看当前附着项目：

```powershell
python scripts/run_pipeline.py show-attachment
```

对单个 feature 跑 Gate：

```powershell
python scripts/run_pipeline.py gate1 your-feature
python scripts/run_pipeline.py gate2 your-feature
python scripts/run_pipeline.py gate3 your-feature
python scripts/run_pipeline.py generate-task-slices your-feature
python scripts/run_pipeline.py gate4 your-feature
python scripts/run_pipeline.py gate5 your-feature
```

同步实现态 baseline 时不要依赖 latest，显式传入已批准版本：

```powershell
python scripts/run_pipeline.py sync-baseline your-feature --design-version v1
```

刷新整套项目级产物：

```powershell
python scripts/run_pipeline.py project-console-cycle
```

推荐 strict-first 主链路：

```powershell
python scripts/run_pipeline.py refresh-baseline --strict --feature-dir specs\your-feature
python scripts/run_pipeline.py design-gates specs\your-feature --strict
python scripts/run_pipeline.py implementation-gates specs\your-feature --strict
python scripts/run_pipeline.py release-gate specs\your-feature --strict
python scripts/run_pipeline.py validate-all-reports --stage all
```

GitHub Actions 示例：

- [../.github/workflows/sdd-pipeline.example.yml](../.github/workflows/sdd-pipeline.example.yml)

校验仓库内置样例矩阵：

```powershell
python scripts/validate_fixture_matrix.py
```

内置样例说明见：

- [../examples/fixtures/README.md](../examples/fixtures/README.md)
- [Report Field Guide](report-field-guide.md)

其中高风险和离线快照样例也已内置，可直接参考：

- `payment-idempotent-full`
- `polyquery-snapshot-offline`

---

## 建议

- 团队内部发布时，把这份文档作为入口页
- 新成员第一次接入时，优先只教 `onboard-project`
- 其他命令放到第二层文档，不要一开始让大家手工拼链路
- 接入 Codex、Gemini CLI、OpenCode 等 agent 时，参考 [Agent 接入说明](agent-integration.md)

## SDD 分级规则

在 `feature-brief.md` 中维护 `sdd_level`：

- `light`：简单查询、简单内部 API，仅要求必要接口材料。
- `standard`：涉及接口、数据库变更、任务拆分和测试骨架。
- `full`：涉及支付、资金、幂等、外部调用、异步事件、状态机、审批或其他高风险场景。

当前 Gate 1 会按 `sdd_level + capability_tags` 校验 Design Pack。高风险 feature 必须使用 `full`；`light` 不允许声明 `payment`、`idempotent`、`async`、`external-call` 等完整模式能力。

## 推广节奏

1. 第 1 阶段只对高风险需求完整执行 SDD，普通需求先用 `light` 或 `standard`。
2. 第 2 阶段把常规需求纳入轻量 SDD，并要求每个例外补录最小设计、测试证据和 baseline 记录。
3. 第 3 阶段把 `design-gates`、`implementation-gates`、`release-gate` 接入 CI。

## Release 例外

如需临时放行、紧急修复或带条件上线，可在对应 `reports/vN/` 下补录：

- `exception.json`

模板可参考：

- [../document/template/Release-Exception-模板.json](../document/template/Release-Exception-模板.json)

当前 Release Gate 会校验以下字段：

- `reason`
- `approver`
- `expires_at`
- `remediation_plan`
- `followup_gate`
- `waived_checks`

`waived_checks` 当前支持的最小豁免项包括：

- `attached_execution`
- `release_plan`
- `gray_strategy`
- `monitoring_alert`
- `rollback`

## 当前边界

- Gate 1/2/3/5 的结论来自脚本报告，不是 AI 自由判断。
- `project-explorer` 当前不是编译器级索引，复杂框架特性可能只形成中低可信证据。
- `schema-context` 的本地快照与 polyquery 元数据可信度不同，高风险 feature 推荐使用 `--polyquery-fallback fail`。
- `design-pack/` 是草稿区；Gate 1 通过后冻结到 `reports/vN/design-pack.snapshot/`，后续同步优先读取快照。
