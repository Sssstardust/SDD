# PolyQuery 接入说明

本项目已支持通过 polyquery MCP 生成 `schema-context.json`，用于 Brownfield Gate 2、设计生成和数据库事实校验。

当前仓库内置 fixture 矩阵见：

- [../examples/fixtures/README.md](../examples/fixtures/README.md)

目前已覆盖轻量 API、标准 `db-change`、多组件示例，以及 `polyquery snapshot` 离线 fixture。

## 1. 配置文件

复制示例配置：

```powershell
Copy-Item config\polyquery.example.json config\polyquery.json
```

`config/polyquery.json` 不建议提交到仓库。

本项目保留 polyquery 原版的多数据库、多数据源配置方式：同一个 MCP Server 可以同时配置 MySQL、PostgreSQL、Oracle、MongoDB、Redis、SQLite；同一种数据库可以通过 `*_CONFIGS` 配置多个数据源。

为了简化团队使用，`sources` 不是必填项。默认推荐由 SDD/agent 自动发现本次 feature 需要沉淀的表结构。

配置示例：

```json
{
  "enabled": true,
  "mcp": {
    "command": "npx",
    "args": ["-y", "polyquery-mcp"],
    "timeout_seconds": 30,
    "env": {
      "READ_ONLY_MODE": "true",
      "POSTGRES_CONFIGS": {
        "test": "postgresql://readonly:${POSTGRES_PASSWORD}@localhost:5432/app_test",
        "reporting": "postgresql://readonly:${POSTGRES_REPORTING_PASSWORD}@localhost:5432/reporting"
      },
      "ORACLE_CONFIGS": {
        "pdc": "oracle://readonly:${ORACLE_PDC_PASSWORD}@pdc-db.example.com:1521/pdc",
        "tob": "oracle://readonly:${ORACLE_TOB_PASSWORD}@tob-db.example.com:1521/tob"
      }
    }
  },
  "discovery": {
    "mode": "agent",
    "max_tables": 30,
    "on_ambiguous": "require-confirmation"
  }
}
```

说明：

- `mcp.env.*_CONFIGS` 保持 polyquery 原版格式。
- 在 JSON 配置里可以把 `POSTGRES_CONFIGS`、`ORACLE_CONFIGS` 等写成对象，SDD 适配层会在启动 MCP 时转换为 polyquery 需要的 JSON 字符串环境变量。
- 默认不需要写 `sources`，SDD 会从 feature 设计材料中提取候选表名和业务关键词，再调用 polyquery 的 `list_databases` / `list_tables` / `describe_table`。
- 敏感密码建议通过 `${ENV_NAME}` 引用环境变量，不写死到仓库。

生产接入安全边界：

- 只连接只读从库或专用元数据库。
- 只授予 metadata / information_schema / describe 权限。
- 禁止使用生产写账号或包含 DML/DDL 权限的业务账号。
- 必须设置查询超时、最大表数量和网络白名单。
- `config/polyquery.json`、`.env` 和真实连接串不得提交；请基于 `config/polyquery.example.json` 与 `.env.example` 本地配置。

DBA 权限申请最小模板：

```text
用途：SDD schema-context 只读元数据刷新
目标库/Schema：
权限范围：metadata / information_schema / describe only
账号类型：只读从库或专用元数据账号
网络来源：CI runner / 办公网段 / 指定跳板机
超时与限流：单次查询 <= 30s，最大表数量 <= 30
审计要求：记录申请人、执行时间、数据源、表数量、是否 fallback
```

高级模式可以继续配置 `sources` 作为人工白名单或搜索边界：

```json
{
  "sources": [
    {
      "db_type": "postgres",
      "connection_name": "test",
      "schema_name": "public",
      "tables": ["t_payment_order"]
    },
    {
      "db_type": "oracle",
      "connection_name": "tob",
      "schema_name": "TOB_OWNER",
      "include_tables": ["^T_TOB_"],
      "exclude_tables": ["_HIS$"]
    }
  ]
}
```

`sources[].connection_name` 必须对应 `*_CONFIGS` 中的数据源名称。

## 2. 刷新实时 schema-context

```powershell
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --polyquery-config config\polyquery.json --polyquery-fallback fail
```

自动发现指定 feature 需要的表：

```powershell
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --auto-discover specs\your-feature --polyquery-config config\polyquery.json --polyquery-fallback fail
```

成功后会写入当前 baseline 分桶：

```text
.spec/baselines/<attached-project-bucket>/schema-context.json
```

生成结果会标记：

- `source: polyquery`
- `scenario: ready`
- `tables[].sources: polyquery:<db_type>:<connection>:<schema>:<table>`

如果查库成功但没有表，会写入：

- `scenario: new-table`
- `tables: []`

如果 polyquery 调用失败且使用 `--polyquery-fallback fail`，会写入错误标记并返回失败：

```json
{
  "__error__": "错误信息",
  "ts": "2026-04-29T00:00:00+00:00",
  "source": "polyquery"
}
```

## 3. 本地降级

如果团队希望 polyquery 不可用时继续使用本地 SQL / design-pack 快照：

```powershell
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --polyquery-config config\polyquery.json --polyquery-fallback local
```

降级结果会标记：

- `source: local-fallback`
- `fallback_from: polyquery`

高风险 feature 不建议使用本地降级通过 Gate 2。发布或 CI 流程应使用：

```powershell
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --polyquery-config config\polyquery.json --polyquery-fallback fail
```

## 4. 离线快照

CI 或无法直接连接 MCP 的环境可以使用 polyquery snapshot：

```powershell
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --polyquery-snapshot .spec\polyquery.snapshot.json
```

snapshot 格式：

```json
{
  "tables": [
    {
      "db_type": "postgres",
      "connection_name": "test",
      "schema_name": "public",
      "table_name": "t_payment_order",
      "columns": [
        { "name": "payment_id", "type": "varchar", "nullable": false },
        { "name": "status", "type": "varchar", "nullable": true }
      ]
    }
  ]
}
```

## 5. 推荐流程

```powershell
python scripts/run_pipeline.py refresh-module-map
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --auto-discover specs\your-feature --polyquery-config config\polyquery.json --polyquery-fallback fail
python scripts/run_pipeline.py design-gates specs\your-feature
```
