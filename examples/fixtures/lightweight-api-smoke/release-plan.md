# Release Plan

```yaml
release:
  owner: smoke-owner
  approver: smoke-approver
  rollback:
    ready: true
  monitoring:
    ready: true
    metrics:
      - smoke_success_rate
  alerting:
    ready: true
    rules:
      - smoke_error_rate_high
  rollout:
    ready: true
    batches:
      - name: canary
        scope: 10%
      - name: full
        scope: 100%
```
