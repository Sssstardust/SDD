# standard-db-change

用途：

- 标准 `db-change` fixture。
- 演示 release gate 对结构化发布计划和 SQL 回滚脚本的要求。

命令链：

```powershell
python scripts/run_pipeline.py release-gate examples/fixtures/standard-db-change
python scripts/run_pipeline.py validate-reports examples/fixtures/standard-db-change --stage implementation
```

预期摘要：

- `release-gate`: `PASS`，并能识别 SQL `DOWN/ROLLBACK` 证据
- `validate-reports --stage implementation`: `PASS`
