# lightweight-api-smoke

用途：

- 最小轻量 API fixture。
- 也是 `scripts/doctor.ps1` 的 Gate smoke fixture。

命令链：

```powershell
python scripts/run_pipeline.py release-gate examples/fixtures/lightweight-api-smoke
python scripts/run_pipeline.py validate-reports examples/fixtures/lightweight-api-smoke --stage implementation
```

预期摘要：

- `release-gate`: `PASS`
- `validate-reports --stage implementation`: `PASS`
