# multi-component-api

用途：

- 多组件 fixture。
- 演示 `affected_components`、组件级需求范围和组件样例配置。

命令链：

```powershell
python scripts/run_pipeline.py release-gate examples/fixtures/multi-component-api
python scripts/run_pipeline.py validate-reports examples/fixtures/multi-component-api --stage implementation
```

预期摘要：

- `release-gate`: `PASS`
- `validate-reports --stage implementation`: `PASS`
- `feature-brief.md` 中保留 `affected_components`
