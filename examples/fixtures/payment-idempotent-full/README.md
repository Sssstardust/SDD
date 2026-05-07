# payment-idempotent-full

用途：

- 完整高风险 `payment + idempotent` fixture。
- 演示审批、`attached_execution_required=true`、高风险 release gate 通过态。

命令链：

```powershell
python scripts/run_pipeline.py release-gate examples/fixtures/payment-idempotent-full
python scripts/run_pipeline.py validate-reports examples/fixtures/payment-idempotent-full --stage all
```

预期摘要：

- `release-gate`: `PASS`
- `validate-reports --stage all`: `PASS`
