# Release Plan

```yaml
release:
  owner: fail-owner
  approver: fail-approver
  rollback:
    ready: true
  monitoring:
    ready: true
    metrics:
      - payment_approve_success_rate
  alerting:
    ready: true
    rules:
      - payment_approve_error_rate
  rollout:
    ready: true
    batches:
      - name: canary
        scope: 10%
      - name: full
        scope: 100%
```
