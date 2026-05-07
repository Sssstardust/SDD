# Fixture Matrix

当前内置 fixture：

- `lightweight-api-smoke`
  - 场景：轻量 API、doctor smoke
  - 命令：`release-gate`、`validate-reports --stage implementation`
  - 预期：全部 `PASS`
- `standard-db-change`
  - 场景：标准 `db-change`
  - 命令：`release-gate`、`validate-reports --stage implementation`
  - 预期：全部 `PASS`，并包含 SQL 回滚证据
- `multi-component-api`
  - 场景：多组件 Brownfield
  - 命令：`release-gate`、`validate-reports --stage implementation`
  - 预期：全部 `PASS`，并保留 `affected_components` 示例
- `payment-idempotent-full`
  - 场景：高风险 `payment + idempotent + full`
  - 命令：`release-gate`、`validate-reports --stage all`
  - 预期：全部 `PASS`，并包含审批与 `attached_execution_required=true`
- `polyquery-snapshot-offline`
  - 场景：离线 `polyquery snapshot`
  - 命令：`refresh-schema-context --from-polyquery --polyquery-snapshot ...`
  - 预期：输出 `source=polyquery-snapshot`、`scenario=ready`
- `governance-fail-high-risk-attached`
  - 场景：高风险治理失败
  - 命令：`gate5`、`validate-reports`、`release-gate`
  - 预期：按治理规则失败，并能命中 `attached_execution` 相关错误
- `governance-warn-gate5-p1`
  - 场景：Gate 5 `WARN`
  - 命令：`gate5`
  - 预期：仅 `P1` 缺口时输出 `WARN` 且不阻断

统一校验命令：

```powershell
python scripts/validate_fixture_matrix.py
```

按名称只校验部分 fixture：

```powershell
python scripts/validate_fixture_matrix.py --fixture lightweight-api-smoke --fixture standard-db-change
```

说明：

- `attached-sample-project/` 是附着项目示例，不属于 feature fixture 矩阵。
- 目前矩阵已同时覆盖正向样例与治理回归样例。
- 下一步可继续补更贴近真实业务的长链路样例、组合场景，以及更多失败原因分型。
