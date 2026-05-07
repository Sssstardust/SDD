# polyquery-snapshot-offline

用途：

- 演示 `polyquery snapshot` 离线复核场景。
- 不依赖在线 MCP 连接，直接消费离线 snapshot。

命令链：

```powershell
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --polyquery-snapshot examples/fixtures/polyquery-snapshot-offline/polyquery.snapshot.json --output .tmp_test_workspace\fixture-matrix\schema-context.generated.json
python scripts/assert_schema_context_fixture.py .tmp_test_workspace\fixture-matrix\schema-context.generated.json --expected-source polyquery-snapshot --expected-scenario ready --expected-table t_payment_order --expected-table t_payment_review_record
```

预期摘要：

- `refresh-schema-context`: `PASS`
- 输出 `schema-context.json` 的 `source=scenario=tables` 校验通过
